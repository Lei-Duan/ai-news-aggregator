import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RedditPost:
    id: str
    title: str
    text: str
    author: str
    subreddit: str
    url: str
    score: int
    num_comments: int
    created_utc: datetime
    permalink: str
    flair: Optional[str]
    upvote_ratio: float

class RedditFetcher:
    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.base_url = "https://oauth.reddit.com"
        self.token_url = "https://www.reddit.com/api/v1/access_token"
        self.access_token = None

    async def _get_access_token(self) -> str:
        """Get Reddit API access token"""
        if self.access_token:
            return self.access_token

        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)

        async with aiohttp.ClientSession() as session:
            data = {
                "grant_type": "client_credentials"
            }

            headers = {"User-Agent": self.user_agent}

            async with session.post(
                self.token_url,
                auth=auth,
                data=data,
                headers=headers
            ) as response:
                if response.status != 200:
                    logger.error(f"Reddit auth error: {response.status}")
                    raise Exception(f"Failed to get Reddit token: {response.status}")

                token_data = await response.json()
                self.access_token = token_data["access_token"]
                return self.access_token

    async def fetch_hot_posts(self, subreddits: List[str], min_score: int = 50) -> List[RedditPost]:
        """Fetch hot posts from specified subreddits"""
        posts = []

        # Get access token
        token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.user_agent
        }

        async with aiohttp.ClientSession() as session:
            for subreddit in subreddits:
                try:
                    subreddit_posts = await self._fetch_subreddit_posts(
                        session, subreddit, headers, min_score
                    )
                    posts.extend(subreddit_posts)
                    logger.info(f"Fetched {len(subreddit_posts)} posts from r/{subreddit}")

                    # Rate limiting
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Error fetching from r/{subreddit}: {e}")

        return posts

    async def _fetch_subreddit_posts(self, session: aiohttp.ClientSession,
                                   subreddit: str, headers: Dict, min_score: int) -> List[RedditPost]:
        """Fetch posts from a specific subreddit"""
        url = f"{self.base_url}/r/{subreddit}/hot"

        params = {
            "limit": 100,
            "t": "day"  # Last 24 hours
        }

        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                logger.error(f"Reddit API error for r/{subreddit}: {response.status}")
                return []

            data = await response.json()

            posts = []
            for post_data in data["data"]["children"]:
                post = post_data["data"]

                # Filter by score
                if post["score"] < min_score:
                    continue

                # Filter AI-related posts
                if not self._is_ai_related(post["title"] + " " + post.get("selftext", "")):
                    continue

                reddit_post = RedditPost(
                    id=post["id"],
                    title=post["title"],
                    text=post.get("selftext", ""),
                    author=post["author"],
                    subreddit=post["subreddit"],
                    url=post["url"],
                    score=post["score"],
                    num_comments=post["num_comments"],
                    created_utc=datetime.fromtimestamp(post["created_utc"]),
                    permalink=f"https://reddit.com{post['permalink']}",
                    flair=post.get("link_flair_text"),
                    upvote_ratio=post["upvote_ratio"]
                )

                posts.append(reddit_post)

            return posts

    def _is_ai_related(self, text: str) -> bool:
        """Check if post is AI-related"""
        ai_keywords = [
            "artificial intelligence", "machine learning", "deep learning",
            "neural network", "transformer", "gpt", "llm", "large language model",
            "generative ai", "agi", "natural language processing", "computer vision",
            "reinforcement learning", "supervised learning", "unsupervised learning",
            "fine-tuning", "prompt engineering", "token", "embedding", "latent",
            "diffusion", "gan", "vae", "bert", "t5", "palm", "claude", "chatgpt",
            "agent", "autonomous", "rlhf", "sft", "pre-training", "foundation model"
        ]

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in ai_keywords)

    async def search_posts(self, query: str, subreddits: List[str],
                          sort: str = "relevance", time_filter: str = "week") -> List[RedditPost]:
        """Search for specific AI-related posts"""
        posts = []
        token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.user_agent
        }

        async with aiohttp.ClientSession() as session:
            for subreddit in subreddits:
                try:
                    search_results = await self._search_subreddit(
                        session, subreddit, query, headers, sort, time_filter
                    )
                    posts.extend(search_results)
                    logger.info(f"Found {len(search_results)} search results in r/{subreddit}")

                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Error searching r/{subreddit}: {e}")

        return posts

    async def _search_subreddit(self, session: aiohttp.ClientSession,
                              subreddit: str, query: str, headers: Dict,
                              sort: str, time_filter: str) -> List[RedditPost]:
        """Search within a specific subreddit"""
        url = f"{self.base_url}/r/{subreddit}/search"

        params = {
            "q": query,
            "restrict_sr": "true",
            "sort": sort,
            "t": time_filter,
            "limit": 50
        }

        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                logger.error(f"Reddit search error: {response.status}")
                return []

            data = await response.json()

            posts = []
            for post_data in data["data"]["children"]:
                post = post_data["data"]

                reddit_post = RedditPost(
                    id=post["id"],
                    title=post["title"],
                    text=post.get("selftext", ""),
                    author=post["author"],
                    subreddit=post["subreddit"],
                    url=post["url"],
                    score=post["score"],
                    num_comments=post["num_comments"],
                    created_utc=datetime.fromtimestamp(post["created_utc"]),
                    permalink=f"https://reddit.com{post['permalink']}",
                    flair=post.get("link_flair_text"),
                    upvote_ratio=post["upvote_ratio"]
                )

                posts.append(reddit_post)

            return posts

    async def fetch_user_posts(self, username: str, limit: int = 50) -> List[RedditPost]:
        """Fetch posts from a specific user"""
        token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.user_agent
        }

        url = f"{self.base_url}/user/{username}/submitted"

        async with aiohttp.ClientSession() as session:
            params = {"limit": limit}

            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    logger.error(f"Reddit user posts error: {response.status}")
                    return []

                data = await response.json()

                posts = []
                for post_data in data["data"]["children"]:
                    post = post_data["data"]

                    # Only include posts (not comments)
                    if post_data["kind"] != "t3":
                        continue

                    reddit_post = RedditPost(
                        id=post["id"],
                        title=post["title"],
                        text=post.get("selftext", ""),
                        author=post["author"],
                        subreddit=post["subreddit"],
                        url=post["url"],
                        score=post["score"],
                        num_comments=post["num_comments"],
                        created_utc=datetime.fromtimestamp(post["created_utc"]),
                        permalink=f"https://reddit.com{post['permalink']}",
                        flair=post.get("link_flair_text"),
                        upvote_ratio=post["upvote_ratio"]
                    )

                    posts.append(reddit_post)

                return posts