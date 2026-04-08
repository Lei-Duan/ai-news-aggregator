import asyncio
import logging
from datetime import datetime
from typing import Dict, List
import yaml

from src.fetchers.twitter import TwitterFetcher
from src.fetchers.github import GitHubFetcher
from src.fetchers.reddit_rss import RedditRSSFetcher
from src.fetchers.hackernews import HackerNewsFetcher
from src.fetchers.rss import RSSFetcher
from src.fetchers.podcast import PodcastFetcher
from src.fetchers.blog import BlogFetcher

from src.processors.summarizer import ContentSummarizer
from src.processors.classifier import ContentClassifier
from src.processors.filter import ContentFilter
from src.processors.state import SeenItemsState
from src.scheduler.basic_processor import BasicContentProcessor

from src.notion.client import NotionClient
from config.settings import settings

logger = logging.getLogger(__name__)


class DailyBriefingJob:
    def __init__(self):
        self.setup_logging()
        self.load_sources()
        self.initialize_clients()
        self.state = SeenItemsState()

    def setup_logging(self):
        logging.basicConfig(
            level=getattr(logging, settings.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(settings.log_file),
                logging.StreamHandler()
            ]
        )

    def load_sources(self):
        with open('config/sources.yaml', 'r') as f:
            self.sources = yaml.safe_load(f)

    def initialize_clients(self):
        self.twitter_fetcher = TwitterFetcher(bearer_token=settings.twitter_bearer_token)
        self.github_fetcher = GitHubFetcher(token=settings.github_token)
        self.reddit_fetcher = RedditRSSFetcher()
        self.hackernews_fetcher = HackerNewsFetcher()
        self.rss_fetcher = RSSFetcher()

        self.podcast_fetcher = PodcastFetcher()
        self.blog_fetcher = BlogFetcher(max_age_hours=72)

        self.summarizer = ContentSummarizer(anthropic_api_key=settings.anthropic_api_key)
        self.classifier = ContentClassifier()
        self.filter = ContentFilter()

        self.notion_client = NotionClient(
            token=settings.notion_token,
            database_id=settings.notion_database_id
        )
        logger.info("All clients initialized")

    # ------------------------------------------------------------------ #
    # Main workflow
    # ------------------------------------------------------------------ #

    async def run_daily_briefing(self):
        logger.info("Starting daily AI briefing generation...")
        self.state.load()

        try:
            logger.info("Fetching content from all sources...")
            raw_content = await self.fetch_all_content()

            logger.info("Deduplicating against seen-items state...")
            raw_content = self.deduplicate(raw_content)

            logger.info("Pre-filtering content before AI summarization...")
            raw_content = self.pre_filter_content(raw_content)

            logger.info("Processing and summarizing content...")
            processed_content = await self.process_content(raw_content)

            logger.info("Filtering and categorizing content...")
            categorized_content = self.categorize_and_filter(processed_content)

            logger.info("Creating Notion page...")
            page_id = await self.create_notion_page(categorized_content)

            # Mark all fetched items as seen AFTER successful Notion publish
            self._mark_all_seen(raw_content)
            self.state.save()

            logger.info(f"Daily briefing completed! Notion page: {page_id}")
            return page_id

        except Exception as e:
            logger.error(f"Error in daily briefing: {e}", exc_info=True)
            self.state.save()   # save whatever we have
            raise

    def deduplicate(self, raw_content: Dict[str, List]) -> Dict[str, List]:
        """Filter out items we've already processed in a previous run."""
        source_map = {
            "twitter":    ("tweets",     "id"),
            "github":     ("github",     "id"),
            "reddit":     ("reddit",     "id"),
            "hackernews": ("hackernews", "id"),
            "rss":        ("rss",        "url"),
            "podcasts":   ("podcasts",   "id"),
            "blogs":      ("blogs",      "url"),
        }
        deduped = {}
        for key, items in raw_content.items():
            state_source, id_field = source_map.get(key, (key, "id"))
            deduped[key] = self.state.filter_unseen(items, state_source, id_field)
        return deduped

    def _mark_all_seen(self, raw_content: Dict[str, List]):
        """Mark every item in raw_content as seen."""
        source_map = {
            "twitter":    ("tweets",     "id"),
            "github":     ("github",     "id"),
            "reddit":     ("reddit",     "id"),
            "hackernews": ("hackernews", "id"),
            "rss":        ("rss",        "url"),
            "podcasts":   ("podcasts",   "id"),
            "blogs":      ("blogs",      "url"),
        }
        for key, items in raw_content.items():
            state_source, id_field = source_map.get(key, (key, "id"))
            self.state.mark_seen_batch(items, state_source, id_field)

    # ------------------------------------------------------------------ #
    # Fetchers
    # ------------------------------------------------------------------ #

    async def fetch_all_content(self) -> Dict[str, List]:
        content = {}

        logger.info("Fetching Twitter content...")
        content["twitter"] = await self.fetch_twitter_content()

        logger.info("Fetching GitHub content...")
        content["github"] = await self.fetch_github_content()

        logger.info("Fetching Reddit content...")
        content["reddit"] = await self.fetch_reddit_content()

        logger.info("Fetching Hacker News content...")
        content["hackernews"] = await self.fetch_hackernews_content()

        logger.info("Fetching RSS content...")
        content["rss"] = await self.fetch_rss_content()

        logger.info("Fetching podcast episodes...")
        content["podcasts"] = await self.fetch_podcast_content()

        logger.info("Fetching tech blog posts...")
        content["blogs"] = await self.fetch_blog_content()

        for source, items in content.items():
            logger.info(f"  Raw [{source}]: {len(items)} items")

        return content

    async def fetch_twitter_content(self) -> List[Dict]:
        if not settings.twitter_bearer_token:
            logger.info("Twitter: no Bearer Token, skipping")
            return []

        # 1) Followed builder accounts (batch lookup)
        account_tweets = await self.twitter_fetcher.fetch_tweets_from_accounts(
            accounts=self.sources["twitter"]["ai_accounts"],
            keywords=self.sources["twitter"]["keywords"],
            hours_back=24,
        )
        logger.info(f"Twitter accounts: {len(account_tweets)} tweets")

        # 2) Trending AI search — high-engagement tweets beyond followed accounts
        trending_tweets = await self.twitter_fetcher.search_trending(
            min_likes=2000,
            hours_back=24,
        )
        logger.info(f"Twitter trending: {len(trending_tweets)} tweets")

        # Merge and deduplicate by tweet ID
        seen_ids = set()
        merged = []
        for t in account_tweets + trending_tweets:
            if t.id not in seen_ids:
                seen_ids.add(t.id)
                merged.append(t)

        # Sort by likes descending
        merged.sort(key=lambda t: t.like_count, reverse=True)
        logger.info(f"Twitter total after merge: {len(merged)} tweets")

        return [
            {
                "type": "tweet",
                "id": t.id,
                "title": f"Tweet by @{t.author_username}",
                "text": t.text,
                "author": t.author_name,
                "author_bio": t.author_bio,
                "source": f"@{t.author_username}",
                "url": t.url,
                "published_at": t.created_at,
                "is_long": t.is_long,
                "engagement": {
                    "retweets": t.retweet_count,
                    "likes": t.like_count,
                    "replies": t.reply_count,
                },
            }
            for t in merged
        ]

    async def fetch_github_content(self) -> List[Dict]:
        trending_repos = await self.github_fetcher.fetch_trending_repos(
            topics=self.sources["github"]["topics"],
            language=None,
            created_after_days=30,
        )
        viral_repos = await self.github_fetcher.fetch_recently_starred(
            min_stars=200, created_after_days=14
        )
        seen = {}
        for repo in trending_repos + viral_repos:
            if repo.full_name not in seen:
                seen[repo.full_name] = repo
        all_repos = sorted(seen.values(), key=lambda r: r.star_velocity, reverse=True)

        return [
            {
                "type": "github",
                "id": repo.full_name,
                "title": repo.full_name,
                "text": f"{repo.description or repo.name} [⭐ {repo.stars} stars, {repo.star_velocity:.1f} stars/day]",
                "author": repo.owner,
                "source": "GitHub",
                "url": repo.url,
                "published_at": repo.created_at,
                "engagement": {"stars": repo.stars, "forks": repo.forks},
                "star_velocity": repo.star_velocity,
                "topics": repo.topics,
                "language": repo.language,
            }
            for repo in all_repos
        ]

    async def fetch_reddit_content(self) -> List[Dict]:
        posts = await self.reddit_fetcher.fetch_combined_feed(
            subreddits=self.sources["reddit"]["subreddits"],
            keywords=self.sources["reddit"].get("keywords", []),
        )
        return [
            {
                "type": "reddit",
                "id": post.id,
                "title": post.title,
                "text": post.text or post.title,
                "author": post.author,
                "source": f"r/{post.subreddit}",
                "url": post.url,
                "permalink": post.permalink,
                "published_at": post.created_at,
                "engagement": {
                    "score": post.score,
                    "comments": post.num_comments,
                    "upvote_ratio": post.upvote_ratio,
                },
                "flair": post.flair,
                "subreddit": post.subreddit,
            }
            for post in posts
        ]

    async def fetch_hackernews_content(self) -> List[Dict]:
        stories = await self.hackernews_fetcher.fetch_top_stories(limit=50)
        return [
            {
                "type": "hackernews",
                "id": str(story.id),
                "title": story.title,
                "text": story.text or story.title,
                "author": story.author,
                "source": "Hacker News",
                "url": story.url or story.permalink,
                "permalink": story.permalink,
                "published_at": story.created_at,
                "engagement": {"points": story.points, "comments": story.num_comments},
                "story_type": story.story_type,
            }
            for story in stories
        ]

    async def fetch_rss_content(self) -> List[Dict]:
        feed_urls = self.sources.get("rss_feeds", [])
        items = await self.rss_fetcher.fetch_feeds(feed_urls)
        return [
            {
                "type": "rss",
                "id": item.link or item.title,
                "url": item.link,
                "title": item.title,
                "text": item.description or item.content or item.title,
                "author": item.author or "Unknown",
                "source": item.source,
                "published_at": item.published,
                "engagement": {},
                "tags": item.tags,
            }
            for item in items
        ]

    async def fetch_podcast_content(self) -> List[Dict]:
        rss_feeds = self.sources.get("podcasts", {}).get("rss_feeds", [])
        if not rss_feeds:
            return []
        episodes = await self.podcast_fetcher.fetch_recent_episodes(
            rss_feeds=rss_feeds,
            max_age_hours=72,
            max_per_podcast=2,
        )
        return [
            {
                "type": "podcast",
                "id": ep.guid,
                "title": ep.title,
                "text": ep.transcript or ep.description,
                "author": ep.podcast_name,
                "source": ep.podcast_name,
                "url": ep.episode_url,
                "published_at": ep.published_at,
                "engagement": {},
                "has_transcript": ep.transcript is not None,
                "duration_sec": ep.duration_sec,
            }
            for ep in episodes
        ]

    async def fetch_blog_content(self) -> List[Dict]:
        posts = await self.blog_fetcher.fetch_all()
        return [
            {
                "type": "blog",
                "id": post.url,
                "url": post.url,
                "title": post.title,
                "text": post.content,
                "author": post.author,
                "source": post.source,
                "published_at": post.published_at,
                "engagement": {},
            }
            for post in posts
        ]

    # ------------------------------------------------------------------ #
    # Pre-filter (keyword gating before AI summarization)
    # ------------------------------------------------------------------ #

    def pre_filter_content(self, raw_content: Dict[str, List]) -> Dict[str, List]:
        AI_KEYWORDS = [
            "ai", "llm", "gpt", "claude", "gemini", "llama", "mistral",
            "machine learning", "deep learning", "neural", "transformer",
            "openai", "anthropic", "agent", "chatbot", "embedding",
            "fine-tun", "rag", "inference", "model", "diffusion",
            "build in public", "indie hacker", "saas", "startup",
        ]
        EXCLUDE = ["crypto", "nft", "blockchain", "bitcoin", "ethereum"]

        def is_relevant(item: Dict) -> bool:
            text = " ".join([
                item.get("title", ""), item.get("text", ""),
                item.get("description", ""), item.get("source", ""),
            ]).lower()
            if any(kw in text for kw in EXCLUDE):
                return False
            # Blogs and podcasts are pre-selected sources — always include
            if item.get("type") in ("blog", "podcast"):
                return True
            return any(kw in text for kw in AI_KEYWORDS)

        LIMITS = {
            "twitter": 20, "github": 15, "hackernews": 20,
            "reddit": 15, "rss": 10, "podcasts": 6, "blogs": 6,
        }

        filtered = {}
        for source, items in raw_content.items():
            items = self.filter.filter_by_date(items, days=3 if source in ("podcasts", "blogs") else 1)
            items = [i for i in items if is_relevant(i)]
            items = items[:LIMITS.get(source, 10)]
            filtered[source] = items
            logger.info(f"Pre-filter [{source}]: {len(raw_content[source])} → {len(items)}")

        return filtered

    # ------------------------------------------------------------------ #
    # AI summarization
    # ------------------------------------------------------------------ #

    async def process_content(self, raw_content: Dict[str, List]) -> List[Dict]:
        all_items = []

        type_map = {
            "twitter":    "tweet",
            "github":     "github",
            "reddit":     "article",
            "hackernews": "article",
            "rss":        "article",
            "podcasts":   "article",
            "blogs":      "article",
        }

        for source_type, items in raw_content.items():
            if not items:
                continue
            content_type = type_map.get(source_type, "article")

            batch_items = []
            for item in items:
                if source_type == "github":
                    batch_items.append({
                        "name": item["title"],
                        "description": item["text"],
                        "stars": item["engagement"]["stars"],
                        "topics": item.get("topics", []),
                        "recent_commits": [],
                    })
                elif source_type == "twitter":
                    batch_items.append(item)
                else:
                    batch_items.append({
                        "title": item["title"],
                        "content": item["text"],
                        "source": item["source"],
                        "url": item["url"],
                    })

            summaries = await self.summarizer.batch_summarize(batch_items, content_type)
            for item, summary in zip(items, summaries):
                item.update({
                    "summary": summary.summary,
                    "summary_zh": summary.summary_zh,
                    "key_points": summary.key_points,
                    "category": summary.category,
                    "quality_score": summary.quality_score,
                    "relevance_score": summary.relevance_score,
                    "entities": summary.entities,
                })
                all_items.append(item)

        return all_items

    # ------------------------------------------------------------------ #
    # Categorize & filter
    # ------------------------------------------------------------------ #

    def categorize_and_filter(self, items: List[Dict]) -> Dict[str, List[Dict]]:
        filtered_items = self.filter.apply_all_filters(items, config={
            "days": 3,
            "min_engagement": 5,
            "required_keywords": [],
            "excluded_keywords": ["crypto", "nft", "blockchain"],
            "min_quality_score": settings.min_quality_score,
        })

        category_names = {
            "agent-project":     "Agent Projects",
            "model-release":     "Model Releases",
            "research-paper":    "Research Papers",
            "industry-news":     "Industry News",
            "technical-tutorial":"Technical Tutorials",
            "product-launch":    "Product Launches",
            "open-source":       "Open Source",
            "podcast":           "Podcasts",
            "blog":              "Tech Blogs",
            "other":             "Other",
        }

        # Override category for typed items
        for item in filtered_items:
            if item.get("type") == "podcast":
                item["category"] = "podcast"
            elif item.get("type") == "blog":
                item["category"] = "blog"

        categorized: Dict[str, List] = {}
        for item in filtered_items:
            cat = category_names.get(item.get("category", "other"), "Other")
            categorized.setdefault(cat, []).append(item)

        for cat in categorized:
            categorized[cat].sort(key=lambda x: x.get("priority_score", 0), reverse=True)
            categorized[cat] = categorized[cat][:settings.max_articles_per_source]

        logger.info(f"Categorized into {len(categorized)} categories:")
        for cat, items in categorized.items():
            logger.info(f"  {cat}: {len(items)} items")

        return categorized

    # ------------------------------------------------------------------ #
    # Notion
    # ------------------------------------------------------------------ #

    async def create_notion_page(self, content: Dict[str, List[Dict]]) -> str:
        page_id = await self.notion_client.create_daily_briefing(
            date=datetime.now(),
            sections=content,
        )
        return page_id

    # ------------------------------------------------------------------ #
    # Test mode
    # ------------------------------------------------------------------ #

    async def test_run(self):
        logger.info("Running test briefing (limited sources)...")
        original = self.sources.copy()
        self.sources["twitter"]["ai_accounts"] = self.sources["twitter"]["ai_accounts"][:3]
        self.sources["github"]["topics"] = self.sources["github"]["topics"][:2]
        try:
            return await self.run_daily_briefing()
        finally:
            self.sources = original


async def run_daily_job():
    job = DailyBriefingJob()
    await job.run_daily_briefing()


if __name__ == "__main__":
    asyncio.run(DailyBriefingJob().test_run())
