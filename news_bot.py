import os
import json
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot, InputMediaPhoto

# Project Modules
import brain

HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {HISTORY_FILE}: {e}")
    return []

def save_history(history):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving {HISTORY_FILE}: {e}")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    logger.error("Telegram credentials missing in .env")
    raise ValueError("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

async def send_text_notification(item):
    """Sends a Strategy Block."""
    try:
        # Construct Strategy Block
        headline = item.get('headline', 'No Headline')
        link = item.get('link', '#')
        source_name = item.get('source_name', 'NewsAPI')
        insta_hook = item.get('insta_hook', 'No caption generated.')
        best_time = item.get('best_time', '09:00 AM EST')
        hashtags = " ".join(item.get('hashtags', []))
        
        caption = (
            f"🔗 Source: <a href='{link}'>{source_name}</a>\n\n"
            f"✍️ <b>Insta Caption</b>:\n{insta_hook}\n\n"
            f"⏰ <b>Best Time to Post</b>: {best_time}\n\n"
            f"#️⃣ <b>Hashtags</b>: {hashtags}"
        )

        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=caption, parse_mode='HTML', disable_web_page_preview=True)
        logger.info("Telegram Strategy Block sent.")

    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")

async def run_news_cycle():
    """Runs a single cycle of the news hunt."""
    logger.info("Starting Global Tech Asset Hunter Cycle...")
    
    # Initialize/Load History locally
    history = load_history()
    
    try:
        logger.info(f"--- Cycle started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        # 1. Brain: Get viral news (Freshness & History Lock applied inside)
        top_stories = brain.process_elon_news(history)
        
        if not top_stories:
            logger.info("No viral news found.")
            return

        for item in top_stories:
            headline = item['headline']
            logger.info(f"Processing viral item (Score {item['score']}): {headline}")
            
            # 2. Delivery: Telegram Strategy Block
            await send_text_notification(item)
            
            # Update History
            history.append(headline)
            if item.get('link'):
                history.append(item['link'])
            save_history(history)
            logger.info("Local history updated.")
        
    except Exception as e:
        logger.error(f"Error in news cycle: {e}")

if __name__ == "__main__":
    asyncio.run(run_news_cycle())
