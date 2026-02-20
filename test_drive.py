import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_account.json'

def authenticate():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def test_drive():
    folder_id = os.getenv('GDRIVE_FOLDER_ID', "").strip()
    
    if not folder_id:
        print("ERROR: GDRIVE_FOLDER_ID is missing or empty.")
        return

    # Mask the ID for safety, showing only the first 5 characters
    masked_id = folder_id[:5] + "*" * (len(folder_id) - 5) if len(folder_id) > 5 else "*****"
    print(f"Testing Drive access for Folder ID: {masked_id}")

    try:
        service = authenticate()
        
        # Create a tiny text file in memory
        file_content = b"This is a test file to verify Drive permissions and quota."
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='text/plain', resumable=True)
        
        file_metadata = {
            'name': 'test.txt',
            'parents': [folder_id]
        }
        
        print("Attempting to create file...")
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        print(f"SUCCESS! test.txt created with ID: {file.get('id')}")
        
    except Exception as e:
        print("\n--- EXACT ERROR MESSAGE ---")
        print(f"Failed to create file in folder {masked_id}.")
        print(f"Error Details:\n{e}")
        print("---------------------------\n")

if __name__ == "__main__":
    test_drive()
