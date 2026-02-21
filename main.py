import time
import logging
import schedule
import asyncio
from datetime import datetime
import pytz

# Project Modules
import news_bot

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Scheduler")

def run_news_job():
    """Wrapper to run the async news cycle."""
    logger.info("⏳ Starting scheduled News Cycle...")
    try:
        asyncio.run(news_bot.run_news_cycle())
        logger.info("✅ News Cycle completed successfully.")
    except Exception as e:
        logger.error(f"❌ News Cycle failed: {e}")

def start_scheduler():
    logger.info("🚀 Tech News Scheduler Started")
    
    # 1. News Bot: Every 8 hours
    schedule.every(8).hours.do(run_news_job)
    logger.info("📅 Scheduled: News Bot every 8 hours.")
    

    # Run immediately on startup? 
    # User didn't ask to run immediately, but typically you want one run to verify.
    # Let's run News Bot immediately once to ensure it's working, or just wait.
    # "Run news_bot.py every 8 hours." -> implies starting now?
    # Usually better to start the first job immediately or wait. 
    # I'll stick to the schedule to be precise, but user might want immediate feedback.
    # Let's run news_bot immediately for instant gratification / check.
    # run_news_job() 
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    start_scheduler()
