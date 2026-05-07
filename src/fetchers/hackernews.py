import aiohttp
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class HackerNewsStory:
    id: int
    title: str
    url: Optional[str]
    text: Optional[str]
    author: str
    points: int
    num_comments: int
    created_at: datetime
    story_type: str  # "story", "job", etc.

    @property
    def permalink(self) -> str:
        return f"https://news.ycombinator.com/item?id={self.id}"

class HackerNewsFetcher:
    def __init__(self):
        self.base_url = "https://hacker-news.firebaseio.com/v0"

    async def fetch_top_stories(self, limit: int = 100) -> List[HackerNewsStory]:
        """Fetch top stories from Hacker News"""
        async with aiohttp.ClientSession() as session:
            # Get top story IDs
            top_stories_url = f"{self.base_url}/topstories.json"

            async with session.get(top_stories_url) as response:
                if response.status != 200:
                    logger.error(f"Hacker News API error: {response.status}")
                    return []

                story_ids = await response.json()
                story_ids = story_ids[:limit]  # Limit to top N stories

            # Fetch individual stories
            stories = []
            for story_id in story_ids:
                try:
                    story = await self._fetch_story(session, story_id)
                    if story and self._is_ai_related(story.title):
                        stories.append(story)

                    # Rate limiting
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Error fetching story {story_id}: {e}")

            return stories

    async def _fetch_story(self, session: aiohttp.ClientSession, story_id: int) -> Optional[HackerNewsStory]:
        """Fetch a single story by ID"""
        story_url = f"{self.base_url}/item/{story_id}.json"

        async with session.get(story_url) as response:
            if response.status != 200:
                return None

            data = await response.json()

            if not data or data.get("type") != "story":
                return None

            # Filter by minimum points
            if data.get("score", 0) < 10:
                return None

            return HackerNewsStory(
                id=data["id"],
                title=data.get("title", ""),
                url=data.get("url"),
                text=data.get("text"),
                author=data.get("by", "unknown"),
                points=data.get("score", 0),
                num_comments=data.get("descendants", 0),
                created_at=datetime.fromtimestamp(data.get("time", 0)),
                story_type=data.get("type", "story")
            )

    def _is_ai_related(self, title: str) -> bool:
        """Check if story is AI-related"""
        ai_keywords = [
            "artificial intelligence", "machine learning", "deep learning",
            "neural network", "transformer", "gpt", "llm", "large language model",
            "generative ai", "agi", "natural language processing", "computer vision",
            "reinforcement learning", "supervised learning", "unsupervised learning",
            "fine-tuning", "prompt engineering", "token", "embedding", "latent",
            "diffusion", "gan", "vae", "bert", "t5", "palm", "claude", "chatgpt",
            "agent", "autonomous", "rlhf", "sft", "pre-training", "foundation model",
            "ai", "ml", "openai", "anthropic", "google ai", "meta ai", "deepmind",
            # AI infrastructure — datacenter, compute, chips, energy
            "datacenter", "data center", "gpu cluster", "compute cluster",
            "training cluster", "hyperscaler", "stargate",
            "blackwell", "hopper", "h100", "h200", "b200", "gb200",
            "tsmc", "foundry", "wafer",
            "gigawatt", "power grid", "nuclear power",
            "ai infrastructure", "ai infra", "coreweave",
        ]

        title_lower = title.lower()
        return any(keyword in title_lower for keyword in ai_keywords)

    async def search_stories(self, query: str, limit: int = 50) -> List[HackerNewsStory]:
        """Search for specific AI-related stories"""
        # HN Search API (third-party)
        search_url = "https://hn.algolia.com/api/v1/search"

        params = {
            "query": query,
            "tags": "story",
            "numericFilters": "created_at_i>" + str(int((datetime.now() - timedelta(days=7)).timestamp())),
            "hitsPerPage": limit
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Hacker News search error: {response.status}")
                    return []

                data = await response.json()

                stories = []
                for hit in data.get("hits", []):
                    story = HackerNewsStory(
                        id=int(hit["objectID"]),
                        title=hit.get("title", ""),
                        url=hit.get("url"),
                        text=hit.get("comment_text", ""),
                        author=hit.get("author", "unknown"),
                        points=hit.get("points", 0),
                        num_comments=hit.get("num_comments", 0),
                        created_at=datetime.fromtimestamp(hit.get("created_at_i", 0)),
                        story_type="story"
                    )
                    stories.append(story)

                return stories

    async def fetch_new_stories(self, limit: int = 100) -> List[HackerNewsStory]:
        """Fetch newest stories"""
        async with aiohttp.ClientSession() as session:
            # Get new story IDs
            new_stories_url = f"{self.base_url}/newstories.json"

            async with session.get(new_stories_url) as response:
                if response.status != 200:
                    logger.error(f"Hacker News API error: {response.status}")
                    return []

                story_ids = await response.json()
                story_ids = story_ids[:limit]

            # Fetch individual stories
            stories = []
            for story_id in story_ids:
                try:
                    story = await self._fetch_story(session, story_id)
                    if story and self._is_ai_related(story.title):
                        stories.append(story)

                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Error fetching story {story_id}: {e}")

            # Sort by date (newest first)
            stories.sort(key=lambda x: x.created_at, reverse=True)

            return stories

    async def fetch_show_hn_stories(self, limit: int = 50) -> List[HackerNewsStory]:
        """Fetch Show HN stories (people showing their projects)"""
        async with aiohttp.ClientSession() as session:
            # Get Show HN story IDs
            show_hn_url = f"{self.base_url}/showstories.json"

            async with session.get(show_hn_url) as response:
                if response.status != 200:
                    logger.error(f"Hacker News API error: {response.status}")
                    return []

                story_ids = await response.json()
                story_ids = story_ids[:limit]

            # Fetch individual stories
            stories = []
            for story_id in story_ids:
                try:
                    story = await self._fetch_story(session, story_id)
                    if story and self._is_ai_related(story.title):
                        stories.append(story)

                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Error fetching story {story_id}: {e}")

            return stories