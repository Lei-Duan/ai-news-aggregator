"""
Tech blog scraper for Anthropic and OpenAI.

Strategy (same as follow-builders):
  1. Fetch index page
  2. Try to extract __NEXT_DATA__ JSON (Next.js SSR)
  3. Fall back to regex HTML link extraction
  4. Fetch individual article pages for full text
"""

import asyncio
import aiohttp
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

BLOG_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BLOG_SOURCES = {
    "Anthropic": {
        # Anthropic's site is client-side rendered — article pages have no date in HTML.
        # Sitemap provides both URLs and accurate lastmod dates in one request.
        "sitemap_url": "https://www.anthropic.com/sitemap.xml",
        "sitemap_path_prefix": "/news/",
        "base": "https://www.anthropic.com",
    },
    "OpenAI": {
        "index_urls": ["https://openai.com/blog"],
        "base": "https://openai.com",
        "link_pattern": r'href="(/blog/[a-z0-9][a-z0-9\-]+)"',
    },
    "Google Gemini": {
        "index_urls": ["https://blog.google/products/gemini/"],
        "base": "https://blog.google",
        "link_pattern": r'href="(/products/gemini/[a-z0-9][a-z0-9\-]+/?)"',
    },
    "Google DeepMind": {
        "index_urls": ["https://deepmind.google/discover/blog/"],
        "base": "https://deepmind.google",
        "link_pattern": r'href="(/discover/blog/[a-z0-9][a-z0-9\-]+/?)"',
    },
}


@dataclass
class BlogPost:
    title: str
    url: str
    source: str           # "Anthropic" or "OpenAI"
    published_at: datetime
    author: str
    content: str          # cleaned full text (first 3000 chars)
    date_unknown: bool = False


