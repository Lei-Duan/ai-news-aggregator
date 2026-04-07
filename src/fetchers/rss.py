import asyncio
import aiohttp
import feedparser
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RSSItem:
    title: str
    link: str
    description: str
    published: datetime
    author: Optional[str]
    tags: List[str]
    source: str
    content: Optional[str]

class RSSFetcher:
    def __init__(self):
        self.timeout = 30  # seconds

    async def fetch_feeds(self, feed_urls: List[str]) -> List[RSSItem]:
        """Fetch and parse multiple RSS feeds"""
        all_items = []

        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_single_feed(session, url) for url in feed_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(feed_urls, results):
                if isinstance(result, Exception):
                    logger.error(f"Error fetching feed {url}: {result}")
                else:
                    all_items.extend(result)
                    logger.info(f"Fetched {len(result)} items from {url}")

        # Sort by published date (newest first)
        all_items.sort(key=lambda x: x.published, reverse=True)

        return all_items[:200]  # Limit total items

    async def _fetch_single_feed(self, session: aiohttp.ClientSession, feed_url: str) -> List[RSSItem]:
        """Fetch and parse a single RSS feed"""
        try:
            async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
                if response.status != 200:
                    logger.error(f"RSS feed error {response.status}: {feed_url}")
                    return []

                content = await response.text()

                # Parse feed in executor to avoid blocking
                loop = asyncio.get_event_loop()
                feed = await loop.run_in_executor(None, feedparser.parse, content)

                if feed.bozo:
                    logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")

                items = []
                for entry in feed.entries:
                    try:
                        item = self._parse_entry(entry, feed_url)
                        if item and self._is_ai_related(item):
                            items.append(item)
                    except Exception as e:
                        logger.error(f"Error parsing entry: {e}")
                        continue

                return items

        except Exception as e:
            logger.error(f"Error fetching feed {feed_url}: {e}")
            return []

    def _parse_entry(self, entry: Dict, feed_url: str) -> Optional[RSSItem]:
        """Parse a single RSS entry"""
        try:
            # Get published date
            published = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6])
            else:
                # Use current time as fallback
                published = datetime.now()

            # Filter by date (last 7 days)
            if published < datetime.now() - timedelta(days=7):
                return None

            # Get content
            content = None
            if hasattr(entry, 'content'):
                content = entry.content[0].value if entry.content else None
            elif hasattr(entry, 'description'):
                content = entry.description
            elif hasattr(entry, 'summary'):
                content = entry.summary

            # Get tags/categories
            tags = []
            if hasattr(entry, 'tags'):
                tags = [tag.term for tag in entry.tags if hasattr(tag, 'term')]

            return RSSItem(
                title=entry.get('title', 'No Title'),
                link=entry.get('link', ''),
                description=entry.get('description', ''),
                published=published,
                author=entry.get('author'),
                tags=tags,
                source=feed_url,
                content=content
            )

        except Exception as e:
            logger.error(f"Error parsing RSS entry: {e}")
            return None

    def _is_ai_related(self, item: RSSItem) -> bool:
        """Check if RSS item is AI-related"""
        ai_keywords = [
            "artificial intelligence", "machine learning", "deep learning",
            "neural network", "transformer", "gpt", "llm", "large language model",
            "generative ai", "agi", "natural language processing", "computer vision",
            "reinforcement learning", "supervised learning", "unsupervised learning",
            "fine-tuning", "prompt engineering", "token", "embedding", "latent",
            "diffusion", "gan", "vae", "bert", "t5", "palm", "claude", "chatgpt",
            "agent", "autonomous", "rlhf", "sft", "pre-training", "foundation model",
            "ai", "ml", "openai", "anthropic", "google ai", "meta ai", "deepmind",
            "huggingface", "stability ai", "midjourney", "runway", "cohere"
        ]

        # Combine title, description and tags
        text = f"{item.title} {item.description} {' '.join(item.tags)}".lower()

        return any(keyword in text for keyword in ai_keywords)

    async def fetch_specific_blog(self, blog_url: str, blog_name: str) -> List[RSSItem]:
        """Fetch posts from a specific AI blog"""
        # Try common RSS feed paths
        feed_paths = [
            "/rss",
            "/feed",
            "/rss.xml",
            "/feed.xml",
            "/blog/rss",
            "/blog/feed",
            "/index.xml",
            "/atom.xml"
        ]

        # Try to find RSS feed
        for path in feed_paths:
            feed_url = blog_url.rstrip('/') + path
            items = await self.fetch_feeds([feed_url])
            if items:
                logger.info(f"Found RSS feed for {blog_name}: {feed_url}")
                return items

        logger.warning(f"No RSS feed found for {blog_name}")
        return []

    def get_ai_blog_feeds(self) -> Dict[str, str]:
        """Get known AI blog RSS feeds"""
        return {
            "OpenAI Blog": "https://openai.com/blog/rss.xml",
            "Anthropic News": "https://www.anthropic.com/news/rss.xml",
            "Google AI Blog": "https://ai.googleblog.com/feeds/posts/default",
            "Google Research Blog": "https://blog.research.google/feeds/posts/default",
            "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
            "Stability AI Blog": "https://stability.ai/news?format=rss",
            "DeepMind Blog": "https://deepmind.com/blog?format=rss",
            "Microsoft Research Blog": "https://www.microsoft.com/en-us/research/blog/feed/",
            "Meta AI Blog": "https://ai.facebook.com/blog/rss/",
            "Distill Publications": "https://distill.pub/rss.xml",
            "Weights & Biases Blog": "https://wandb.ai/feed/rss",
            "Papers with Code": "https://paperswithcode.com/rss"
        }