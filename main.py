#!/usr/bin/env python3
"""
AI News Aggregator - Main Entry Point

This script orchestrates the daily collection and summarization of AI-related content
from various sources and publishes it to Notion.
"""

import asyncio
import argparse
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from config.settings import settings
from src.scheduler.daily_job import DailyBriefingJob, run_daily_job

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
        self.scheduler = AsyncIOScheduler()
        self.job = DailyBriefingJob()

    def setup_scheduler(self):
        """Setup the daily scheduler"""
        # Parse schedule time
        schedule_hour, schedule_minute = settings.schedule_time.split(':')

        # Create cron trigger for daily execution
        trigger = CronTrigger(
            hour=int(schedule_hour),
            minute=int(schedule_minute),
            timezone=ZoneInfo(settings.timezone)
        )

        # Add job to scheduler
        self.scheduler.add_job(
            run_daily_job,
            trigger=trigger,
            id='daily_briefing',
            name='Daily AI Briefing',
            replace_existing=True
        )

        logger.info(f"Scheduler configured for {settings.schedule_time} {settings.timezone}")

    async def run_once(self, test_mode: bool = False):
        """Run the briefing once"""
        logger.info("Running AI News Aggregator (once)...")

        if test_mode:
            page_id = await self.job.test_run()
        else:
            page_id = await self.job.run_daily_briefing()

        logger.info(f"Briefing completed. Notion page ID: {page_id}")
        return page_id

    def start_scheduler(self):
        """Start the scheduler for continuous operation"""
        self.setup_scheduler()
        self.scheduler.start()
        logger.info("AI News Aggregator scheduler started. Press Ctrl+C to exit.")

        try:
            # Keep the scheduler running
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down scheduler...")
            self.scheduler.shutdown()

async def main():
    parser = argparse.ArgumentParser(description='AI News Aggregator')
    parser.add_argument('--mode', choices=['once', 'schedule', 'test'], default='once',
                       help='Run mode: once (default), schedule (continuous), or test')
    parser.add_argument('--config', type=str, help='Path to config file (optional)')

    args = parser.parse_args()

    aggregator = AINewsAggregator()

    if args.mode == 'schedule':
        # Run in scheduled mode
        aggregator.start_scheduler()
    elif args.mode == 'test':
        # Run in test mode
        logger.info("Running in test mode...")
        await aggregator.run_once(test_mode=True)
    else:
        # Run once
        logger.info("Running in single execution mode...")
        await aggregator.run_once()

if __name__ == "__main__":
    asyncio.run(main())