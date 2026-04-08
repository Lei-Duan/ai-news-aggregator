"""
Podcast fetcher: parses AI podcast RSS feeds.
Returns episode metadata + RSS description/summary for Claude to summarize.
"""

import asyncio
import aiohttp
import feedparser
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

PODCAST_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class PodcastEpisode:
    guid: str
    title: str
    podcast_name: str
    rss_url: str
    episode_url: str
    audio_url: str
    published_at: datetime
    duration_sec: int
    description: str


class PodcastFetcher:
    def __init__(self):
        pass

    async def fetch_recent_episodes(
        self,
        rss_feeds: List[str],
        max_age_hours: int = 72,
        max_per_podcast: int = 2,
    ) -> List[PodcastEpisode]:
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
                    logger.info(f"Podcast {rss_url}: {len(episodes)} recent episodes")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error fetching podcast {rss_url}: {e}")

        return all_episodes

    async def _fetch_feed(self, session, rss_url, cutoff, max_per_podcast):
        async with session.get(rss_url) as resp:
            if resp.status != 200:
                return []
            content = await resp.text()

        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, content)
        podcast_name = feed.feed.get("title", rss_url)

        episodes = []
        for entry in feed.entries[:10]:
            if len(episodes) >= max_per_podcast:
                break
            ep = self._parse_entry(entry, podcast_name, rss_url)
            if ep and ep.published_at >= cutoff:
                episodes.append(ep)
        return episodes

    def _parse_entry(self, entry, podcast_name, rss_url) -> Optional[PodcastEpisode]:
        try:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            else:
                published = datetime.now(tz=timezone.utc)

            audio_url = ""
            for enc in getattr(entry, "enclosures", []):
                if "audio" in enc.get("type", ""):
                    audio_url = enc.get("href", "")
                    break

            duration_sec = self._parse_duration(str(getattr(entry, "itunes_duration", "0")))

            description = (
                getattr(entry, "itunes_summary", None)
                or getattr(entry, "summary", None)
                or getattr(entry, "description", "")
                or ""
            )
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
