import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Tweet:
    id: str
    text: str
    author_username: str
    author_name: str
    created_at: datetime
    retweet_count: int
    like_count: int
    reply_count: int
    url: str
    entities: Dict

class TwitterFetcher:
    def __init__(self, bearer_token: str, api_key: str, api_secret: str,
                 access_token: str, access_token_secret: str):
        self.bearer_token = bearer_token
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.base_url = "https://api.twitter.com/2"

    async def fetch_tweets_from_accounts(self, accounts: List[str],
                                       keywords: List[str],
                                       hours_back: int = 24) -> List[Tweet]:
        """Fetch tweets from specific accounts containing keywords"""
        tweets = []

        async with aiohttp.ClientSession() as session:
            for account in accounts:
                try:
                    account_tweets = await self._fetch_user_tweets(
                        session, account, keywords, hours_back
                    )
                    tweets.extend(account_tweets)
                    logger.info(f"Fetched {len(account_tweets)} tweets from {account}")

                    # Rate limiting
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Error fetching tweets from {account}: {e}")

        return tweets

    async def _fetch_user_tweets(self, session: aiohttp.ClientSession,
                                username: str, keywords: List[str],
                                hours_back: int) -> List[Tweet]:
        """Fetch tweets for a specific user"""

        # Get user ID from username
        user_id = await self._get_user_id(session, username)
        if not user_id:
            return []

        # Calculate time range
        start_time = datetime.utcnow() - timedelta(hours=hours_back)
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build query parameters
        params = {
            "max_results": 100,
            "tweet.fields": "created_at,public_metrics,entities,author_id",
            "user.fields": "username,name",
            "expansions": "author_id",
            "start_time": start_time_str
        }

        headers = {"Authorization": f"Bearer {self.bearer_token}"}

        url = f"{self.base_url}/users/{user_id}/tweets"

        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                logger.error(f"Twitter API error: {response.status}")
                return []

            data = await response.json()

            if "data" not in data:
                return []

            tweets = []
            users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}

            for tweet_data in data["data"]:
                # Filter by keywords
                if not self._contains_keywords(tweet_data["text"], keywords):
                    continue

                author = users.get(tweet_data["author_id"], {})

                tweet = Tweet(
                    id=tweet_data["id"],
                    text=tweet_data["text"],
                    author_username=author.get("username", ""),
                    author_name=author.get("name", ""),
                    created_at=datetime.fromisoformat(tweet_data["created_at"].replace("Z", "+00:00")),
                    retweet_count=tweet_data["public_metrics"]["retweet_count"],
                    like_count=tweet_data["public_metrics"]["like_count"],
                    reply_count=tweet_data["public_metrics"]["reply_count"],
                    url=f"https://twitter.com/{author.get('username', '')}/status/{tweet_data['id']}",
                    entities=tweet_data.get("entities", {})
                )

                tweets.append(tweet)

            return tweets

    async def _get_user_id(self, session: aiohttp.ClientSession, username: str) -> Optional[str]:
        """Get user ID from username"""
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        params = {"usernames": username.lstrip("@")}

        url = f"{self.base_url}/users/by/username/{username.lstrip('@')}"

        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                logger.error(f"Failed to get user ID for {username}: {response.status}")
                return None

            data = await response.json()
            return data.get("data", {}).get("id")

    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains any of the keywords (case insensitive)"""
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in keywords)

    async def search_recent_tweets(self, query: str, max_results: int = 100) -> List[Tweet]:
        """Search for recent tweets matching a query"""
        tweets = []

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            params = {
                "query": query,
                "max_results": max_results,
                "tweet.fields": "created_at,public_metrics,entities,author_id",
                "user.fields": "username,name",
                "expansions": "author_id"
            }

            url = f"{self.base_url}/tweets/search/recent"

            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    logger.error(f"Twitter search API error: {response.status}")
                    return []

                data = await response.json()

                if "data" not in data:
                    return []

                users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}

                for tweet_data in data["data"]:
                    author = users.get(tweet_data["author_id"], {})

                    tweet = Tweet(
                        id=tweet_data["id"],
                        text=tweet_data["text"],
                        author_username=author.get("username", ""),
                        author_name=author.get("name", ""),
                        created_at=datetime.fromisoformat(tweet_data["created_at"].replace("Z", "+00:00")),
                        retweet_count=tweet_data["public_metrics"]["retweet_count"],
                        like_count=tweet_data["public_metrics"]["like_count"],
                        reply_count=tweet_data["public_metrics"]["reply_count"],
                        url=f"https://twitter.com/{author.get('username', '')}/status/{tweet_data['id']}",
                        entities=tweet_data.get("entities", {})
                    )

                    tweets.append(tweet)

        return tweets