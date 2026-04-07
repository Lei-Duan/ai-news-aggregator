import asyncio
import logging
from datetime import datetime
from typing import Dict, List
import yaml

# Import fetchers
from src.fetchers.twitter import TwitterFetcher
from src.fetchers.github import GitHubFetcher
from src.fetchers.reddit_rss import RedditRSSFetcher  # Use RSS instead of API
from src.fetchers.hackernews import HackerNewsFetcher
from src.fetchers.rss import RSSFetcher

# Import processors
from src.processors.summarizer import ContentSummarizer
from src.processors.classifier import ContentClassifier
from src.processors.filter import ContentFilter
from src.scheduler.basic_processor import BasicContentProcessor

# Import Notion client
from src.notion.client import NotionClient

# Import settings
from config.settings import settings

logger = logging.getLogger(__name__)

class DailyBriefingJob:
    def __init__(self):
        self.setup_logging()
        self.load_sources()
        self.initialize_clients()

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, settings.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(settings.log_file),
                logging.StreamHandler()
            ]
        )

    def load_sources(self):
        """Load source configuration from YAML file"""
        with open('config/sources.yaml', 'r') as f:
            self.sources = yaml.safe_load(f)

    def initialize_clients(self):
        """Initialize all API clients"""
        # Twitter client
        self.twitter_fetcher = TwitterFetcher(
            bearer_token=settings.twitter_bearer_token,
            api_key=settings.twitter_api_key,
            api_secret=settings.twitter_api_secret,
            access_token=settings.twitter_access_token,
            access_token_secret=settings.twitter_access_token_secret
        )

        # GitHub client
        self.github_fetcher = GitHubFetcher(
            token=settings.github_token
        )

        # Reddit client (using RSS instead of API - no credentials needed)
        self.reddit_fetcher = RedditRSSFetcher()

        # Hacker News client
        self.hackernews_fetcher = HackerNewsFetcher()

        # RSS client
        self.rss_fetcher = RSSFetcher()

        # Content processors
        # Always use AI summarization since you have Anthropic API
        self.summarizer = ContentSummarizer(
            anthropic_api_key=settings.anthropic_api_key
        )
        self.use_ai_summarization = True
        logger.info("Using AI-powered summarization with Claude")

        self.classifier = ContentClassifier()
        self.filter = ContentFilter()

        # Notion client
        self.notion_client = NotionClient(
            token=settings.notion_token,
            database_id=settings.notion_database_id
        )

    async def run_daily_briefing(self):
        """Run the complete daily briefing workflow"""
        logger.info("Starting daily AI briefing generation...")

        try:
            # Step 1: Fetch content from all sources
            logger.info("Fetching content from all sources...")
            raw_content = await self.fetch_all_content()

            # Step 2: Pre-filter BEFORE summarization to save tokens
            logger.info("Pre-filtering content before AI summarization...")
            raw_content = self.pre_filter_content(raw_content)

            # Step 3: Process and summarize (only filtered content)
            logger.info("Processing and summarizing content...")
            processed_content = await self.process_content(raw_content)

            # Step 4: Filter and categorize
            logger.info("Filtering and categorizing content...")
            categorized_content = self.categorize_and_filter(processed_content)

            # Step 5: Create Notion page
            logger.info("Creating Notion page...")
            page_id = await self.create_notion_page(categorized_content)

            logger.info(f"Daily briefing completed successfully! Page ID: {page_id}")
            return page_id

        except Exception as e:
            logger.error(f"Error in daily briefing generation: {e}", exc_info=True)
            raise

    def pre_filter_content(self, raw_content: Dict[str, List]) -> Dict[str, List]:
        """Pre-filter content BEFORE AI summarization to minimize token usage"""
        AI_KEYWORDS = [
            "ai", "llm", "gpt", "claude", "gemini", "llama", "mistral",
            "machine learning", "deep learning", "neural", "transformer",
            "openai", "anthropic", "agent", "chatbot", "embedding",
            "fine-tun", "rag", "inference", "model", "diffusion",
            "build in public", "indie hacker", "saas", "startup"
        ]
        EXCLUDE_KEYWORDS = ["crypto", "nft", "blockchain", "bitcoin", "ethereum"]

        def is_relevant(item: Dict) -> bool:
            text = " ".join([
                item.get("title", ""), item.get("text", ""),
                item.get("description", ""), item.get("source", "")
            ]).lower()
            has_exclude = any(kw in text for kw in EXCLUDE_KEYWORDS)
            if has_exclude:
                return False
            has_ai = any(kw in text for kw in AI_KEYWORDS)
            return has_ai

        # Per-source limits to cap token usage
        LIMITS = {
            "twitter": 20,
            "github": 15,
            "hackernews": 20,
            "reddit": 15,
            "rss": 10,
        }

        filtered = {}
        for source, items in raw_content.items():
            # Date filter: keep only last 24 hours
            items = self.filter.filter_by_date(items, days=1)
            # Keyword relevance filter
            items = [i for i in items if is_relevant(i)]
            # Cap per source
            limit = LIMITS.get(source, 10)
            items = items[:limit]
            filtered[source] = items
            logger.info(f"Pre-filter {source}: {len(raw_content[source])} → {len(items)} items")

        return filtered

    async def fetch_all_content(self) -> Dict[str, List]:
        """Fetch content from all configured sources"""
        content = {}

        # Fetch Twitter content
        logger.info("Fetching Twitter content...")
        twitter_content = await self.fetch_twitter_content()
        content["twitter"] = twitter_content

        # Fetch GitHub content
        logger.info("Fetching GitHub content...")
        github_content = await self.fetch_github_content()
        content["github"] = github_content

        # Fetch Reddit content
        logger.info("Fetching Reddit content...")
        reddit_content = await self.fetch_reddit_content()
        content["reddit"] = reddit_content

        # Fetch Hacker News content
        logger.info("Fetching Hacker News content...")
        hackernews_content = await self.fetch_hackernews_content()
        content["hackernews"] = hackernews_content

        # Fetch RSS content
        logger.info("Fetching RSS content...")
        rss_content = await self.fetch_rss_content()
        content["rss"] = rss_content

        return content

    async def fetch_twitter_content(self) -> List[Dict]:
        """Fetch AI-related tweets"""
        tweets = await self.twitter_fetcher.fetch_tweets_from_accounts(
            accounts=self.sources["twitter"]["ai_accounts"],
            keywords=self.sources["twitter"]["keywords"],
            hours_back=24
        )

        # Convert to standard format
        return [
            {
                "type": "tweet",
                "id": tweet.id,
                "title": f"Tweet by @{tweet.author_username}",
                "text": tweet.text,
                "author": tweet.author_name,
                "source": f"@{tweet.author_username}",
                "url": tweet.url,
                "published_at": tweet.created_at,
                "engagement": {
                    "retweets": tweet.retweet_count,
                    "likes": tweet.like_count,
                    "replies": tweet.reply_count
                }
            }
            for tweet in tweets
        ]

    async def fetch_github_content(self) -> List[Dict]:
        """Fetch trending AI repositories, prioritized by star velocity (fastest-rising new projects)."""
        # Fetch trending repos by topics — multi-language, sorted by star velocity
        trending_repos = await self.github_fetcher.fetch_trending_repos(
            topics=self.sources["github"]["topics"],
            language=None,  # search all major languages
            created_after_days=30
        )

        # Also catch viral new AI repos that may not have topic tags yet
        viral_repos = await self.github_fetcher.fetch_recently_starred(
            min_stars=200,
            created_after_days=14
        )

        # Merge, deduplicate, re-sort by star velocity
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
                # Include star velocity in text so Claude can surface it in the summary
                "text": f"{repo.description or repo.name} [⭐ {repo.stars} stars, {repo.star_velocity:.1f} stars/day]",
                "author": repo.owner,
                "source": "GitHub",
                "url": repo.url,
                "published_at": repo.created_at,  # sort by creation date for recency filter
                "engagement": {
                    "stars": repo.stars,
                    "forks": repo.forks,
                    "watchers": repo.stars
                },
                "star_velocity": repo.star_velocity,
                "topics": repo.topics,
                "language": repo.language
            }
            for repo in all_repos
        ]

    async def fetch_hackernews_content(self) -> List[Dict]:
        """Fetch AI-related Hacker News stories"""
        stories = await self.hackernews_fetcher.fetch_top_stories(limit=50)

        # Convert to standard format
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
                "engagement": {
                    "points": story.points,
                    "comments": story.num_comments
                },
                "story_type": story.story_type
            }
            for story in stories
        ]

    async def fetch_rss_content(self) -> List[Dict]:
        """Fetch AI-related RSS feed items"""
        # Get AI blog feeds from sources.yaml
        feed_urls = self.sources.get("rss_feeds", [])

        items = await self.rss_fetcher.fetch_feeds(feed_urls)

        # Convert to standard format
        return [
            {
                "type": "rss",
                "id": item.link or item.title,
                "title": item.title,
                "text": item.description or item.content or item.title,
                "author": item.author or "Unknown",
                "source": item.source,
                "url": item.link,
                "published_at": item.published,
                "engagement": {},  # RSS doesn't have engagement metrics
                "tags": item.tags
            }
            for item in items
        ]

    async def fetch_reddit_content(self) -> List[Dict]:
        """Fetch AI-related Reddit posts via RSS (no API needed)"""
        posts = await self.reddit_fetcher.fetch_combined_feed(
            subreddits=self.sources["reddit"]["subreddits"],
            keywords=self.sources["reddit"].get("keywords", [])
        )

        # Convert to standard format
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
                    "upvote_ratio": post.upvote_ratio
                },
                "flair": post.flair,
                "subreddit": post.subreddit
            }
            for post in posts
        ]

    async def process_content(self, raw_content: Dict[str, List]) -> List[Dict]:
        """Process and summarize all content"""
        all_items = []

        # Process each source type
        for source_type, items in raw_content.items():
            if source_type == "twitter":
                # Always use AI summarization with your Anthropic API
                tweet_summaries = await self.summarizer.batch_summarize(
                    items, "tweet"
                )
                for item, summary in zip(items, tweet_summaries):
                    item.update({
                        "summary": summary.summary,
                        "summary_zh": summary.summary_zh,
                        "key_points": summary.key_points,
                        "category": summary.category,
                        "quality_score": summary.quality_score,
                        "relevance_score": summary.relevance_score,
                        "entities": summary.entities
                    })
                    all_items.append(item)
            elif source_type == "github":
                # Summarize GitHub repos
                github_items = []
                for item in items:
                    github_items.append({
                        "name": item["title"],
                        "description": item["text"],
                        "stars": item["engagement"]["stars"],
                        "topics": item["topics"],
                        "recent_commits": []  # TODO: Fetch recent commits
                    })

                repo_summaries = await self.summarizer.batch_summarize(
                    github_items, "github"
                )
                for item, summary in zip(items, repo_summaries):
                    item.update({
                        "summary": summary.summary,
                        "summary_zh": summary.summary_zh,
                        "key_points": summary.key_points,
                        "category": summary.category,
                        "quality_score": summary.quality_score,
                        "relevance_score": summary.relevance_score,
                        "entities": summary.entities
                    })
                    all_items.append(item)

            elif source_type == "reddit":
                # Summarize Reddit posts
                reddit_items = []
                for item in items:
                    reddit_items.append({
                        "title": item["title"],
                        "content": item["text"],
                        "source": f"r/{item['subreddit']}",
                        "url": item["url"]
                    })

                reddit_summaries = await self.summarizer.batch_summarize(
                    reddit_items, "article"
                )
                for item, summary in zip(items, reddit_summaries):
                    item.update({
                        "summary": summary.summary,
                        "summary_zh": summary.summary_zh,
                        "key_points": summary.key_points,
                        "category": summary.category,
                        "quality_score": summary.quality_score,
                        "relevance_score": summary.relevance_score,
                        "entities": summary.entities
                    })
                    all_items.append(item)

            elif source_type == "hackernews":
                # Summarize Hacker News stories
                hn_items = []
                for item in items:
                    hn_items.append({
                        "title": item["title"],
                        "content": item["text"] or item["title"],
                        "source": "Hacker News",
                        "url": item["url"] or item["permalink"]
                    })

                hn_summaries = await self.summarizer.batch_summarize(
                    hn_items, "article"
                )
                for item, summary in zip(items, hn_summaries):
                    item.update({
                        "summary": summary.summary,
                        "summary_zh": summary.summary_zh,
                        "key_points": summary.key_points,
                        "category": summary.category,
                        "quality_score": summary.quality_score,
                        "relevance_score": summary.relevance_score,
                        "entities": summary.entities
                    })
                    all_items.append(item)

            elif source_type == "rss":
                # Summarize RSS feed items
                rss_items = []
                for item in items:
                    rss_items.append({
                        "title": item["title"],
                        "content": item["text"],
                        "source": item["source"],
                        "url": item["url"]
                    })

                rss_summaries = await self.summarizer.batch_summarize(
                    rss_items, "article"
                )
                for item, summary in zip(items, rss_summaries):
                    item.update({
                        "summary": summary.summary,
                        "summary_zh": summary.summary_zh,
                        "key_points": summary.key_points,
                        "category": summary.category,
                        "quality_score": summary.quality_score,
                        "relevance_score": summary.relevance_score,
                        "entities": summary.entities
                    })
                    all_items.append(item)

        return all_items

    def _basic_categorize(self, text: str) -> str:
        """Basic categorization without AI"""
        text_lower = text.lower()
        if "agent" in text_lower or "autonomous" in text_lower:
            return "agent-project"
        elif "gpt" in text_lower or "claude" in text_lower or "llm" in text_lower or "model" in text_lower:
            return "model-release"
        elif "research" in text_lower or "paper" in text_lower:
            return "research-paper"
        elif "github" in text_lower or "open source" in text_lower:
            return "open-source"
        else:
            return "other"

    def _basic_extract_entities(self, text: str) -> List[str]:
        """Basic entity extraction"""
        text_lower = text.lower()
        entities = []

        # Companies
        companies = ["openai", "anthropic", "google", "microsoft", "meta"]
        entities.extend([c.title() for c in companies if c in text_lower])

        # Models
        models = ["gpt", "claude", "llama", "gemini"]
        entities.extend([m.title() for m in models if m in text_lower])

        return entities

    def categorize_and_filter(self, items: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize and filter content"""
        # Apply filters
        filtered_items = self.filter.apply_all_filters(items, config={
            "days": 1,
            "min_engagement": 5,
            "required_keywords": [],
            "excluded_keywords": ["crypto", "nft", "blockchain"],
            "min_quality_score": settings.min_quality_score
        })

        # Categorize by content type
        categorized = {}
        category_names = {
            "agent-project": "Agent Projects",
            "model-release": "Model Releases",
            "research-paper": "Research Papers",
            "industry-news": "Industry News",
            "technical-tutorial": "Technical Tutorials",
            "product-launch": "Product Launches",
            "open-source": "Open Source",
            "other": "Other"
        }

        for item in filtered_items:
            category = item.get("category", "other")
            category_name = category_names.get(category, "Other")

            if category_name not in categorized:
                categorized[category_name] = []

            categorized[category_name].append(item)

        # Sort each category by priority score
        for category in categorized:
            categorized[category].sort(
                key=lambda x: x.get("priority_score", 0),
                reverse=True
            )

        # Limit items per category
        for category in categorized:
            categorized[category] = categorized[category][:settings.max_articles_per_source]

        logger.info(f"Categorized content into {len(categorized)} categories")
        for cat, items in categorized.items():
            logger.info(f"  {cat}: {len(items)} items")

        return categorized

    async def create_notion_page(self, content: Dict[str, List[Dict]]) -> str:
        """Create Notion page with the categorized content"""
        today = datetime.now()

        # Create new page (duplicate check skipped — Notion query API unstable in SDK v3)
        page_id = await self.notion_client.create_daily_briefing(
            date=today,
            sections=content
        )

        return page_id

    async def test_run(self):
        """Run a test with limited content"""
        logger.info("Running test briefing...")

        # Limit sources for testing
        original_sources = self.sources.copy()
        self.sources["twitter"]["ai_accounts"] = self.sources["twitter"]["ai_accounts"][:3]
        self.sources["github"]["topics"] = self.sources["github"]["topics"][:3]

        try:
            page_id = await self.run_daily_briefing()
            logger.info(f"Test run completed. Page ID: {page_id}")
            return page_id

        finally:
            # Restore original sources
            self.sources = original_sources

# Standalone function for scheduler
async def run_daily_job():
    """Function to be called by the scheduler"""
    job = DailyBriefingJob()
    await job.run_daily_briefing()

if __name__ == "__main__":
    # Run test
    asyncio.run(DailyBriefingJob().test_run())