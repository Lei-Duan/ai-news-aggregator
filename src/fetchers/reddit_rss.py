"""
Reddit fetcher via RSS (no auth required, no 403 from cloud IPs).
Uses /r/{subreddit}/hot.rss which works from any IP.
Score data is limited in RSS, so we sort by recency instead.
"""

import asyncio
import aiohttp
import feedparser
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

RSS_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) "
    "Gecko/20100101 Firefox/115.0"
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
    BASE_URL = "https://old.reddit.com"

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
                    logger.info(f"Reddit RSS r/{subreddit}: {len(posts)} posts")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error fetching r/{subreddit}: {e}")

        all_posts.sort(key=lambda p: p.created_at, reverse=True)
        return all_posts[:120]

    async def _fetch_rss(self, session: aiohttp.ClientSession, subreddit: str) -> List[RedditRSSPost]:
        url = f"{self.BASE_URL}/r/{subreddit}/hot.rss"
        async with session.get(url) as resp:
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
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            else:
                published = datetime.now(tz=timezone.utc)

            url = entry.get("link", "")
            post_id = url.split("/")[-3] if "/comments/" in url else entry.get("id", url)

            text = entry.get("summary", entry.get("description", ""))
            text = re.sub(r"<[^>]+>", "", text).strip()[:500]

            author = getattr(entry, "author", "unknown")

            return RedditRSSPost(
                id=post_id,
                title=entry.get("title", ""),
                text=text,
                author=author,
                subreddit=subreddit,
                url=url,
                score=0,          # RSS doesn't expose score reliably
                num_comments=0,
                created_at=published,
                permalink=url,
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
