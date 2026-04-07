"""
Podcast fetcher: parses AI podcast RSS feeds and optionally transcribes
episodes via pod2txt (https://pod2txt.vercel.app).

Without a POD2TXT_API_KEY the fetcher still returns episode metadata +
RSS description, which is enough for Claude to summarise.
"""

import asyncio
import aiohttp
import feedparser
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

PODCAST_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
POD2TXT_BASE = "https://pod2txt.vercel.app/api"
MAX_TRANSCRIPT_POLLS = 5
POLL_INTERVAL_SEC = 30


@dataclass
class PodcastEpisode:
    guid: str
    title: str
    podcast_name: str
    rss_url: str
    episode_url: str          # link to show notes / web page
    audio_url: str            # enclosure URL
    published_at: datetime
    duration_sec: int
    description: str          # RSS summary (always available)
    transcript: Optional[str] = None   # full text, if transcribed


class PodcastFetcher:
    def __init__(self, pod2txt_api_key: Optional[str] = None):
        self.pod2txt_api_key = pod2txt_api_key
        self.can_transcribe = bool(pod2txt_api_key)

    async def fetch_recent_episodes(
        self,
        rss_feeds: List[str],
        max_age_hours: int = 72,          # look back 3 days
        max_per_podcast: int = 2,
    ) -> List[PodcastEpisode]:
        """Fetch recent episodes from a list of RSS feed URLs."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=max_age_hours)
        all_episodes: List[PodcastEpisode] = []

        async with aiohttp.ClientSession(
            headers={"User-Agent": PODCAST_USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as session:
            for rss_url in rss_feeds:
                try:
                    episodes = await self._fetch_feed(session, rss_url, cutoff, max_per_podcast)
                    all_episodes.extend(episodes)
                    logger.info(f"Podcast RSS {rss_url}: {len(episodes)} recent episodes")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error fetching podcast feed {rss_url}: {e}")

        # Transcribe if API key is available
        if self.can_transcribe and all_episodes:
            all_episodes = await self._transcribe_episodes(all_episodes)

        return all_episodes

    async def _fetch_feed(
        self,
        session: aiohttp.ClientSession,
        rss_url: str,
        cutoff: datetime,
        max_per_podcast: int,
    ) -> List[PodcastEpisode]:
        async with session.get(rss_url) as resp:
            if resp.status != 200:
                logger.error(f"Podcast RSS error {resp.status}: {rss_url}")
                return []
            content = await resp.text()

        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, content)

        podcast_name = feed.feed.get("title", rss_url)
        episodes = []

        for entry in feed.entries[:10]:   # only check latest 10
            if len(episodes) >= max_per_podcast:
                break
            ep = self._parse_entry(entry, podcast_name, rss_url)
            if ep and ep.published_at >= cutoff:
                episodes.append(ep)

        return episodes

    def _parse_entry(self, entry, podcast_name: str, rss_url: str) -> Optional[PodcastEpisode]:
        try:
            # Published date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            else:
                published = datetime.now(tz=timezone.utc)

            # Audio enclosure URL
            audio_url = ""
            for enc in getattr(entry, "enclosures", []):
                if "audio" in enc.get("type", ""):
                    audio_url = enc.get("href", "")
                    break

            # Duration
            duration_str = getattr(entry, "itunes_duration", "0")
            duration_sec = self._parse_duration(str(duration_str))

            # Description: prefer itunes:summary, fall back to summary/description
            description = (
                getattr(entry, "itunes_summary", None)
                or getattr(entry, "summary", None)
                or getattr(entry, "description", "")
                or ""
            )
            # Strip HTML tags from description
            import re
            description = re.sub(r"<[^>]+>", "", description).strip()[:1000]

            guid = entry.get("id") or entry.get("guid") or entry.get("link", "")

            return PodcastEpisode(
                guid=guid,
                title=entry.get("title", "Untitled Episode"),
                podcast_name=podcast_name,
                rss_url=rss_url,
                episode_url=entry.get("link", ""),
                audio_url=audio_url,
                published_at=published,
                duration_sec=duration_sec,
                description=description,
            )
        except Exception as e:
            logger.error(f"Error parsing podcast entry: {e}")
            return None

    def _parse_duration(self, s: str) -> int:
        """Parse HH:MM:SS or MM:SS or raw seconds into total seconds."""
        try:
            parts = s.strip().split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            else:
                return int(float(s))
        except Exception:
            return 0

    async def _transcribe_episodes(self, episodes: List[PodcastEpisode]) -> List[PodcastEpisode]:
        """Submit episodes to pod2txt and poll for transcripts."""
        async with aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.pod2txt_api_key}"},
            timeout=aiohttp.ClientTimeout(total=60),
        ) as session:
            for ep in episodes:
                if not ep.audio_url and not ep.rss_url:
                    continue
                try:
                    transcript = await self._transcribe_one(session, ep)
                    if transcript:
                        ep.transcript = transcript[:4000]   # cap length
                        logger.info(f"Transcribed: {ep.title[:60]}")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Transcription failed for '{ep.title}': {e}")
        return episodes

    async def _transcribe_one(self, session: aiohttp.ClientSession, ep: PodcastEpisode) -> Optional[str]:
        """Start transcription job and poll until done."""
        payload = {"rss": ep.rss_url, "guid": ep.guid}
        async with session.post(f"{POD2TXT_BASE}/transcript", json=payload) as resp:
            if resp.status not in (200, 202):
                logger.warning(f"pod2txt submit failed {resp.status} for {ep.title}")
                return None
            data = await resp.json()
            job_id = data.get("id")

        if not job_id:
            return None

        for attempt in range(MAX_TRANSCRIPT_POLLS):
            await asyncio.sleep(POLL_INTERVAL_SEC)
            async with session.get(f"{POD2TXT_BASE}/transcript", params={"id": job_id}) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                status = data.get("status")
                if status == "ready":
                    return data.get("transcript") or data.get("text")
                elif status in ("error", "failed"):
                    logger.warning(f"pod2txt job failed for {ep.title}")
                    return None
                logger.debug(f"pod2txt poll {attempt + 1}/{MAX_TRANSCRIPT_POLLS}: {status}")

        logger.warning(f"pod2txt timed out for {ep.title}")
        return None
