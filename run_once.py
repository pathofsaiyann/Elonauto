import asyncio
import logging
import news_bot
import clipper
import vc_hunter

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

    # 2. VC Hunter
    logger.info("--- Running VC Hunter ---")
    try:
        await vc_hunter.run_vc_hunter()
    except Exception as e:
        logger.error(f"VC Hunter failed: {e}")


    # 4. Clipper (Optional: Usually high resource, but let's include it)
    logger.info("--- Running Viral Clipper ---")
    try:
        await clipper.run_clipper()
    except Exception as e:
        logger.error(f"Clipper failed: {e}")

    logger.info("✅ GitHub Actions cycle complete.")

if __name__ == "__main__":
    asyncio.run(run_everything_once())
