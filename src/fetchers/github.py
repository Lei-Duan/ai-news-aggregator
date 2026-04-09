import asyncio
import aiohttp
from typing import List, Optional
from datetime import datetime, timezone
import logging
import re
from dataclasses import dataclass, field
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TRENDING_URL = "https://github.com/trending"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Languages to pull trending for (one request per language + one overall)
LANGUAGES = ["python", "typescript", "javascript", "rust", "go"]

# Repos from giant orgs are well-known baselines, not trending discoveries
EXCLUDED_ORGS = {
    "openai", "anthropics", "google", "microsoft", "meta", "facebook",
    "huggingface", "deepmind", "apple", "amazon", "alibaba", "baidu",
}

# AI-related keywords to filter non-AI repos from the general trending page
AI_KEYWORDS = [
    "llm", "ai", "gpt", "claude", "gemini", "llama", "mistral",
    "machine learning", "deep learning", "neural", "transformer",
    "agent", "chatbot", "embedding", "diffusion", "inference",
    "openai", "anthropic", "langchain", "rag", "fine-tun",
    "vibe cod", "copilot", "stable diffusion", "hugging",
]


@dataclass
class GitHubRepo:
    name: str
    full_name: str
    description: str
    url: str
    stars: int
    forks: int
    language: str
    created_at: datetime
    updated_at: datetime
    topics: List[str]
    owner: str
    star_velocity: float = 0.0   # stars gained this week (from trending page)


class GitHubFetcher:
    def __init__(self, token: str = ""):
        # Token kept for backwards compat but not used in trending scrape
        self.token = token

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def fetch_trending_repos(self, topics: List[str] = None,
                                   language: str = None,
                                   created_after_days: int = 30) -> List[GitHubRepo]:
        """
        Scrape github.com/trending (weekly) for AI-related repos.
        Returns repos sorted by stars gained this week (descending).
        `topics` and `created_after_days` params kept for API compatibility but unused —
        GitHub trending already reflects the best weekly signal.
        """
        all_repos: dict[str, GitHubRepo] = {}

        # One request per language + one language-agnostic request
        urls = [f"{TRENDING_URL}?since=weekly"] + [
            f"{TRENDING_URL}/{lang}?since=weekly" for lang in LANGUAGES
        ]

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for url in urls:
                try:
                    repos = await self._scrape_trending_page(session, url)
                    for repo in repos:
                        if repo.full_name not in all_repos:
                            all_repos[repo.full_name] = repo
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"GitHub trending scrape error for {url}: {e}")

        # Filter out excluded orgs and non-AI repos
        filtered = [
            r for r in all_repos.values()
            if r.owner.lower() not in EXCLUDED_ORGS and self._is_ai_related(r)
        ]

        filtered.sort(key=lambda r: r.star_velocity, reverse=True)
        logger.info(f"GitHub trending: {len(filtered)} AI repos this week")
        return filtered[:40]

    async def fetch_recently_starred(self, min_stars: int = 200,
                                     created_after_days: int = 14) -> List[GitHubRepo]:
        """
        Kept for API compatibility. Trending scrape already covers fast-rising repos,
        so this returns an empty list to avoid duplicating results.
        """
        return []

    # ------------------------------------------------------------------ #
    # Scraping
    # ------------------------------------------------------------------ #

    async def _scrape_trending_page(self, session: aiohttp.ClientSession,
                                    url: str) -> List[GitHubRepo]:
        async with session.get(url, headers=HEADERS) as resp:
            if resp.status != 200:
                logger.warning(f"GitHub trending returned {resp.status} for {url}")
                return []
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("article.Box-row")
        repos = []

        for article in articles:
            repo = self._parse_article(article)
            if repo:
                repos.append(repo)

        logger.info(f"GitHub trending [{url.split('?')[0].split('/')[-1] or 'all'}]: "
                    f"{len(repos)} repos")
        return repos

    def _parse_article(self, article) -> Optional[GitHubRepo]:
        try:
            # Repo full name from the heading link
            heading = article.select_one("h2 a")
            if not heading:
                return None
            raw_path = heading.get("href", "").strip("/")   # "owner/repo"
            if raw_path.count("/") != 1:
                return None
            owner, repo_name = raw_path.split("/", 1)

            # Description
            desc_el = article.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else ""

            # Language
            lang_el = article.select_one("[itemprop='programmingLanguage']")
            language = lang_el.get_text(strip=True) if lang_el else ""

            # Total stars (second svg-link in the meta row)
            star_links = article.select("a.Link--muted")
            total_stars = 0
            forks = 0
            for link in star_links:
                text = link.get_text(strip=True).replace(",", "")
                href = link.get("href", "")
                if "stargazers" in href:
                    total_stars = self._parse_int(text)
                elif "forks" in href:
                    forks = self._parse_int(text)

            # Stars this week — the float-right span
            weekly_el = article.select_one("span.float-sm-right")
            stars_this_week = 0
            if weekly_el:
                weekly_text = weekly_el.get_text(strip=True)
                # e.g. "1,234 stars this week"
                stars_this_week = self._parse_int(weekly_text)

            return GitHubRepo(
                name=repo_name,
                full_name=raw_path,
                description=description,
                url=f"https://github.com/{raw_path}",
                stars=total_stars,
                forks=forks,
                language=language,
                created_at=datetime.now(tz=timezone.utc),   # not available on trending page
                updated_at=datetime.now(tz=timezone.utc),
                topics=[],
                owner=owner,
                star_velocity=float(stars_this_week),
            )
        except Exception as e:
            logger.error(f"GitHub: error parsing trending article: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _parse_int(self, text: str) -> int:
        """Extract first integer from a string like '1,234 stars this week'."""
        cleaned = re.sub(r"[^\d]", "", text.split()[0]) if text.split() else ""
        return int(cleaned) if cleaned else 0

    def _is_ai_related(self, repo: GitHubRepo) -> bool:
        text = f"{repo.name} {repo.description} {repo.language}".lower()
        return any(kw in text for kw in AI_KEYWORDS)