class BlogFetcher:
    def __init__(self, max_age_hours: int = 72):
        self.max_age_hours = max_age_hours
        self.timeout = aiohttp.ClientTimeout(total=20)
        self.headers = {"User-Agent": BLOG_USER_AGENT}

    async def fetch_all(self) -> List[BlogPost]:
        """Fetch recent posts from all configured blogs."""
        posts: List[BlogPost] = []
        async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
            for source_name, cfg in BLOG_SOURCES.items():
                try:
                    source_posts = await self._fetch_source(session, source_name, cfg)
                    posts.extend(source_posts)
                    logger.info(f"Blog [{source_name}]: found {len(source_posts)} recent posts")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Blog fetch error [{source_name}]: {e}")
        return posts

    async def _fetch_source(self, session: aiohttp.ClientSession, source_name: str, cfg: dict) -> List[BlogPost]:
        """Discover article URLs (via sitemap or index page), then fetch each article."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=self.max_age_hours)
        posts = []

        if "sitemap_url" in cfg:
            # Sitemap path: accurate dates from sitemap, no need to parse article HTML for date
            url_date_map = await self._fetch_from_sitemap(session, cfg, cutoff)
            for url, pub_date in list(url_date_map.items())[:15]:
                try:
                    post = await self._fetch_article(session, url, source_name)
                    if post:
                        post.published_at = pub_date
                        post.date_unknown = False
                        posts.append(post)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error fetching article {url}: {e}")
        else:
            # Index page path: discover URLs then fetch articles
            article_urls = set()
            for index_url in cfg["index_urls"]:
                urls = await self._discover_article_urls(session, index_url, cfg)
                article_urls.update(urls)

            for url in list(article_urls)[:15]:
                try:
                    post = await self._fetch_article(session, url, source_name)
                    if post and post.published_at >= cutoff:
                        posts.append(post)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error fetching article {url}: {e}")

        posts.sort(key=lambda p: p.published_at, reverse=True)
        return posts[:5]   # keep 5 most recent

    async def _fetch_from_sitemap(self, session: aiohttp.ClientSession, cfg: dict,
                                   cutoff: datetime) -> dict:
        """Fetch sitemap and return {url: lastmod_date} for recent articles, sorted newest first."""
        try:
            async with session.get(cfg["sitemap_url"]) as resp:
                if resp.status != 200:
                    logger.warning(f"Sitemap fetch failed: {resp.status} for {cfg['sitemap_url']}")
                    return {}
                xml = await resp.text()
        except Exception as e:
            logger.error(f"Sitemap fetch error: {e}")
            return {}

        prefix = cfg.get("sitemap_path_prefix", "")
        entries = re.findall(
            r'<loc>(https?://[^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>', xml
        )

        url_dates = {}
        for url, lastmod in entries:
            from urllib.parse import urlparse
            path = urlparse(url).path
            if prefix and not path.startswith(prefix):
                continue
            try:
                dt = datetime.fromisoformat(lastmod.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= cutoff:
                    url_dates[url] = dt
            except Exception:
                continue

        # Sort newest first
        return dict(sorted(url_dates.items(), key=lambda x: x[1], reverse=True))

    async def _discover_article_urls(self, session: aiohttp.ClientSession, index_url: str, cfg: dict) -> List[str]:
        """Extract article links from an index page."""
        try:
            async with session.get(index_url) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
        except Exception as e:
            logger.error(f"Index page fetch failed {index_url}: {e}")
            return []

        base = cfg["base"]
        found = set()

        # Strategy 1: __NEXT_DATA__ JSON (Next.js SSR)
        next_data = self._extract_next_data(html)
        if next_data:
            urls = self._find_urls_in_json(next_data, base, cfg["link_pattern"])
            found.update(urls)

        # Strategy 2: Regex on raw HTML
        for path in re.findall(cfg["link_pattern"], html):
            url = urljoin(base, path)
            if self._is_valid_article_url(url, base):
                found.add(url)

        return list(found)

    def _extract_next_data(self, html: str) -> Optional[dict]:
        """Extract __NEXT_DATA__ JSON embedded in Next.js pages."""
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _find_urls_in_json(self, data, base: str, pattern: str) -> List[str]:
        """Recursively search JSON for URL-like strings matching our pattern."""
        urls = []
        if isinstance(data, str):
            if re.match(r'/(?:research|news|blog)/[a-z0-9][a-z0-9\-]+$', data):
                url = urljoin(base, data)
                if self._is_valid_article_url(url, base):
                    urls.append(url)
        elif isinstance(data, dict):
            for v in data.values():
                urls.extend(self._find_urls_in_json(v, base, pattern))
        elif isinstance(data, list):
            for item in data:
                urls.extend(self._find_urls_in_json(item, base, pattern))
        return urls

    def _is_valid_article_url(self, url: str, base: str) -> bool:
        """Filter out index/tag/author pages, keep only article URLs."""
        parsed = urlparse(url)
        if not url.startswith(base):
            return False
        path = parsed.path.rstrip("/")
        # Must have at least 2 segments (e.g. /blog/article-name)
        segments = [s for s in path.split("/") if s]
        if len(segments) < 2:
            return False
        # Exclude pagination and generic pages
        last = segments[-1]
        if re.match(r'^\d+$', last):    # page numbers
            return False
        if last in ("blog", "research", "news", "tag", "author", "category"):
            return False
        return True

    async def _fetch_article(self, session: aiohttp.ClientSession, url: str, source_name: str) -> Optional[BlogPost]:
        """Fetch and parse an individual article page."""
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
        except Exception:
            return None

        title = self._extract_title(html)
        if not title:
            return None

        published_at = self._extract_date(html, url)
        date_unknown = published_at is None
        if date_unknown:
            # Include the article but flag it — better to show undated content
            # than silently drop potentially important posts.
            published_at = datetime.now(tz=timezone.utc)
            logger.debug(f"Blog: date unknown for {url}, including with flag")

        author = self._extract_author(html)
        content = self._extract_content(html)

        return BlogPost(
            title=title,
            url=url,
            source=source_name,
            published_at=published_at,
            date_unknown=date_unknown,
            author=author,
            content=content[:3000],
        )

    def _extract_title(self, html: str) -> str:
        # Try <h1>, then <title>
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
        if m:
            return re.sub(r'<[^>]+>', '', m.group(1)).strip()
        m = re.search(r'<title>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
        if m:
            return re.sub(r'<[^>]+>', '', m.group(1)).split('|')[0].strip()
        return ""

    def _extract_date(self, html: str, url: str) -> Optional[datetime]:
        """
        Try multiple strategies to extract the real publication date.
        Returns None if the date cannot be determined — callers must skip such articles
        rather than fabricating a timestamp.
        """
        candidates = []

        def _parse(s: str) -> Optional[datetime]:
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
                return None

        # 1. JSON-LD / schema.org datePublished
        for m in re.finditer(r'"datePublished"\s*:\s*"([^"]+)"', html):
            d = _parse(m.group(1))
            if d:
                candidates.append(d)

        # 2. meta article:published_time (Open Graph)
        for m in re.finditer(r'(?:property|name)="article:published_time"\s+content="([^"]+)"', html):
            d = _parse(m.group(1))
            if d:
                candidates.append(d)

        # 3. __NEXT_DATA__ / JSON fields: publishedAt, published_at, date, createdAt
        for key in (r'"publishedAt"', r'"published_at"', r'"date"', r'"createdAt"', r'"dateModified"'):
            for m in re.finditer(key + r'\s*:\s*"([^"]+)"', html):
                d = _parse(m.group(1))
                if d:
                    candidates.append(d)

        # 4. <time datetime="..."> HTML element
        for m in re.finditer(r'<time[^>]+datetime="([^"]+)"', html, re.IGNORECASE):
            d = _parse(m.group(1))
            if d:
                candidates.append(d)

        # 5. Date in URL path  e.g. /2025/12/article or /2025-12-01-article
        m = re.search(r'/(\d{4})[/-](\d{2})(?:[/-](\d{2}))?', url)
        if m:
            try:
                year, month = int(m.group(1)), int(m.group(2))
                day = int(m.group(3)) if m.group(3) else 1
                if 2020 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                    candidates.append(datetime(year, month, day, tzinfo=timezone.utc))
            except Exception:
                pass

        if not candidates:
            return None   # ← unknown date: caller will skip this article

        # Return the most recent plausible date (filter out future dates)
        now = datetime.now(tz=timezone.utc)
        valid = [d for d in candidates if d <= now]
        return max(valid) if valid else None

    def _extract_author(self, html: str) -> str:
        m = re.search(r'"author"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'<meta\s+name="author"\s+content="([^"]+)"', html)
        if m:
            return m.group(1)
        return "Unknown"

    def _extract_content(self, html: str) -> str:
        """Extract readable text from article body."""
        # Remove script/style blocks
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Try to isolate main article body
        for tag_pattern in [
            r'<article[^>]*>(.*?)</article>',
            r'<main[^>]*>(.*?)</main>',
            r'<div[^>]+class="[^"]*(?:content|article|post|body)[^"]*"[^>]*>(.*?)</div>',
        ]:
            m = re.search(tag_pattern, html, re.DOTALL | re.IGNORECASE)
            if m:
                html = m.group(1)
                break

        # Strip remaining tags and clean whitespace
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'&[a-z]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
