import time
import logging
import schedule
import asyncio
from datetime import datetime
import pytz

# Project Modules
import news_bot
import clipper
import vc_hunter
import paper_hunter

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

def run_clipper_job():
    """Wrapper to run the async clipper."""
    logger.info("⏳ Starting scheduled Viral Clipper...")
    try:
        asyncio.run(clipper.run_clipper())
        logger.info("✅ Viral Clipper completed successfully.")
    except Exception as e:
        logger.error(f"❌ Viral Clipper failed: {e}")

def run_vc_job():
    """Wrapper to run the async VC Hunter."""
    logger.info("⏳ Starting scheduled VC Hunter...")
    try:
        asyncio.run(vc_hunter.run_vc_hunter())
        logger.info("✅ VC Hunter completed successfully.")
    except Exception as e:
        logger.error(f"❌ VC Hunter failed: {e}")

def run_paper_job():
    """Wrapper to run the async Paper Hunter."""
    logger.info("⏳ Starting scheduled Paper Hunter...")
    try:
        asyncio.run(paper_hunter.run_paper_hunter())
        logger.info("✅ Paper Hunter completed successfully.")
    except Exception as e:
        logger.error(f"❌ Paper Hunter failed: {e}")

def start_scheduler():
    """Start the global scheduler for all automated bots.
    
    This function configures recurring jobs using the ``schedule`` library and
    logs each registration:
    
    * **News Bot** – runs every 8 hours.
    * **Viral Clipper** – runs daily at 21:00 IST.
    * **Paper Hunter** – runs daily at 10:00.
    
    After scheduling, it enters an infinite loop that checks for pending jobs
    every
    logger.info("🚀 Global Tech Asset Hunter Scheduler Started")
    
    # 1. News Bot: Every 8 hours
    schedule.every(8).hours.do(run_news_job)
    logger.info("📅 Scheduled: News Bot every 8 hours.")
    
    # 2. Viral Clipper: Every day at 9:00 PM IST
    schedule.every().day.at("21:00").do(run_clipper_job)
    logger.info("📅 Scheduled: Viral Clipper daily at 21:00.")

    # 3. VC Hunter: Every 12 hours
    schedule.every(12).hours.do(run_vc_job)
    logger.info("📅 Scheduled: VC Hunter every 12 hours.")
    
    # 4. Paper Hunter: Every day at 10:00 AM
    schedule.every().day.at("10:00").do(run_paper_job)
    logger.info("📅 Scheduled: Paper Hunter daily at 10:00.")

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
