"""
Twitter/X fetcher — mirrors the follow-builders approach:
  1. One batch API call to resolve all usernames → user IDs
  2. Per-user timeline fetch with 200ms delay
  3. Use note_tweet.text for tweets longer than 280 chars
  4. Exclude retweets and replies
  5. Max 3 tweets per user, must be within last 24 hours

Requires only a Bearer Token (read-only, free API is NOT enough —
needs Basic tier $100/mo for /users/:id/tweets).
If the token is missing or the tier is insufficient, the fetcher
logs a warning and returns empty results without crashing.
"""

import asyncio
import aiohttp
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_TWEETS_PER_USER = 3
INTER_REQUEST_DELAY = 0.2   # 200ms between per-user requests (polite)
BATCH_SIZE = 100             # max usernames per /users/by request


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
    is_long: bool = False     # True when pulled from note_tweet


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
        Main entry point.
        Batch-resolves usernames, then fetches each user's timeline.
        Returns tweets matching at least one keyword, sorted by like_count desc.
        """
        if not self.bearer_token:
            logger.warning("Twitter: no Bearer Token configured, skipping")
            return []

        clean_handles = [a.lstrip("@") for a in accounts]

        async with aiohttp.ClientSession() as session:
            user_map = await self._batch_resolve_usernames(session, clean_handles)
            if not user_map:
                logger.warning("Twitter: could not resolve any user IDs")
                return []

            logger.info(f"Twitter: resolved {len(user_map)}/{len(clean_handles)} user IDs")

            cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)
            all_tweets: List[Tweet] = []

            for username, user_data in user_map.items():
                try:
                    tweets = await self._fetch_user_timeline(
                        session, user_data, cutoff, keywords
                    )
                    all_tweets.extend(tweets)
                    await asyncio.sleep(INTER_REQUEST_DELAY)
                except Exception as e:
                    logger.error(f"Twitter: error fetching @{username}: {e}")

        # Sort by engagement (like_count) descending
        all_tweets.sort(key=lambda t: t.like_count, reverse=True)
        logger.info(f"Twitter: fetched {len(all_tweets)} tweets total")
        return all_tweets

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    async def _batch_resolve_usernames(
        self, session: aiohttp.ClientSession, usernames: List[str]
    ) -> Dict[str, dict]:
        """
        Single API call: GET /2/users/by?usernames=u1,u2,...
        Returns dict: { username_lower: {id, name, username, description} }
        """
        result = {}
        # Process in batches of BATCH_SIZE (API limit)
        for i in range(0, len(usernames), BATCH_SIZE):
            chunk = usernames[i : i + BATCH_SIZE]
            params = {
                "usernames": ",".join(chunk),
                "user.fields": "id,name,username,description",
            }
            async with session.get(
                f"{self.base_url}/users/by",
                headers=self._headers,
                params=params,
            ) as resp:
                if resp.status == 401:
                    logger.error("Twitter: 401 Unauthorized — check Bearer Token")
                    return {}
                if resp.status == 403:
                    logger.error(
                        "Twitter: 403 Forbidden — Bearer Token likely on free tier "
                        "(Basic $100/mo required for timeline reads)"
                    )
                    return {}
                if resp.status != 200:
                    logger.error(f"Twitter: /users/by returned {resp.status}")
                    return {}
                data = await resp.json()
                for user in data.get("data", []):
                    result[user["username"].lower()] = user
        return result

    async def _fetch_user_timeline(
        self,
        session: aiohttp.ClientSession,
        user: dict,
        cutoff: datetime,
        keywords: List[str],
    ) -> List[Tweet]:
        """Fetch up to MAX_TWEETS_PER_USER recent original tweets from a user."""
        params = {
            "max_results": 10,       # fetch more, then filter down
            "tweet.fields": "created_at,public_metrics,note_tweet,entities",
            "expansions": "author_id",
            "user.fields": "name,username,description",
            "exclude": "retweets,replies",
            "start_time": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        url = f"{self.base_url}/users/{user['id']}/tweets"
        async with session.get(url, headers=self._headers, params=params) as resp:
            if resp.status == 403:
                logger.warning(
                    f"Twitter: 403 on @{user.get('username')} — "
                    "Basic tier may be required"
                )
                return []
            if resp.status != 200:
                logger.error(f"Twitter: timeline error {resp.status} for @{user.get('username')}")
                return []
            data = await resp.json()

        raw_tweets = data.get("data", [])
        tweets: List[Tweet] = []

        for td in raw_tweets:
            if len(tweets) >= MAX_TWEETS_PER_USER:
                break

            # Use note_tweet.text for long tweets (> 280 chars)
            is_long = "note_tweet" in td
            text = td.get("note_tweet", {}).get("text") or td["text"]

            if keywords and not self._matches_keywords(text, keywords):
                continue

            created = datetime.fromisoformat(td["created_at"].replace("Z", "+00:00"))

            metrics = td.get("public_metrics", {})
            tweet = Tweet(
                id=td["id"],
                text=text,
                author_username=user.get("username", ""),
                author_name=user.get("name", ""),
                author_bio=user.get("description", ""),
                created_at=created,
                retweet_count=metrics.get("retweet_count", 0),
                like_count=metrics.get("like_count", 0),
                reply_count=metrics.get("reply_count", 0),
                url=f"https://x.com/{user.get('username', '')}/status/{td['id']}",
                entities=td.get("entities", {}),
                is_long=is_long,
            )
            tweets.append(tweet)

        return tweets

    def _matches_keywords(self, text: str, keywords: List[str]) -> bool:
        tl = text.lower()
        return any(kw.lower() in tl for kw in keywords)
