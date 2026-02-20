import os
import json
import logging
import requests
from datetime import datetime, timedelta
from groq import Groq
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "").strip()

if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY not found in environment variables.")
    raise ValueError("Missing GROQ_API_KEY")

if not NEWSAPI_KEY:
    logger.error("NEWSAPI_KEY not found in environment variables.")
    raise ValueError("Missing NEWSAPI_KEY")

client = Groq(api_key=GROQ_API_KEY)

def evaluate_headline(headline):
    """Evaluates a headline using Groq's Llama 3 70B model."""
    # Prepare the prompt for Groq
    prompt = (
        f"Analyze this tech news headline: '{headline}'\n"
        "Return a JSON object with these exact keys:\n"
        "1. 'score': Virality score 0-10 (integer).\n"
        "2. 'sentiment': One word (Positive, Negative, Neutral).\n"
        "3. 'people': List of up to 2 key people mentioned.\n"
        "4. 'companies': List of up to 2 key companies mentioned.\n"
        "5. 'insta_hook': A formatted string for Instagram Caption:\n"
        "   - Line 1: Mind-blowing Hook (e.g., 'Sam Altman just changed the game...').\n"
        "   - Line 2-4: 3 Quick Value-Bombs (The 'What' and 'Why').\n"
        "   - Line 5: Call to Action (Question to boost comments).\n"
        "6. 'best_time': Best time to upload based on category (e.g., '09:00 AM EST').\n"
        "7. 'hashtags': List of 5 niche-specific high-engagement hashtags.\n"
        "Output ONLY the valid JSON object. No markdown."
    )
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Instagram Growth Specialist and Data Scientist."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7, # Slightly higher for creativity in hooks
        )

        response_content = chat_completion.choices[0].message.content
        # robust parsing
        response_content = response_content.replace('```json', '').replace('```', '').strip()
        
        result = json.loads(response_content)
        return result
    except Exception as e:
        logger.error(f"Error evaluating headline '{headline}': {e}")
        return {
            'score': 0, 'sentiment': 'Neutral', 'people': [], 'companies': [], 
            'insta_hook': '', 'best_time': '12:00 PM EST', 'hashtags': []
        }

def process_elon_news(history=None):
    """Main function to scrape, evaluate, and filter headlines using NewsAPI."""
    # Broadened Tech Scope
    queries = ["AI technology", "Startup innovation", "Tech gadgets 2026", "Future tech"]
    
    high_impact_items = []
    
    # URL for NewsAPI
    base_url = "https://newsapi.org/v2/everything"
    
    # Calculate 12-hour window
    from_time = (datetime.now() - timedelta(hours=12)).isoformat()
    
    for query in queries:
        logger.info(f"Fetching headlines for query: {query}")
        
        params = {
            'q': query,
            'apiKey': NEWSAPI_KEY,
            'language': 'en',
            'sortBy': 'popularity',
            'from': from_time, # Freshness Logic
            'pageSize': 5
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            articles = data.get('articles', [])
            
            if not articles:
                logger.warning(f"No results found for {query}")
                continue

            for article in articles:
                headline = article.get('title')
                link = article.get('url')
                date = article.get('publishedAt')
                source_name = article.get('source', {}).get('name', 'Unknown')
                
                # STRICT HISTORY LOCK
                if not headline or '[Removed]' in headline:
                    continue
                    
                if history:
                    # Check both headline and link to be sure
                    if headline in history or link in str(history):
                        continue
                
                logger.info(f"New headline found: {headline}")
                
                # Deep Analysis (Only if passed history lock)
                analysis = evaluate_headline(headline)
                score = analysis.get('score', 0)
                
                if score >= 5: # Lowered threshold to guarantee 1 post/day
                    high_impact_items.append({
                        'score': score,
                        'headline': headline,
                        'sentiment': analysis.get('sentiment', 'Neutral'),
                        'people': analysis.get('people', []),
                        'companies': analysis.get('companies', []),
                        'insta_hook': analysis.get('insta_hook', ''),
                        'best_time': analysis.get('best_time', '09:00 AM EST'),
                        'hashtags': analysis.get('hashtags', []),
                        'link': link,
                        'source_name': source_name,
                        'date': date
                    })
                    
        except Exception as e:
            logger.error(f"NewsAPI error for {query}: {e}")
            continue
    
    # Sort by score desc, return top 3
    high_impact_items.sort(key=lambda x: x['score'], reverse=True)
    return high_impact_items[:3]

if __name__ == "__main__":
    logger.info("Starting Brain script...")
    results = process_elon_news()
    
    if results:
        print("\n--- High Impact Tech News ---")
        print(json.dumps(results, indent=4))
    else:
        print("\nNo viral news found.")
