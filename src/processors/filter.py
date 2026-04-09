from typing import List, Dict, Set
from datetime import datetime, timedelta
import re
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class ContentFilter:
    """Filter and deduplicate content based on various criteria"""

    def __init__(self):
        self.seen_urls: Set[str] = set()
        self.seen_titles: Set[str] = set()
        self.content_hashes: Set[str] = set()

    def filter_by_date(self, items: List[Dict], days: int = 1) -> List[Dict]:
        """Filter items by publication date"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        filtered = []

        for item in items:
            pub_date = item.get("published_at", item.get("created_at"))
            if pub_date:
                if isinstance(pub_date, str):
                    try:
                        pub_date = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    except:
                        continue

                # Ensure both datetimes have the same timezone awareness
                if pub_date.tzinfo is not None and cutoff_date.tzinfo is None:
                    cutoff_date = cutoff_date.replace(tzinfo=pub_date.tzinfo)
                elif pub_date.tzinfo is None and cutoff_date.tzinfo is not None:
                    pub_date = pub_date.replace(tzinfo=cutoff_date.tzinfo)

                if pub_date >= cutoff_date:
                    filtered.append(item)

        logger.info(f"Filtered {len(items)} to {len(filtered)} items by date")
        return filtered

    def filter_by_engagement(self, items: List[Dict], min_engagement: int = 10) -> List[Dict]:
        """Filter items by minimum engagement metrics"""
        filtered = []

        for item in items:
            item_type = item.get("type", "")
            eng = item.get("engagement", {})

            # RSS and tweets always pass — RSS has no engagement data,
            # tweets are pre-curated by account selection so engagement threshold
            # should not apply (fresh tweets from followed accounts have 0 likes)
            if item_type in ("rss", "tweet") or not eng:
                filtered.append(item)
                continue

            engagement = 0

            # Twitter metrics (nested under engagement dict)
            if "retweets" in eng or "likes" in eng:
                engagement += eng.get("retweets", 0)
                engagement += eng.get("likes", 0)
                engagement += eng.get("replies", 0)

            # GitHub metrics
            elif "stars" in eng:
                engagement = eng.get("stars", 0)

            # Reddit metrics — use comment count as quality signal
            # (score/upvotes can be gamed; comments indicate real discussion)
            elif "score" in eng:
                engagement = eng.get("comments", 0)
                min_engagement = 50  # override threshold for Reddit

            # Hacker News metrics
            elif "points" in eng:
                engagement = eng.get("points", 0)

            if engagement >= min_engagement:
                filtered.append(item)

        logger.info(f"Filtered {len(items)} to {len(filtered)} items by engagement")
        return filtered

    def filter_by_keywords(self, items: List[Dict], required_keywords: List[str],
                          excluded_keywords: List[str] = None) -> List[Dict]:
        """Filter items by required and excluded keywords"""
        if excluded_keywords is None:
            excluded_keywords = []

        filtered = []

        for item in items:
            text = self._get_item_text(item).lower()

            # Check required keywords
            has_required = all(keyword.lower() in text for keyword in required_keywords)

            # Check excluded keywords
            has_excluded = any(keyword.lower() in text for keyword in excluded_keywords)

            if has_required and not has_excluded:
                filtered.append(item)

        logger.info(f"Filtered {len(items)} to {len(filtered)} items by keywords")
        return filtered

    def deduplicate_content(self, items: List[Dict]) -> List[Dict]:
        """Remove duplicate content based on various criteria"""
        unique_items = []
        seen_content = set()

        for item in items:
            # Generate content fingerprint
            fingerprint = self._generate_fingerprint(item)

            if fingerprint not in seen_content:
                seen_content.add(fingerprint)
                unique_items.append(item)

        logger.info(f"Deduplicated {len(items)} to {len(unique_items)} items")
        return unique_items

    def _generate_fingerprint(self, item: Dict) -> str:
        """Generate a content fingerprint for deduplication"""
        # Use title + first 100 chars of content
        title = item.get("title", "")
        content = self._get_item_text(item)[:100]

        # Remove common words and normalize
        fingerprint = f"{title} {content}".lower()
        fingerprint = re.sub(r'[^\w\s]', '', fingerprint)
        fingerprint = ' '.join(fingerprint.split()[:20])  # First 20 words

        return fingerprint

    def _get_item_text(self, item: Dict) -> str:
        """Extract text content from item"""
        text_fields = ["text", "content", "description", "body", "summary"]

        for field in text_fields:
            if field in item and item[field]:
                return str(item[field])

        return ""

    def filter_by_source_quality(self, items: List[Dict],
                               trusted_sources: List[str] = None) -> List[Dict]:
        """Filter items by source quality and trustworthiness"""
        if trusted_sources is None:
            trusted_sources = [
                # Twitter accounts
                "@AndrewYNg", "@karpathy", "@goodfellow_ian", "@ylecun",
                "@jeremyphoward", "@hardmaru", "@_akhaliq", "@omarsar0",
                "@seb_ruder", "@huggingface",

                # Organizations
                "openai", "anthropics", "google-research", "facebookresearch",
                "deepmind", "microsoft", "pytorch", "tensorflow",

                # Publications
                "arxiv.org", "distill.pub", "ai.googleblog.com",
                "blog.research.google", "openai.com/blog", "anthropic.com/news"
            ]

        filtered = []

        for item in items:
            source = item.get("source", "")
            author = item.get("author", "")
            url = item.get("url", "")

            # Check if from trusted source
            is_trusted = any(trusted in source.lower() or
                           trusted in author.lower() or
                           trusted in url.lower()
                           for trusted in trusted_sources)

            # Boost quality score for trusted sources
            if is_trusted:
                if "quality_score" not in item:
                    item["quality_score"] = 0.0
                item["quality_score"] = min(1.0, item["quality_score"] + 0.2)
                filtered.append(item)

        logger.info(f"Filtered {len(items)} to {len(filtered)} trusted sources")
        return filtered

    def prioritize_content(self, items: List[Dict]) -> List[Dict]:
        """Prioritize content based on multiple factors"""
        scored_items = []

        for item in items:
            score = 0

            # Engagement score (0-40 points)
            engagement = self._calculate_engagement_score(item)
            score += min(40, engagement / 1000 * 40)

            # Recency score (0-30 points)
            recency = self._calculate_recency_score(item)
            score += recency

            # Quality score (0-20 points)
            quality = item.get("quality_score", 0.5) * 20
            score += quality

            # Source authority (0-10 points)
            authority = self._calculate_authority_score(item)
            score += authority

            item["priority_score"] = score
            scored_items.append(item)

        # Sort by priority score
        scored_items.sort(key=lambda x: x["priority_score"], reverse=True)

        return scored_items

    def _calculate_engagement_score(self, item: Dict) -> int:
        """Calculate engagement score for an item"""
        score = 0

        # Twitter
        if "retweet_count" in item:
            score += item.get("retweet_count", 0) * 2
            score += item.get("like_count", 0)
            score += item.get("reply_count", 0) * 3

        # GitHub
        elif "stars" in item:
            score = item.get("stars", 0)

        # Reddit
        elif "score" in item:
            score = item.get("score", 0)

        # Hacker News
        elif "points" in item:
            score = item.get("points", 0)

        return score

    def _calculate_recency_score(self, item: Dict) -> float:
        """Calculate recency score (0-30 points)"""
        pub_date = item.get("published_at", item.get("created_at"))
        if not pub_date:
            return 15  # Default score

        if isinstance(pub_date, str):
            try:
                pub_date = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            except:
                return 15

        now = datetime.now(pub_date.tzinfo) if pub_date.tzinfo else datetime.utcnow()
        hours_old = (now - pub_date).total_seconds() / 3600

        # Exponential decay: 30 points for 0 hours, 0 points for 48+ hours
        score = 30 * max(0, 1 - (hours_old / 48))

        return score

    def _calculate_authority_score(self, item: Dict) -> float:
        """Calculate source authority score (0-10 points)"""
        source = item.get("source", "").lower()
        author = item.get("author", "").lower()

        # High authority sources
        high_authority = [
            "openai", "anthropic", "deepmind", "google research",
            "facebook research", "microsoft research", "arxiv"
        ]

        # Medium authority sources
        medium_authority = [
            "huggingface", "pytorch", "tensorflow", "distill.pub",
            "ai.googleblog", "blog.research.google"
        ]

        for auth_source in high_authority:
            if auth_source in source or auth_source in author:
                return 10

        for auth_source in medium_authority:
            if auth_source in source or auth_source in author:
                return 7

        # Check for verified Twitter accounts (implied by high engagement)
        if "retweet_count" in item and item.get("retweet_count", 0) > 1000:
            return 5

        return 2  # Default score

    def apply_all_filters(self, items: List[Dict], config: Dict = None) -> List[Dict]:
        """Apply all filtering steps in sequence"""
        if config is None:
            config = {
                "days": 1,
                "min_engagement": 10,
                "required_keywords": [],
                "excluded_keywords": ["crypto", "nft", "blockchain"],
                "min_quality_score": 0.6
            }

        # Step 1: Filter by date
        items = self.filter_by_date(items, config.get("days", 1))

        # Step 2: Filter by engagement
        items = self.filter_by_engagement(items, config.get("min_engagement", 10))

        # Step 3: Filter by keywords
        items = self.filter_by_keywords(
            items,
            config.get("required_keywords", []),
            config.get("excluded_keywords", [])
        )

        # Step 4: Deduplicate
        items = self.deduplicate_content(items)

        # Step 5: Skip trusted-sources-only filter — content was already keyword-filtered
        # filter_by_source_quality drops everything not from a hardcoded list, which is too
        # aggressive for general AI/indie-hacker content from Reddit, HN, etc.

        # Step 6: Prioritize
        items = self.prioritize_content(items)

        # Step 7: Quality score filter intentionally removed.
        # Each source has its own quality signal:
        #   - tweet (account): curated account list
        #   - tweet (trending): ≥5000 likes
        #   - reddit: comments ≥ 50
        #   - hackernews: ≥ 30 points (filtered at fetch time)
        #   - github: stars this week (from trending page)
        #   - rss / podcast / blog: pre-selected trusted sources
        # Claude's quality_score has no clear grounding — don't use it as a hard gate.

        logger.info(f"Final filtered result: {len(items)} items")
        return items