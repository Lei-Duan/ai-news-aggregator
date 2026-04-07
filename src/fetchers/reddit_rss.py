import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timezone
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

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
    """Fetch Reddit content via JSON API - No API key required, returns real score data."""

    BASE_URL = "https://www.reddit.com"
    HEADERS = {"User-Agent": "AI-News-Aggregator/1.0 (research project)"}

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def fetch_subreddit_feeds(self, subreddits: List[str], sort_by: str = "hot") -> List[RedditRSSPost]:
        """Fetch top-of-day posts from multiple subreddits via JSON API."""
        all_posts = []

        async with aiohttp.ClientSession(headers=self.HEADERS, timeout=self.timeout) as session:
            for subreddit in subreddits:
                try:
                    posts = await self._fetch_subreddit_json(session, subreddit)
                    all_posts.extend(posts)
                    logger.info(f"Fetched {len(posts)} posts from r/{subreddit}")
                    await asyncio.sleep(1)  # polite rate limiting
                except Exception as e:
                    logger.error(f"Error fetching r/{subreddit}: {e}")

        # Sort by score descending
        all_posts.sort(key=lambda x: x.score, reverse=True)
        return all_posts[:100]

    async def _fetch_subreddit_json(self, session: aiohttp.ClientSession, subreddit: str) -> List[RedditRSSPost]:
        """Fetch today's top posts from a subreddit using the JSON API."""
        url = f"{self.BASE_URL}/r/{subreddit}/top.json"
        params = {"limit": 25, "t": "day"}

        async with session.get(url, params=params) as response:
            if response.status == 429:
                logger.warning(f"Rate limited on r/{subreddit}, skipping")
                return []
            if response.status != 200:
                logger.error(f"Reddit JSON error {response.status} for r/{subreddit}")
                return []

            data = await response.json()
            posts = []
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                try:
                    parsed = self._parse_post(post, subreddit)
                    if parsed and self._is_ai_or_builder_related(parsed.title + " " + parsed.text):
                        posts.append(parsed)
                except Exception as e:
                    logger.error(f"Error parsing post: {e}")
            return posts

    def _parse_post(self, post: Dict, subreddit: str) -> Optional[RedditRSSPost]:
        created_utc = post.get("created_utc", 0)
        created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc) if created_utc else datetime.now(tz=timezone.utc)

        # selftext for text posts; for link posts use the title as text
        text = post.get("selftext", "").strip()
        if not text or text == "[removed]" or text == "[deleted]":
            text = post.get("title", "")

        permalink = post.get("permalink", "")
        if permalink:
            permalink = f"https://www.reddit.com{permalink}"

        return RedditRSSPost(
            id=post.get("id", ""),
            title=post.get("title", ""),
            text=text[:500],  # cap text length
            author=post.get("author", "unknown"),
            subreddit=post.get("subreddit", subreddit),
            url=post.get("url", permalink),
            score=post.get("score", 0),
            num_comments=post.get("num_comments", 0),
            created_at=created_at,
            permalink=permalink,
            flair=post.get("link_flair_text"),
            upvote_ratio=post.get("upvote_ratio", 0.0),
        )

    def _is_ai_or_builder_related(self, text: str) -> bool:
        """Check if post is relevant to AI or indie builder community."""
        keywords = [
            # AI / ML
            "ai", "llm", "gpt", "claude", "gemini", "llama", "mistral", "openai",
            "anthropic", "huggingface", "deepseek", "agent", "chatbot", "ml",
            "machine learning", "deep learning", "neural", "transformer", "diffusion",
            "fine-tun", "rag", "embedding", "inference", "model", "generative",
            # Builder community
            "build in public", "buildinpublic", "indie hacker", "indiehacker",
            "side project", "saas", "mrr", "arr", "startup", "solo founder",
            "ship", "launch", "product hunt", "vibe coding", "cursor", "windsurf",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    async def fetch_combined_feed(self, subreddits: List[str], keywords: List[str] = None) -> List[RedditRSSPost]:
        """Fetch and optionally filter posts by keywords."""
        posts = await self.fetch_subreddit_feeds(subreddits)

        if keywords:
            filtered = []
            for post in posts:
                text = (post.title + " " + post.text).lower()
                if any(kw.lower() in text for kw in keywords):
                    filtered.append(post)
            return filtered

        return posts

    async def fetch_user_feed(self, username: str) -> List[RedditRSSPost]:
        """Fetch recent posts from a specific Reddit user."""
        url = f"{self.BASE_URL}/user/{username}/submitted.json"
        params = {"limit": 25, "sort": "new"}

        async with aiohttp.ClientSession(headers=self.HEADERS, timeout=self.timeout) as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Reddit user posts error {response.status} for u/{username}")
                    return []
                data = await response.json()
                posts = []
                for child in data.get("data", {}).get("children", []):
                    if child.get("kind") != "t3":
                        continue
                    try:
                        parsed = self._parse_post(child["data"], f"u/{username}")
                        if parsed:
                            posts.append(parsed)
                    except Exception as e:
                        logger.error(f"Error parsing user post: {e}")
                return posts
