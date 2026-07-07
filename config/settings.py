import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)


class Settings:
    # API Keys
    twitter_bearer_token: str = os.getenv("TWITTER_BEARER_TOKEN", "")

    github_token: str = os.getenv("GITHUB_TOKEN", "")

    notion_token: str = os.getenv("NOTION_TOKEN", "")
    notion_database_id: str = os.getenv("NOTION_DATABASE_ID", "")

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Scheduler
    schedule_time: str = os.getenv("SCHEDULE_TIME", "09:00")
    timezone: str = os.getenv("TIMEZONE", "US/Pacific")

    # Content filtering
    min_quality_score: float = float(os.getenv("MIN_QUALITY_SCORE", "0.7"))
    max_articles_per_source: int = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "10"))
    summary_max_length: int = int(os.getenv("SUMMARY_MAX_LENGTH", "200"))

    # Email notification (optional)
    email_sender: str = os.getenv("GMAIL_USER", "")
    email_password: str = os.getenv("GMAIL_APP_PASSWORD", "")
    email_recipients: str = os.getenv("EMAIL_RECIPIENTS", "")  # comma-separated

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "logs/aggregator.log")


settings = Settings()
