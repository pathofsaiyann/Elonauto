import os
import json
import logging
import asyncio
import re
from datetime import datetime
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from groq import Groq
from dotenv import load_dotenv
from telegram import Bot

import random
import storage

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Ensure FFmpeg is in PATH (Local Windows fallback)
if os.name == 'nt': # Windows only
    ffmpeg_path = r"C:\ffmpeg\ffmpeg-2026-02-18-git-52b676bb29-full_build\bin"
    if os.path.exists(ffmpeg_path) and ffmpeg_path not in os.environ['PATH']:
        os.environ['PATH'] += f";{ffmpeg_path}"
        logger.info(f"Added FFmpeg to PATH: {ffmpeg_path}")

if not GROQ_API_KEY or not TELEGRAM_TOKEN:
    logger.error("Missing API keys in .env")
    exit(1)

client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)

SEARCH_KEYWORDS = [
    "Elon Musk podcast", 
    "AI technology future", 
    "Startup motivation", 
    "Tech billionaire advice"
]

def search_ytdlp_keyword(keyword):
    """Searches YouTube globally for a keyword, returning up to 30 results."""
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            # Removed time filters (e.g., dateafter), allowing old videos.
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Custom search query: ytsearch30 fetches top 30
            search_query = f"ytsearch30:{keyword}"
            info = ydl.extract_info(search_query, download=False)
            
            if 'entries' not in info:
                return []
            
            results = []
            for entry in info['entries']:
                results.append({
                    'id': entry['id'],
                    'title': entry.get('title', ''),
                    'url': entry['url']
                })
            return results
    except Exception as e:
        logger.error(f"Error searching for {keyword}: {e}")
    return []

def get_transcript_text(video_id):
    """Fetches transcript."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        # Combine into a single string with timestamps for context if needed, 
        # but for LLM analysis, we might just want text blocks. 
        # However, to cut, we need to map back to timestamps.
        # Let's verify if we can just feed text and get approx timestamps or feed the whole JSON.
        # Feeding the whole JSON might be too big. 
        # Let's simplify: Feed text chunks with time markers.
        
        full_text = ""
        for t in transcript:
            start = int(t['start'])
            text = t['text']
            # Add timestamp every 30 seconds to help LLM locate
            full_text += f"[{start}s] {text} "
            
        return full_text
    except Exception as e:
        logger.error(f"Error fetching transcript for {video_id}: {e}")
        return None

def analyze_transcript(text):
    """Uses Groq to find the viral segment."""
    prompt = (
        "Analyze this podcast transcript. Find the single most viral, meaningful, and high-energy "
        "30-40 second segment about xAI, Mars, the future of humanity, openai, chatgpt, nvidia, gpu. "
        "Return a JSON object with these exact keys:\n"
        "1. 'start': Start timestamp in HH:MM:SS format.\n"
        "2. 'end': End timestamp in HH:MM:SS format (must be 30-40s after start).\n"
        "3. 'caption': A viral Instagram caption with hooks and hashtags.\n"
        "Output ONLY the valid JSON object. No markdown.\n\n"
        f"Transcript:\n{text[:25000]}" # Limit context window involved
    )
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a viral content editor."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
        )
        content = chat_completion.choices[0].message.content
        content = content.replace('```json', '').replace('```', '').strip()
        return json.loads(content)
    except Exception as e:
        logger.error(f"Groq analysis failed: {e}")
        return None

def time_str_to_seconds(time_str):
    """Converts HH:MM:SS to seconds."""
    try:
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s
    except:
        # Try MM:SS
        try:
            m, s = map(int, time_str.split(':'))
            return m * 60 + s
        except:
            return 0

def download_clip(video_url, start_time, end_time, output_filename="clip.mp4"):
    """Downloads and cuts the clip."""
    start_sec = time_str_to_seconds(start_time)
    end_sec = time_str_to_seconds(end_time)
    
    if end_sec - start_sec < 5: 
        end_sec = start_sec + 30 # Fallback default
        
    logger.info(f"Clipping from {start_sec}s to {end_sec}s")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_filename,
        'download_ranges': yt_dlp.utils.download_range_func(None, [(start_sec, end_sec)]),
        'force_keyframes_at_cuts': True,
        'quiet': False,
        'overwrite': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return output_filename
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return None

async def send_telegram_video(video_path, caption):
    """Sends video to Telegram."""
    try:
        if os.path.exists(video_path):
            logger.info("Sending video to Telegram...")
            with open(video_path, 'rb') as f:
                await bot.send_video(chat_id=TELEGRAM_CHAT_ID, video=f, caption=caption)
            logger.info("Video sent successfully.")
        else:
            logger.error("Video file not found.")
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")

async def run_clipper():
    logger.info("Starting Viral Clipper...")
    
    # 1. Load History STRICTLY
    history = storage.load_history()
    
    # 2. Pick a Random Keyword
    selected_keyword = random.choice(SEARCH_KEYWORDS)
    logger.info(f"Selected Keyword: '{selected_keyword}'")
    
    # 3. Global Search (No time filters)
    logger.info("Searching YouTube...")
    videos = search_ytdlp_keyword(selected_keyword)
    
    found_video = None
    
    # 4. Strict 1-Video Rule: Find the FIRST unseen video
    for video in videos:
        if video['id'] not in history:
            logger.info(f"Fresh match found: {video['title']} (ID: {video['id']})")
            found_video = video
            
            # 5. IMMEDIATELY update history to lock it globally
            history.append(video['id'])
            storage.save_history(history)
            logger.info(f"Video {video['id']} saved to history.json. It will never repeat.")
            
            break # Stop searching, we have our 1 video
        else:
            logger.debug(f"Skipping processed video: {video['id']}")
    
    if not found_video:
        logger.info("No fresh videos found for this keyword today.")
        return

    logger.info("Fetching transcript...")
    transcript_text = get_transcript_text(found_video['id'])
    
    if not transcript_text:
        logger.warn("No transcript available.")
        return

    logger.info("Analyzing with Groq...")
    analysis = analyze_transcript(transcript_text)
    
    if not analysis:
        logger.error("Analysis failed.")
        return
        
    logger.info(f"Segment identified: {analysis['start']} - {analysis['end']}")
    
    clip_filename = f"viral_clip_{found_video['id']}.mp4"
    saved_path = download_clip(found_video['url'], analysis['start'], analysis['end'], clip_filename)
    
    if saved_path:
        caption = f"🎬 *{found_video['title']}*\n\n{analysis['caption']}\n\n🔗 {found_video['url']}"
        await send_telegram_video(saved_path, caption)
        
        # Cleanup
        # os.remove(saved_path)

if __name__ == "__main__":
    asyncio.run(run_clipper())
