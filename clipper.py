import os
import json
import logging
import asyncio
import re
from datetime import datetime
import yt_dlp
import subprocess
from groq import Groq
from dotenv import load_dotenv
from telegram import Bot

import random

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
    "Sam Altman interview", 
    "Jeff Bezos advice", 
    "Jensen Huang speech", 
    "Mark Zuckerberg interview", 
    "Satya Nadella tech", 
    "Naval Ravikant podcast", 
    "Peter Thiel interview"
]

def search_ytdlp_keyword(keyword, date_filter=None):
    """Searches YouTube globally for a keyword, returning up to 30 results."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'extractor_args': {'youtube': {'player_client': ['ios', 'android']}},
        }
        if date_filter:
            ydl_opts['dateafter'] = date_filter
            
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
    """Fetches auto-generated subtitles using yt-dlp and reads the .vtt file."""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        temp_vtt = f"temp_{video_id}"
        
        ydl_opts = {
            'skip_download': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'outtmpl': temp_vtt,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['ios', 'android']}},
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # yt-dlp auto-appends language code, e.g., temp_VIDEOID.en.vtt
        vtt_file = f"{temp_vtt}.en.vtt"
        
        if not os.path.exists(vtt_file):
            logger.warning(f"No auto-subtitles generated for {video_id}")
            return None
            
        # Read and parse VTT
        full_text = ""
        with open(vtt_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                # Basic cleaning of VTT metadata and formatting
                if '-->' in line or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:') or not line.strip():
                    continue
                clean_line = re.sub(r'<[^>]+>', '', line).strip() # Remove tags like <c>
                if clean_line:
                    full_text += clean_line + " "
                    
        # Cleanup
        os.remove(vtt_file)
        return full_text
        
    except Exception as e:
        logger.error(f"Error fetching transcript via yt-dlp for {video_id}: {e}")
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
    """Downloads and cuts the clip using raw FFmpeg subprocess and yt-dlp direct stream URL."""
    start_sec = time_str_to_seconds(start_time)
    end_sec = time_str_to_seconds(end_time)
    
    duration = end_sec - start_sec
    if duration < 5: 
        duration = 30 # Fallback default
        
    logger.info(f"Clipping exactly {duration}s starting from {start_time}")
    
    try:
        # 1. Get direct stream URL via yt-dlp
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['ios', 'android']}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info['url']
            
        # 2. Raw FFmpeg subprocess execution
        command = [
            'ffmpeg',
            '-ss', str(start_sec),
            '-i', stream_url,
            '-t', str(duration),
            '-c', 'copy', # Ultra-fast stream copy mapping
            '-y', # Overwrite exactly
            output_filename
        ]
        
        logger.info(f"Running FFmpeg: {' '.join(command)}")
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if os.path.exists(output_filename):
            return output_filename
        else:
            logger.error("FFmpeg completed but output file missing.")
            return None
            
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg Subprocess error: {e.stderr.decode()}")
        return None
    except Exception as e:
        logger.error(f"Download/Cut failed: {e}")
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
    
    # 1. Load History STRICTLY locally
    history = load_history()
    
    # 2. Pick a Random Keyword
    selected_keyword = random.choice(SEARCH_KEYWORDS)
    logger.info(f"Selected Keyword: '{selected_keyword}'")
    
    # 3. First pass: recent videos (last 7 days)
    logger.info("Searching YouTube for recent videos (last 7 days)...")
    videos = search_ytdlp_keyword(selected_keyword, date_filter='today-7days')
    
    found_video = None
    
    # 4. Strict 1-Video Rule: Find the FIRST unseen video WITH A TRANSCRIPT
    for video in videos:
        if video['id'] not in history:
            logger.info(f"Recent fresh match found: {video['title']} (ID: {video['id']})")
            
            logger.info("Fetching transcript...")
            transcript_text = get_transcript_text(video['id'])
            
            if not transcript_text:
                logger.warning(f"No transcript available for {video['id']}. Skipping to next video.")
                continue # Transcript failed (e.g., disabled), try next video!
                
            # SUCCESS! We found a fresh video with a working transcript
            found_video = video
            break
            
    # 5. Fallback pass: any age
    if not found_video:
        logger.info("No fresh recent videos found. Falling back to older videos...")
        videos = search_ytdlp_keyword(selected_keyword, date_filter=None)
        
        for video in videos:
            if video['id'] not in history:
                logger.info(f"Older fresh match found: {video['title']} (ID: {video['id']})")
                
                logger.info("Fetching transcript...")
                transcript_text = get_transcript_text(video['id'])
                
                if not transcript_text:
                    logger.warning(f"No transcript available for {video['id']}. Skipping to next video.")
                    continue
                    
                # SUCCESS!
                found_video = video
                break

    if not found_video:
        logger.info("No viable videos (with transcripts) found for this keyword today.")
        return
        
    # IMMEDIATELY update history to lock it globally so it won't repeat
    history.append(found_video['id'])
    save_history(history)
    logger.info(f"Video {found_video['id']} saved to local history.json. It will never repeat.")

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
        
        # Cleanup local file
        try:
            os.remove(saved_path)
            logger.info(f"Deleted local clip: {saved_path}")
        except Exception as e:
            logger.error(f"Failed to delete {saved_path}: {e}")

if __name__ == "__main__":
    asyncio.run(run_clipper())
