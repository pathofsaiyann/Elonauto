import os
import logging
import requests
import shutil
import json
from pathlib import Path
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

if not SERPER_API_KEY:
    logger.error("SERPER_API_KEY not found in environment variables.")
    raise ValueError("Missing SERPER_API_KEY")

def download_image_from_url(url, output_path):
    """Downloads an image from a direct URL."""
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        
        with open(output_path, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        
        logger.info(f"Downloaded: {output_path}")
        return str(output_path)
    except Exception as e:
        logger.warning(f"Failed to download {url}: {e}")
        return None

def serper_image_search(query, output_dir, filename_prefix):
    """Searches for a high-res image using Serper and downloads the first valid one."""
    url = "https://google.serper.dev/images"
    
    # Payload for High-Res images
    payload = json.dumps({
        "q": query,
        "tbs": "isz:l", # Large images
        "num": 5 # Fetch top 5 to have fallbacks
    })
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()
        results = response.json().get("images", [])
        
        for i, img in enumerate(results):
            image_url = img.get("imageUrl")
            if not image_url:
                continue
                
            # Try to determine extension or default to .jpg
            ext = ".jpg"
            if ".png" in image_url.lower(): ext = ".png"
            if ".webp" in image_url.lower(): ext = ".webp"
            
            final_name = f"{filename_prefix}{ext}"
            final_path = output_dir / final_name
            
            # Attempt download
            if download_image_from_url(image_url, final_path):
                return str(final_path)
                
        logger.warning(f"No valid images found/downloaded for query: {query}")
        return None
            
    except Exception as e:
        logger.error(f"Serper API error: {e}")
        return None

def cleanup_old_hunts():
    """Attempts to remove old hunt directories."""
    try:
        base_root = Path("assets")
        if not base_root.exists():
            return
            
        for path in base_root.glob("temp_hunt_*"):
            if path.is_dir():
                try:
                    shutil.rmtree(path)
                except Exception:
                    # Ignore errors, likely locked
                    pass
    except Exception:
        pass

def hunt_assets(headline, people, companies):
    """
    Hunts for 4 specific high-res assets based on the news item.
    Returns a dictionary of paths.
    """
    # Cleanup old runs (best effort)
    cleanup_old_hunts()
    
    # Use unique directory to avoid file locks
    import time
    timestamp = int(time.time())
    base_dir = Path(f"assets/temp_hunt_{timestamp}")
    base_dir.mkdir(parents=True, exist_ok=True)
    
    assets = {}
    
    # 1. High-Res Abstract Background
    # "1 High-res abstract background related to the tech"
    tech_topic = companies[0] if companies else "Future Technology"
    bg_query = f"{tech_topic} abstract technology background 4k wallpaper -text"
    assets['bg_context'] = serper_image_search(bg_query, base_dir, "bg_abstract")
    
    # 2. High-Res Portrait 1 (Main Subject)
    # "2 High-res portraits of the main subject (imagesize: large)"
    # We'll try to find 2 different ones if we have 1 person, or 1 each if we have 2 people.
    if len(people) > 0:
        p1 = people[0]
        assets['subject_1'] = serper_image_search(f"{p1} portrait high resolution photography -text", base_dir, "subject_1")
        
        if len(people) > 1:
            p2 = people[1]
            assets['subject_2'] = serper_image_search(f"{p2} portrait high resolution photography -text", base_dir, "subject_2")
        else:
            # Get a second different one for the same person? Or just use company as fallback.
            # "identify the 2 main people involved... fetch 2 High-res portraits of the main subject"
            # If brain only found 1 person, fetch 2 images of them.
            assets['subject_2'] = serper_image_search(f"{p1} close up portrait high quality -text", base_dir, "subject_2")
    else:
        # Fallback to Company if no people
        c_name = companies[0] if companies else "Tech CEO"
        assets['subject_1'] = serper_image_search(f"{c_name} ceo portrait -text", base_dir, "subject_1")
        assets['subject_2'] = serper_image_search(f"{c_name} headquarters building high res -text", base_dir, "subject_2")

    # 3. High-Res Company Logo
    # "1 High-res company logo (Transparent PNG)"
    if len(companies) > 0:
        c1 = companies[0]
        assets['company_logo'] = serper_image_search(f"{c1} logo transparent png", base_dir, "company_logo")
    else:
        assets['company_logo'] = serper_image_search("Tech News logo transparent png", base_dir, "company_logo")

    return assets

if __name__ == "__main__":
    # Test
    # Need to mock requests or just run it if keys are set
    pass
