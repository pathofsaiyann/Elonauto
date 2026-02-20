import asyncio
import logging
import news_bot

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GH_Actions")

async def run_everything_once():
    """Executes all bot modules once for a scheduled GitHub Action run."""
    logger.info("🚀 Starting GitHub Actions execution cycle...")
    
    # 1. News Bot
    logger.info("--- Running News Bot ---")
    try:
        await news_bot.run_news_cycle()
    except Exception as e:
        logger.error(f"News Bot failed: {e}")

    logger.info("✅ GitHub Actions cycle complete.")

if __name__ == "__main__":
    asyncio.run(run_everything_once())
