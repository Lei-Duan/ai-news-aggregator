#!/usr/bin/env python3
"""
AI News Aggregator - Main Entry Point

This script orchestrates the daily collection and summarization of AI-related content
from various sources and publishes it to Notion. Scheduling is handled by the
GitHub Actions cron workflow; this entry point only runs single executions.
"""

import asyncio
import argparse
import logging

from config.settings import settings
from src.scheduler.daily_job import DailyBriefingJob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class AINewsAggregator:
    def __init__(self):
        self.job = DailyBriefingJob()

    async def run_once(self, test_mode: bool = False):
        """Run the briefing once"""
        logger.info("Running AI News Aggregator (once)...")

        if test_mode:
            page_id = await self.job.test_run()
        else:
            page_id = await self.job.run_daily_briefing()

        logger.info(f"Briefing completed. Notion page ID: {page_id}")
        return page_id

async def main():
    parser = argparse.ArgumentParser(description='AI News Aggregator')
    parser.add_argument('--mode', choices=['once', 'test'], default='once',
                       help='Run mode: once (default) or test')

    args = parser.parse_args()

    aggregator = AINewsAggregator()

    if args.mode == 'test':
        logger.info("Running in test mode...")
        await aggregator.run_once(test_mode=True)
    else:
        logger.info("Running in single execution mode...")
        await aggregator.run_once()

if __name__ == "__main__":
    asyncio.run(main())
