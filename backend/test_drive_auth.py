import json
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.discovery import build

def test_drive_connection():
    try:
        # Load credentials
        credentials = service_account.Credentials.from_service_account_file(
            'google_credentials.json',
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        
        # Build Drive service
        service = build('drive', 'v3', credentials=credentials)
        
        # List all files/folders accessible (should only be Finance folder contents)
        results = service.files().list(pageSize=50).execute()
        files = results.get('files', [])
        
        print("✅ Authentication successful!")
        print(f"📁 Found {len(files)} files/folders in Finance directory")
        
        # Show what's in the Finance folder
        if files:
            print("\n📋 Contents of Finance folder:")
            for file in files[:10]:  # Show first 10 items
                file_type = "📁 Folder" if file.get('mimeType') == 'application/vnd.google-apps.folder' else "📄 File"
                print(f"   {file_type}: {file['name']}")
            
            if len(files) > 10:
                print(f"   ... and {len(files) - 10} more items")
        else:
            print("⚠️  No files found. Check folder sharing permissions.")
            
    except Exception as e:
        print(f"❌ Authentication failed: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    test_drive_connection()
