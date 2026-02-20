import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_account.json'

def authenticate():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def clean_trash():
    print("Authenticating with Google Drive Service Account...")
    try:
        drive_service = authenticate()
        print("Emptying trash to clear storage quota...")
        
        # Execute the exact command requested
        drive_service.files().emptyTrash().execute()
        
        print("Trash Emptied Successfully")
        print("Google Drive quota should now be restored.")
    except Exception as e:
        print(f"Failed to empty trash: {e}")

if __name__ == "__main__":
    clean_trash()
