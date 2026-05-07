"""
Twitter/X fetcher — cost-optimized search-based approach.

Why "search" instead of "per-user timeline"?
  Each call to /2/tweets/search/recent costs the same as one timeline read,
  but a single search with `from:u1 OR from:u2 OR ...` returns tweets from
  many users at once. For ~25 curated accounts this collapses ~25 timeline
  calls into 1 search call (~95% reduction in API cost).

Pipeline:
  1. Resolve usernames → user IDs, with a 7-day on-disk cache
     (state/twitter_user_ids.json). Cache hit = 0 API calls for resolution.
  2. Build chunked search queries: `(from:u1 OR from:u2 OR ...) lang:en
     -is:retweet -is:reply` — each chunk stays under 480 chars to fit the
     512-char query limit on the Basic tier.
  3. For each chunk, one /tweets/search/recent call.
  4. Group results by author, keep top MAX_TWEETS_PER_USER per user, sort.
  5. Trending search: 2 merged OR-queries (was 4) using min_faves:5000.

Long tweets: search/recent returns note_tweet via tweet.fields=note_tweet
so >280-char tweets keep full text.

Requires a Bearer Token with Basic tier or higher
(/tweets/search/recent + min_faves operator).
"""

import asyncio
import aiohttp
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_TWEETS_PER_USER = 3
INTER_REQUEST_DELAY = 0.2          # 200ms between API calls (polite)
BATCH_SIZE = 100                    # max usernames per /users/by request

# User-ID cache (avoids the daily /users/by lookup)
USER_ID_CACHE_PATH = Path("state/twitter_user_ids.json")
USER_ID_CACHE_TTL_DAYS = 7

# Search query construction
SEARCH_SUFFIX = " -is:retweet -is:reply lang:en"
SEARCH_QUERY_MAX_LEN = 480          # safety margin under 512-char Basic-tier limit
SEARCH_MAX_RESULTS = 100            # /tweets/search/recent server max per page

# Trending search — minimum engagement to count as "trending"
TRENDING_MIN_LIKES = 5000
TRENDING_MAX_RESULTS = 50           # per merged query (server-filtered by min_faves)


@dataclass
class Tweet:
    id: str
    text: str
    author_username: str
    author_name: str
    author_bio: str
    created_at: datetime
    retweet_count: int
    like_count: int
    reply_count: int
    url: str
    entities: Dict = field(default_factory=dict)
    is_long: bool = False           # True when pulled from note_tweet
    source_type: str = "account"    # "account" = curated list, "trending" = search


