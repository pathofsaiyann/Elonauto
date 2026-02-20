import os
import json
import logging
import requests
import asyncio
from datetime import datetime, timedelta
from groq import Groq
from dotenv import load_dotenv
from telegram import Bot, InputMediaPhoto

# Project Modules
import hunter
import storage

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not all([GROQ_API_KEY, SERPER_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
    logger.error("Missing API keys in .env")
    exit(1)

client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)

def search_vc_news():
    """Searches for VC funding news using Serper."""
    url = "https://google.serper.dev/news"
    # Target specific funding keywords
    # "Series A", "Series B", "raised", "funding", "venture capital"
    # Limit to last 24 hours naturally by Google News, but we can verify date
    payload = json.dumps({
        "q": "startup raised funding OR \"Series A\" OR \"Series B\" OR \"Venture Capital\"",
        "num": 10,
        "tbs": "qdr:d" # Past 24 hours
    })
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()
        return response.json().get("news", [])
    except Exception as e:
        logger.error(f"Serper Search Error: {e}")
        return []

def analyze_deal(article):
    """Uses Groq to extract deal details and filter by amount."""
    headline = article.get('title', '')
    snippet = article.get('snippet', '')
    
    prompt = (
        f"Analyze this VC news:\nHeadline: {headline}\nSnippet: {snippet}\n\n"
        "Extract the following in JSON:\n"
        "1. 'company': Company name.\n"
        "2. 'amount': Amount raised in USD (integer). Return 0 if not found/unclear.\n"
        "3. 'round': Funding round (e.g., Series A, Seed).\n"
        "4. 'founder': Key founder name (if mentioned, else 'Founder').\n"
        "5. 'investors': Top investor name (or 'Venture Capital').\n"
        "6. 'summary': One sentence punchy summary.\n"
        "Output ONLY valid JSON."
    )
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a Venture Capital Analyst."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
        )
        content = chat_completion.choices[0].message.content
        content = content.replace('```json', '').replace('```', '').strip()
        data = json.loads(content)
        
        # Filter > $10M
        if data.get('amount', 0) > 10000000:
            return data
            
    except Exception as e:
        logger.error(f"Groq Analysis Error: {e}")
        
    return None

async def send_vc_alert(deal, assets, article_url):
    """Sends a Telegram VC Alert."""
    try:
        media_group = []
        # We generally expect subject_1 (Founder) and company_logo
        # hunter returns: bg_context, subject_1, subject_2, company_logo
        
        keys = ['subject_1', 'company_logo']
        for key in keys:
            path = assets.get(key)
            if path and os.path.exists(path):
                with open(path, 'rb') as f:
                    media_group.append(InputMediaPhoto(media=f.read()))
        
        # Caption
        amount_str = f"${deal['amount']:,}"
        caption = (
            f"💸 **VC ALERT: {deal['company']} raises {amount_str}**\n\n"
            f"🚀 **Round**: {deal['round']}\n"
            f"👤 **Founder**: {deal['founder']}\n"
            f"🏦 **Investor**: {deal['investors']}\n\n"
            f"📝 *{deal['summary']}*\n\n"
            f"🔗 [Read More]({article_url})"
        )
        
        if media_group:
            await bot.send_media_group(chat_id=TELEGRAM_CHAT_ID, media=media_group, caption=caption, parse_mode='Markdown')
        else:
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=caption, parse_mode='Markdown')
            
        logger.info(f"Sent VC Alert for {deal['company']}")
        
    except Exception as e:
        logger.error(f"Telegram Error: {e}")

async def run_vc_hunter():
    logger.info("Starting VC Hunter...")
    
    history = storage.load_history()
    
    articles = search_vc_news()
    
    if not articles:
        logger.info("No recent VC news found.")
        return

    for article in articles:
        # Check history first (by Link or Title) to save Groq tokens
        if article.get('link') in history or article.get('title') in history:
            continue

        deal = analyze_deal(article)
        if deal:
            # Check history again (by Company Name)
            if deal['company'] in history:
                logger.info(f"Skipping {deal['company']} (Already in history)")
                continue

            logger.info(f"High Value Deal Found: {deal['company']} - ${deal['amount']}")
            
            # Use Hunter to get assets
            people = [deal['founder']] if deal['founder'] != 'Founder' else []
            companies = [deal['company']]
            
            headline_query = f"{deal['company']} {deal['round']} Funding"
            
            assets = hunter.hunt_assets(headline_query, people, companies)
            
            await send_vc_alert(deal, assets, article.get('link', '#'))
            
            # Update History
            history.append(deal['company'])
            if article.get('link'):
                history.append(article['link'])
            storage.save_history(history)
            
            # Throttle
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_vc_hunter())
