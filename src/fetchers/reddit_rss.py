"""
Reddit fetcher via JSON API (no auth required).
Uses /r/{subreddit}/hot.json which includes real score and comment counts.
"""

import asyncio
import aiohttp
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

JSON_USER_AGENT = "ai-news-aggregator/1.0 (by /u/ai-aggregator-bot)"


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
            headers={"User-Agent": JSON_USER_AGENT},
            timeout=self.timeout,
        ) as session:
            for subreddit in subreddits:
                try:
                    posts = await self._fetch_json(session, subreddit)
                    all_posts.extend(posts)
                    logger.info(f"Reddit r/{subreddit}: {len(posts)} posts")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error fetching r/{subreddit}: {e}")

        all_posts.sort(key=lambda p: p.num_comments, reverse=True)
        return all_posts[:120]

    async def _fetch_json(self, session: aiohttp.ClientSession, subreddit: str) -> List[RedditRSSPost]:
        url = f"{self.BASE_URL}/r/{subreddit}/hot.json?limit=25"
        async with session.get(url) as resp:
            if resp.status == 429:
                logger.warning(f"Reddit rate limit on r/{subreddit}, skipping")
                return []
            if resp.status != 200:
                logger.error(f"Reddit JSON {resp.status}: r/{subreddit}")
                return []
            data = await resp.json()

        posts = []
        for child in data.get("data", {}).get("children", []):
            post = self._parse_post(child.get("data", {}), subreddit)
            if post and self._is_relevant(post.title + " " + post.text):
                posts.append(post)
        return posts

    def _parse_post(self, d: dict, subreddit: str) -> Optional[RedditRSSPost]:
        try:
            # Skip stickied mod posts
            if d.get("stickied") or d.get("distinguished") == "moderator":
                return None

            created_utc = d.get("created_utc", 0)
            created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)

            # Self-text or empty for link posts
            text = d.get("selftext", "") or ""
            text = re.sub(r"\s+", " ", text).strip()[:500]

            permalink = "https://www.reddit.com" + d.get("permalink", "")
            url = d.get("url", permalink)

            return RedditRSSPost(
                id=d.get("id", ""),
                title=d.get("title", ""),
                text=text,
                author=d.get("author", "unknown"),
                subreddit=subreddit,
                url=url,
                score=d.get("score", 0),
                num_comments=d.get("num_comments", 0),
                created_at=created_at,
                permalink=permalink,
                flair=d.get("link_flair_text"),
                upvote_ratio=d.get("upvote_ratio", 0.0),
            )
        except Exception as e:
            logger.error(f"Error parsing Reddit post: {e}")
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
