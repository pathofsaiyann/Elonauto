import os
import shutil
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Load environment variables
load_dotenv()

# Scopes for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_account.json'

def authenticate_drive():
    """Authenticates using the service account and returns the Drive service."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path, folder_id=None):
    """
    Uploads a file to a specific Google Drive folder.
    Ensures quota compliance by explicitly setting parents.
    """
    if folder_id is None:
        folder_id = os.getenv('GDRIVE_FOLDER_ID', "").strip()
    
    if not folder_id:
        print("CRITICAL ERROR: GDRIVE_FOLDER_ID is missing. Cannot upload to Drive.")
        return None

    file_name = os.path.basename(file_path)
    print(f"Attempting to sync '{file_name}' to Folder ID: {folder_id}")

    # 1. Quota Check: See if it exists in THIS folder first
    file_id = get_file_id_by_name(file_name, folder_id)
    
    if file_id:
        print(f"File found (ID: {file_id}). Updating existing file to preserve quota...")
        return update_in_drive(file_path, file_id)

    # 2. Create new with explicit parent metadata
    service = authenticate_drive()
    file_metadata = {
        'name': file_name,
        'parents': [os.getenv('GDRIVE_FOLDER_ID').strip()]
    }
    media = MediaFileUpload(file_path, resumable=True)
    
    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        print(f"SUCCESS: Created in folder {folder_id}. ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        print(f"QUOTA ERROR/FAILURE in Folder {folder_id}: {e}")
        return None

def update_in_drive(file_path, file_id):
    """Updates an existing file on Google Drive."""
    service = authenticate_drive()
    media = MediaFileUpload(file_path, resumable=True)
    try:
        file = service.files().update(
            fileId=file_id,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        print(f"File updated successfully! File ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        print(f"An error occurred during update: {e}")
        return None

def get_file_id_by_name(name, folder_id):
    """Finds a file ID by its name in a specific folder."""
    service = authenticate_drive()
    # Escape single quotes in filename for safety
    safe_name = name.replace("'", "\\'")
    query = f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false"
    try:
        results = service.files().list(
            q=query, 
            fields="files(id)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = results.get('files', [])
        return files[0].get('id') if files else None
    except Exception as e:
        print(f"An error occurred searching for file: {e}")
        return None

def download_from_drive(file_name, local_path, folder_id=None):
    """Downloads a file from Google Drive."""
    if folder_id is None:
        folder_id = os.getenv('GDRIVE_FOLDER_ID', "").strip()
    
    file_id = get_file_id_by_name(file_name, folder_id)
    if not file_id:
        print(f"File {file_name} not found on Drive.")
        return False

    service = authenticate_drive()
    try:
        from googleapiclient.http import MediaIoBaseDownload
        import io
        request = service.files().get_media(
            fileId=file_id,
            supportsAllDrives=True
        )
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        with open(local_path, 'wb') as f:
            f.write(fh.getvalue())
        print(f"File {file_name} downloaded to {local_path}.")
        return True
    except Exception as e:
        print(f"An error occurred during download: {e}")
        return False

def zip_assets(folder_path, output_name):
    """
    Zips a folder and its contents.
    
    Args:
        folder_path (str): Path to the folder to zip.
        output_name (str): The name of the resulting zip file (without .zip extension).
    """
    if not os.path.exists(folder_path):
        print(f"Error: Folder {folder_path} does not exist.")
        return None

    try:
        # shutil.make_archive adds .zip extension automatically
        zip_file_path = shutil.make_archive(output_name, 'zip', folder_path)
        print(f"Folder zipped successfully: {zip_file_path}")
        return zip_file_path
    except Exception as e:
        print(f"An error occurred during zipping: {e}")
        return None

import json

def load_history(filename="history.json"):
    """
    Loads history from Google Drive or local file.
    Ensures a local file exists.
    Returns: list of history items (strings).
    """
    history = []
    
    # Try to download from Drive first
    if download_from_drive(filename, filename):
        try:
            with open(filename, 'r') as f:
                history = json.load(f)
            print(f"History loaded from Drive: {len(history)} items.")
        except Exception as e:
            print(f"Error reading {filename} from disk: {e}")
            history = []
    else:
        print("No history found on Drive. Checking local...")
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    content = f.read().strip()
                    if content:
                        history = json.loads(content)
                    else:
                        history = []
            except Exception as e:
                print(f"Error reading local history: {e}")
                history = []
        else:
            print(f"Initializing new local {filename}")
            with open(filename, 'w') as f:
                json.dump([], f)
            history = []
            
    return history

def save_history(history, filename="history.json"):
    """
    Saves history to local file and uploads to Google Drive.
    """
    try:
        # Save locally
        with open(filename, 'w') as f:
            json.dump(history, f, indent=4)
        
        # Upload to Drive
        upload_to_drive(filename)
        print(f"History saved and uploaded: {len(history)} items.")
    except Exception as e:
        print(f"Error saving history: {e}")

if __name__ == "__main__":
    pass
