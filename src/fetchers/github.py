import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Repos from these giant orgs are well-known baselines, not trending discoveries
EXCLUDED_ORGS = {"openai", "anthropics", "google", "microsoft", "meta", "facebook",
                 "huggingface", "deepmind", "apple", "amazon", "alibaba", "baidu"}

# Languages to search across for broader coverage
SEARCH_LANGUAGES = ["python", "typescript", "javascript", "go", "rust"]


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
    star_velocity: float = 0.0  # stars per day since creation


@dataclass
class GitHubRelease:
    tag_name: str
    name: str
    body: str
    published_at: datetime
    html_url: str
    repo_name: str


class GitHubFetcher:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def _compute_star_velocity(self, repo: GitHubRepo) -> float:
        """Stars per day since repo creation. Higher = faster rising."""
        now = datetime.now(tz=timezone.utc)
        created = repo.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days_alive = max(1, (now - created).total_seconds() / 86400)
        return repo.stars / days_alive

    async def fetch_trending_repos(self, topics: List[str], language: str = None,
                                   created_after_days: int = 30) -> List[GitHubRepo]:
        """Fetch recently-created repos by topic, sorted by star velocity (fastest rising first)."""
        repos = []
        created_after = datetime.utcnow() - timedelta(days=created_after_days)
        created_after_str = created_after.strftime("%Y-%m-%d")

        # Search each topic across multiple languages for broad coverage
        languages_to_search = SEARCH_LANGUAGES if language is None else [language]

        async with aiohttp.ClientSession() as session:
            for topic in topics:
                for lang in languages_to_search:
                    try:
                        topic_repos = await self._search_repos(
                            session, topic, lang, created_after_str
                        )
                        repos.extend(topic_repos)
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Error fetching repos for topic={topic} lang={lang}: {e}")

        # Deduplicate by full_name, exclude giant orgs
        seen = {}
        for repo in repos:
            if repo.owner.lower() in EXCLUDED_ORGS:
                continue
            if repo.full_name not in seen:
                seen[repo.full_name] = repo

        # Compute star velocity and sort — fastest-rising new projects first
        unique_repos = list(seen.values())
        for repo in unique_repos:
            repo.star_velocity = self._compute_star_velocity(repo)

        unique_repos.sort(key=lambda r: r.star_velocity, reverse=True)

        logger.info(f"GitHub trending: {len(unique_repos)} unique repos after velocity sort")
        return unique_repos[:40]

    async def _search_repos(self, session: aiohttp.ClientSession, topic: str,
                            language: str, created_after: str) -> List[GitHubRepo]:
        """Search GitHub for repos by topic + language created after a date."""
        # Require at least some traction (stars >= 10) to filter noise
        query = f"topic:{topic} language:{language} created:>{created_after} stars:>=10"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 30
        }

        url = f"{self.base_url}/search/repositories"

        async with session.get(url, headers=self.headers, params=params) as response:
            if response.status == 403:
                logger.warning("GitHub API rate limit hit")
                return []
            if response.status != 200:
                logger.error(f"GitHub API error {response.status} for topic={topic}")
                return []

            data = await response.json()
            repos = []
            for item in data.get("items", []):
                repo = self._parse_repo(item)
                if repo:
                    repos.append(repo)
            return repos

    def _parse_repo(self, item: Dict) -> Optional[GitHubRepo]:
        try:
            return GitHubRepo(
                name=item["name"],
                full_name=item["full_name"],
                description=item.get("description") or "",
                url=item["html_url"],
                stars=item["stargazers_count"],
                forks=item["forks_count"],
                language=item.get("language") or "",
                created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00")),
                topics=item.get("topics", []),
                owner=item["owner"]["login"]
            )
        except Exception as e:
            logger.error(f"Error parsing repo {item.get('full_name', '?')}: {e}")
            return None

    async def fetch_recently_starred(self, min_stars: int = 200,
                                     created_after_days: int = 14) -> List[GitHubRepo]:
        """Fetch AI repos created recently with meaningful star count — catches viral new repos."""
        created_after = datetime.utcnow() - timedelta(days=created_after_days)
        created_after_str = created_after.strftime("%Y-%m-%d")

        ai_queries = [
            f"topic:llm created:>{created_after_str} stars:>={min_stars}",
            f"topic:ai-agent created:>{created_after_str} stars:>={min_stars}",
            f"\"vibe coding\" created:>{created_after_str} stars:>={min_stars}",
        ]

        repos = []
        async with aiohttp.ClientSession() as session:
            for query in ai_queries:
                try:
                    params = {"q": query, "sort": "stars", "order": "desc", "per_page": 20}
                    async with session.get(f"{self.base_url}/search/repositories",
                                          headers=self.headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            for item in data.get("items", []):
                                repo = self._parse_repo(item)
                                if repo and repo.owner.lower() not in EXCLUDED_ORGS:
                                    repo.star_velocity = self._compute_star_velocity(repo)
                                    repos.append(repo)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error in fetch_recently_starred: {e}")

        seen = {}
        for r in repos:
            if r.full_name not in seen:
                seen[r.full_name] = r

        result = sorted(seen.values(), key=lambda r: r.star_velocity, reverse=True)
        return result[:20]

    async def fetch_recent_releases(self, repos: List[str]) -> List[GitHubRelease]:
        """Fetch recent releases from specific repositories."""
        releases = []

        async with aiohttp.ClientSession() as session:
            for repo in repos:
                try:
                    repo_releases = await self._fetch_releases(session, repo)
                    releases.extend(repo_releases)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error fetching releases from {repo}: {e}")

        cutoff_date = datetime.now(tz=timezone.utc) - timedelta(days=7)
        recent_releases = [r for r in releases if r.published_at > cutoff_date]
        return sorted(recent_releases, key=lambda x: x.published_at, reverse=True)

    async def _fetch_releases(self, session: aiohttp.ClientSession,
                              repo_full_name: str) -> List[GitHubRelease]:
        url = f"{self.base_url}/repos/{repo_full_name}/releases"

        async with session.get(url, headers=self.headers) as response:
            if response.status != 200:
                return []

            data = await response.json()
            releases = []
            for item in data[:5]:  # only latest 5 releases
                release = GitHubRelease(
                    tag_name=item["tag_name"],
                    name=item.get("name", ""),
                    body=item.get("body", ""),
                    published_at=datetime.fromisoformat(item["published_at"].replace("Z", "+00:00")),
                    html_url=item["html_url"],
                    repo_name=repo_full_name
                )
                releases.append(release)
            return releases
