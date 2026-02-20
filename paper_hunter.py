import os
import logging
import asyncio
import arxiv
from groq import Groq
from dotenv import load_dotenv
from telegram import Bot

# Project Modules
import storage

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not all([GROQ_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
    logger.error("Missing API keys in .env")
    exit(1)

client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)

def fetch_arxiv_papers():
    """Fetches top 5 latest AI papers."""
    logger.info("Fetching ArXiv papers...")
    try:
        # Search for cs.AI, sort by submitted date descending
        # Ensure we ask for a bit more in case of duplicates in history
        search = arxiv.Search(
            query="cat:cs.AI",
            max_results=10, 
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        papers = []
        for result in search.results():
            papers.append({
                'title': result.title,
                'abstract': result.summary,
                'link': result.entry_id, 
                'date': result.published.strftime("%Y-%m-%d")
            })
        return papers
    except Exception as e:
        logger.error(f"ArXiv Error: {e}")
        return []

def summarize_abstract(abstract):
    """Uses Groq to summarize abstract into one simple sentence."""
    prompt = (
        f"Summarize why this research matters in exactly one simple, punchy sentence (max 20 words).\n\n"
        f"Abstract: {abstract}"
    )
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful research assistant."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq Summary Error: {e}")
        return "Summary unavailable."

async def send_daily_digest(papers):
    """Sends the formatted list to Telegram."""
    if not papers:
        logger.info("No papers to send.")
        return

    message = "🎓 **Daily AI Paper TL;DR**\n\n"
    
    for i, paper in enumerate(papers, 1):
        summary = summarize_abstract(paper['abstract'])
        message += (
            f"{i}. [{paper['title']}]({paper['link']})\n"
            f"💡 *{summary}*\n\n"
        )
    
    try:
        # Split if too long (Telegram limit 4096)
        if len(message) > 4000:
            message = message[:4000] + "..."
            
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID, 
            text=message, 
            parse_mode='Markdown', 
            disable_web_page_preview=True
        )
        logger.info("Daily Digest sent.")
        return True
    except Exception as e:
        logger.error(f"Telegram Error: {e}")
        return False

async def run_paper_hunter():
    logger.info("Starting Paper Hunter...")
    
    history = storage.load_history()
    
    all_papers = fetch_arxiv_papers()
    if not all_papers:
        return

    new_papers = []
    for paper in all_papers:
        if paper['link'] not in history:
            new_papers.append(paper)
            if len(new_papers) >= 5: # Limit to top 5 new ones
                break
    
    if not new_papers:
        logger.info("No new papers found (all in history).")
        return

    if await send_daily_digest(new_papers):
        # Update history only if sent successfully
        for paper in new_papers:
            history.append(paper['link'])
        storage.save_history(history)

if __name__ == "__main__":
    asyncio.run(run_paper_hunter())