class TwitterFetcher:
    def __init__(self, bearer_token: str, **kwargs):
        self.bearer_token = bearer_token
        self.base_url = "https://api.twitter.com/2"
        self._headers = {"Authorization": f"Bearer {bearer_token}"}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def fetch_tweets_from_accounts(
        self,
        accounts: List[str],
        keywords: List[str],
        hours_back: int = 24,
    ) -> List[Tweet]:
        """
        Resolve usernames (cached), then issue ONE search call per
        ~25-account chunk to collect their recent tweets.
        Returns up to MAX_TWEETS_PER_USER per author, sorted by likes desc.
        """
        if not self.bearer_token:
            logger.warning("Twitter: no Bearer Token configured, skipping")
            return []

        clean_handles = [a.lstrip("@") for a in accounts]

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            user_map = await self._get_user_ids(session, clean_handles)
            if not user_map:
                logger.warning("Twitter: could not resolve any user IDs")
                return []

            handles_lower = list(user_map.keys())
            chunks = self._chunk_handles(handles_lower)
            logger.info(
                f"Twitter: {len(handles_lower)}/{len(clean_handles)} accounts resolved, "
                f"split into {len(chunks)} search chunk(s)"
            )

            cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)
            start_time = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

            all_tweets: List[Tweet] = []
            for i, chunk in enumerate(chunks):
                query = self._build_from_query(chunk)
                try:
                    tweets = await self._run_search(
                        session, query, start_time,
                        max_results=SEARCH_MAX_RESULTS,
                        source_type="account",
                    )
                    logger.info(
                        f"Twitter accounts chunk {i+1}/{len(chunks)} "
                        f"({len(chunk)} users): {len(tweets)} tweets"
                    )
                    all_tweets.extend(tweets)
                    await asyncio.sleep(INTER_REQUEST_DELAY)
                except Exception as e:
                    logger.error(f"Twitter accounts chunk {i+1} error: {e}")

        # Group by author, cap per-user, then global sort by likes
        by_user: Dict[str, List[Tweet]] = {}
        for t in all_tweets:
            by_user.setdefault(t.author_username.lower(), []).append(t)

        capped: List[Tweet] = []
        for user_tweets in by_user.values():
            user_tweets.sort(key=lambda t: t.created_at, reverse=True)
            capped.extend(user_tweets[:MAX_TWEETS_PER_USER])

        capped.sort(key=lambda t: t.like_count, reverse=True)
        logger.info(
            f"Twitter accounts: {len(capped)} tweets from {len(by_user)} users "
            f"(API calls: {len(chunks)} search + cache resolve)"
        )
        return capped

    async def search_trending(
        self,
        min_likes: int = TRENDING_MIN_LIKES,
        hours_back: int = 24,
        max_results: int = TRENDING_MAX_RESULTS,
    ) -> List[Tweet]:
        """
        Surface high-engagement AI tweets from across X (not just followed
        accounts). Uses 2 merged OR-queries instead of 4 — same recall
        surface, half the API spend.
        """
        if not self.bearer_token:
            return []

        # NOTE: `min_faves:` operator requires Pro tier ($5K/mo). On Basic tier
        # it 400s. We omit it from the query and filter client-side after fetch.
        # Sorting by relevancy + max_results=100 keeps recall high enough that
        # the post-filter still finds high-engagement tweets.

        # Merged from 4 → 2 queries.
        #   Group A: AI/model/tool/news (incl. AI hashtags)
        #   Group B: indie builder wins (incl. builder hashtags)
        queries = [
            '(LLM OR "AI agent" OR "vibe coding" OR Claude OR "GPT-4o" OR Gemini '
            'OR Llama OR "new model" OR benchmark OR "state of the art" '
            'OR #AI OR #LLM OR #GenAI OR #AIagent OR #claude) '
            'lang:en -is:retweet -is:reply',

            '("build in public" OR "indie hacker" OR "AI SaaS" OR MRR '
            'OR "just launched" OR "just shipped" OR #BuildInPublic OR #agent) '
            'lang:en -is:retweet -is:reply',
        ]

        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)
        start_time = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        all_tweets: List[Tweet] = []
        seen_ids = set()

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for query in queries:
                try:
                    tweets = await self._run_search(
                        session, query, start_time, max_results,
                        source_type="trending",
                    )
                    if tweets:
                        max_lc = max(t.like_count for t in tweets)
                        logger.info(
                            f"Twitter trending search: {len(tweets)} tweets, "
                            f"max likes={max_lc} (gate={min_likes})"
                        )
                    for t in tweets:
                        if t.id not in seen_ids and t.like_count >= min_likes:
                            seen_ids.add(t.id)
                            all_tweets.append(t)
                    await asyncio.sleep(INTER_REQUEST_DELAY)
                except Exception as e:
                    logger.error(f"Twitter trending search error: {e}")

        all_tweets.sort(key=lambda t: t.like_count, reverse=True)
        logger.info(
            f"Twitter trending: {len(all_tweets)} tweets ≥{min_likes} likes "
            f"(API calls: {len(queries)})"
        )
        return all_tweets[:30]

    # ------------------------------------------------------------------ #
    # User-ID cache
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load_user_id_cache() -> dict:
        try:
            if USER_ID_CACHE_PATH.exists():
                with open(USER_ID_CACHE_PATH, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Twitter: cache load failed ({e}), starting fresh")
        return {"version": 1, "users": {}}

    @staticmethod
    def _save_user_id_cache(cache: dict) -> None:
        try:
            USER_ID_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(USER_ID_CACHE_PATH, "w") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Twitter: cache save failed: {e}")

    async def _get_user_ids(
        self, session: aiohttp.ClientSession, handles: List[str]
    ) -> Dict[str, dict]:
        """
        Returns {username_lower: {id, name, username, description}}.
        Hits the on-disk cache first; only resolves missing/stale entries
        via /users/by.
        """
        cache = self._load_user_id_cache()
        users_block = cache.get("users", {})
        now = datetime.now(tz=timezone.utc)
        ttl = timedelta(days=USER_ID_CACHE_TTL_DAYS)

        fresh: Dict[str, dict] = {}
        stale_or_missing: List[str] = []

        for h in handles:
            key = h.lower()
            entry = users_block.get(key)
            if entry:
                cached_at = entry.get("cached_at", "")
                try:
                    ts = datetime.fromisoformat(cached_at)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    fresh_in_ttl = (now - ts) < ttl
                except Exception:
                    fresh_in_ttl = False

                if fresh_in_ttl:
                    if entry.get("tombstone"):
                        # Known-bad handle, skip without API call
                        continue
                    if entry.get("id"):
                        fresh[key] = {
                            "id": entry["id"],
                            "name": entry.get("name", ""),
                            "username": entry.get("username", h),
                            "description": entry.get("description", ""),
                        }
                        continue
            stale_or_missing.append(h)

        if stale_or_missing:
            logger.info(
                f"Twitter: cache hit {len(fresh)}/{len(handles)}, "
                f"resolving {len(stale_or_missing)} via /users/by"
            )
            resolved = await self._batch_resolve_usernames(session, stale_or_missing)
            for username_lower, ud in resolved.items():
                fresh[username_lower] = ud
                users_block[username_lower] = {
                    **ud,
                    "cached_at": now.isoformat(),
                }
            # Negative cache: handles that /users/by failed to resolve get a
            # tombstone so we don't retry every day. Same TTL as live entries.
            unresolved = [h for h in stale_or_missing if h.lower() not in resolved]
            for h in unresolved:
                users_block[h.lower()] = {
                    "id": None,
                    "username": h,
                    "tombstone": True,
                    "cached_at": now.isoformat(),
                }
            if unresolved:
                logger.info(
                    f"Twitter: {len(unresolved)} handles unresolvable, "
                    f"tombstoned for {USER_ID_CACHE_TTL_DAYS}d: {unresolved}"
                )
            cache["users"] = users_block
            self._save_user_id_cache(cache)
        else:
            logger.info(
                f"Twitter: all {len(handles)} user IDs from cache "
                f"(no /users/by call needed)"
            )

        return fresh

    # ------------------------------------------------------------------ #
    # Query helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _chunk_handles(handles: List[str]) -> List[List[str]]:
        """
        Split handles into chunks whose `(from:u1 OR from:u2 ...) <suffix>`
        stays under SEARCH_QUERY_MAX_LEN. Twitter Basic tier = 512-char limit.
        """
        chunks: List[List[str]] = []
        current: List[str] = []
        overhead = len(SEARCH_SUFFIX) + 2   # parentheses
        cur_len = overhead
        for h in handles:
            piece = len(f"from:{h}")
            sep = len(" OR ") if current else 0
            if current and cur_len + sep + piece > SEARCH_QUERY_MAX_LEN:
                chunks.append(current)
                current = [h]
                cur_len = overhead + piece
            else:
                current.append(h)
                cur_len += sep + piece
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _build_from_query(handles: List[str]) -> str:
        return "(" + " OR ".join(f"from:{h}" for h in handles) + ")" + SEARCH_SUFFIX

    # ------------------------------------------------------------------ #
    # Twitter API calls
    # ------------------------------------------------------------------ #

    async def _batch_resolve_usernames(
        self, session: aiohttp.ClientSession, usernames: List[str]
    ) -> Dict[str, dict]:
        """
        GET /2/users/by?usernames=u1,u2,...
        Returns dict: {username_lower: {id, name, username, description}}
        """
        result: Dict[str, dict] = {}
        for i in range(0, len(usernames), BATCH_SIZE):
            chunk = usernames[i : i + BATCH_SIZE]
            params = {
                "usernames": ",".join(chunk),
                "user.fields": "id,name,username,description",
            }
            try:
                async with session.get(
                    f"{self.base_url}/users/by",
                    headers=self._headers,
                    params=params,
                ) as resp:
                    body = await resp.text()
                    if resp.status == 401:
                        logger.error(
                            "Twitter: 401 Unauthorized — check Bearer Token. "
                            "Response: %s", body[:300]
                        )
                        return {}
                    if resp.status == 403:
                        logger.error(
                            "Twitter: 403 Forbidden — Bearer Token likely free-tier "
                            "(Basic $100/mo required). Response: %s", body[:300]
                        )
                        return {}
                    if resp.status != 200:
                        logger.error(
                            "Twitter: /users/by returned %s. Response: %s",
                            resp.status, body[:300]
                        )
                        return {}
                    data = json.loads(body)
                    for user in data.get("data", []):
                        result[user["username"].lower()] = user
            except Exception as e:
                logger.error("Twitter: exception in _batch_resolve_usernames: %s", e)
                return {}
        return result

    async def _run_search(
        self,
        session: aiohttp.ClientSession,
        query: str,
        start_time: str,
        max_results: int,
        source_type: str = "trending",
    ) -> List[Tweet]:
        """One /tweets/search/recent call → list of Tweet objects."""
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "start_time": start_time,
            # account chunks want completeness (recent), trending wants relevance
            "sort_order": "recency" if source_type == "account" else "relevancy",
            "tweet.fields": "created_at,public_metrics,note_tweet,entities,author_id",
            "expansions": "author_id",
            "user.fields": "name,username,description",
        }
        async with session.get(
            f"{self.base_url}/tweets/search/recent",
            headers=self._headers,
            params=params,
        ) as resp:
            if resp.status == 403:
                body = await resp.text()
                logger.warning(
                    "Twitter search: 403 — Basic tier required. Body: %s",
                    body[:200]
                )
                return []
            if resp.status != 200:
                body = await resp.text()
                logger.error(
                    "Twitter search: %s for query: %s | body: %s",
                    resp.status, query[:120], body[:200]
                )
                return []
            data = await resp.json()

        users = {
            u["id"]: u
            for u in data.get("includes", {}).get("users", [])
        }

        tweets: List[Tweet] = []
        for td in data.get("data", []):
            author = users.get(td.get("author_id", ""), {})
            is_long = "note_tweet" in td
            text = td.get("note_tweet", {}).get("text") or td.get("text", "")
            metrics = td.get("public_metrics", {})
            try:
                created = datetime.fromisoformat(td["created_at"].replace("Z", "+00:00"))
            except Exception:
                created = datetime.now(tz=timezone.utc)
            username = author.get("username", "")
            tweets.append(Tweet(
                id=td["id"],
                text=text,
                author_username=username,
                author_name=author.get("name", ""),
                author_bio=author.get("description", ""),
                created_at=created,
                retweet_count=metrics.get("retweet_count", 0),
                like_count=metrics.get("like_count", 0),
                reply_count=metrics.get("reply_count", 0),
                url=f"https://x.com/{username}/status/{td['id']}",
                entities=td.get("entities", {}),
                is_long=is_long,
                source_type=source_type,
            ))
        return tweets

    # ------------------------------------------------------------------ #
    # Misc
    # ------------------------------------------------------------------ #

    @staticmethod
    def _matches_keywords(text: str, keywords: List[str]) -> bool:
        tl = text.lower()
        return any(kw.lower() in tl for kw in keywords)
