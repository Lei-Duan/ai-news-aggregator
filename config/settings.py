import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Force reload from .env file
load_dotenv(override=True)

class Settings(BaseSettings):
    # API Keys
    twitter_bearer_token: str = Field(default="", env="TWITTER_BEARER_TOKEN")
    twitter_api_key: str = Field(default="", env="TWITTER_API_KEY")
    twitter_api_secret: str = Field(default="", env="TWITTER_API_SECRET")
    twitter_access_token: str = Field(default="", env="TWITTER_ACCESS_TOKEN")
    twitter_access_token_secret: str = Field(default="", env="TWITTER_ACCESS_TOKEN_SECRET")

    github_token: str = Field(default="", env="GITHUB_TOKEN")

    reddit_client_id: str = Field(default="", env="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", env="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="ai-news-aggregator/1.0", env="REDDIT_USER_AGENT")

    notion_token: str = Field(default="", env="NOTION_TOKEN")
    notion_database_id: str = Field(default="", env="NOTION_DATABASE_ID")

    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")

    # Scheduler Settings
    schedule_time: str = Field(default="09:00", env="SCHEDULE_TIME")
    timezone: str = Field(default="US/Pacific", env="TIMEZONE")

    # Content Filtering
    min_quality_score: float = Field(default=0.7, env="MIN_QUALITY_SCORE")
    max_articles_per_source: int = Field(default=10, env="MAX_ARTICLES_PER_SOURCE")
    summary_max_length: int = Field(default=200, env="SUMMARY_MAX_LENGTH")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/aggregator.log", env="LOG_FILE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()