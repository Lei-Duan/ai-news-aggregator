"""
Reddit fetcher via RSS feeds (no auth required).
Uses /r/{subreddit}/hot.rss — RSS endpoints are far less aggressively blocked
than the JSON API.
"""

import asyncio
import aiohttp
import feedparser
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

RSS_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class RedditRSSPost:
    id: str
    title: str
    text: str
    author: str
    subreddit: str
    url: str
    score: int
    num_comments: int
    created_at: datetime
    permalink: str
    flair: Optional[str]
    upvote_ratio: float


class RedditRSSFetcher:
    BASE_URL = "https://www.reddit.com"

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def fetch_subreddit_feeds(self, subreddits: List[str]) -> List[RedditRSSPost]:
        all_posts: List[RedditRSSPost] = []

        async with aiohttp.ClientSession(
            headers={"User-Agent": RSS_USER_AGENT},
            timeout=self.timeout,
        ) as session:
            for subreddit in subreddits:
                try:
                    posts = await self._fetch_rss(session, subreddit)
                    all_posts.extend(posts)
                    logger.info(f"Reddit r/{subreddit}: {len(posts)} posts")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error fetching r/{subreddit}: {e}")

        all_posts.sort(key=lambda p: p.created_at, reverse=True)
        return all_posts[:120]

    async def _fetch_rss(self, session: aiohttp.ClientSession, subreddit: str) -> List[RedditRSSPost]:
        url = f"{self.BASE_URL}/r/{subreddit}/hot.rss?limit=25"
        async with session.get(url) as resp:
            if resp.status == 429:
                logger.warning(f"Reddit rate limit on r/{subreddit}, skipping")
                return []
            if resp.status != 200:
                logger.error(f"Reddit RSS {resp.status}: r/{subreddit}")
                return []
            content = await resp.text()

        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, content)

        posts = []
        for entry in feed.entries:
            post = self._parse_entry(entry, subreddit)
            if post and self._is_relevant(post.title + " " + post.text):
                posts.append(post)
        return posts

    def _parse_entry(self, entry, subreddit: str) -> Optional[RedditRSSPost]:
        try:
            # Parse published date — prefer published_parsed (already parsed by feedparser)
            published_at = datetime.now(tz=timezone.utc)
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, "published") and entry.published:
                try:
                    published_at = parsedate_to_datetime(entry.published)
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            # Extract text from the HTML content in RSS description
            raw_content = ""
            if hasattr(entry, "content") and entry.content:
                raw_content = entry.content[0].get("value", "")
            elif hasattr(entry, "summary"):
                raw_content = entry.summary or ""
            text = re.sub(r"<[^>]+>", " ", raw_content)
            text = re.sub(r"\s+", " ", text).strip()[:500]

            # Always link to the Reddit discussion thread, not the external URL
            permalink = entry.get("link", "")
            url = permalink

            # Build a stable ID from the permalink
            post_id = re.search(r"/comments/([a-z0-9]+)/", permalink)
            post_id = post_id.group(1) if post_id else permalink

            author = ""
            if hasattr(entry, "author"):
                author = entry.author.replace("/u/", "").replace("u/", "")

            return RedditRSSPost(
                id=post_id,
                title=entry.get("title", ""),
                text=text,
                author=author,
                subreddit=subreddit,
                url=url,
                score=0,          # not available in RSS
                num_comments=0,   # not available in RSS
                created_at=published_at,
                permalink=permalink,
                flair=None,
                upvote_ratio=0.0,
            )
        except Exception as e:
            logger.error(f"Error parsing Reddit RSS entry: {e}")
            return None

    def _is_relevant(self, text: str) -> bool:
        keywords = [
            "ai", "llm", "gpt", "claude", "gemini", "llama", "openai", "anthropic",
            "agent", "chatbot", "ml", "machine learning", "deep learning", "neural",
            "transformer", "diffusion", "fine-tun", "rag", "embedding", "inference",
            "build in public", "buildinpublic", "indie hacker", "side project",
            "saas", "mrr", "startup", "ship", "launch", "vibe coding",
        ]
        tl = text.lower()
        return any(kw in tl for kw in keywords)

    async def fetch_combined_feed(self, subreddits: List[str], keywords: List[str] = None) -> List[RedditRSSPost]:
        posts = await self.fetch_subreddit_feeds(subreddits)
        if keywords:
            posts = [
                p for p in posts
                if any(kw.lower() in (p.title + " " + p.text).lower() for kw in keywords)
            ]
        return posts
