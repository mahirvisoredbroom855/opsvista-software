import os
import sys
from dotenv import load_dotenv

# Add app directory to path
sys.path.append('app')

load_dotenv()

from app.features.finance.google_drive_service import GoogleDriveService

def test_google_drive_connection():
    """Test Google Drive service functionality"""
    print("🔍 Testing Google Drive Integration...")
    print("=" * 60)
    
    try:
        # Initialize service
        print("1️⃣ Connecting to Google Drive...")
        drive_service = GoogleDriveService()
        
        # Test connection
        print("2️⃣ Testing connection...")
        connection_test = drive_service.test_connection()
        
        if connection_test['connected']:
            print("✅ Google Drive connection successful!")
            print(f"   Test time: {connection_test['test_time']}")
        else:
            print("❌ Google Drive connection failed!")
            print(f"   Error: {connection_test.get('error')}")
            return False
        
        # Find finance folder
        print("\n3️⃣ Looking for Finance folder...")
        folder_id = drive_service.find_finance_folder("Md. Mizanur Rahman (PTIL)")
        
        if folder_id:
            print(f"✅ Found Finance folder: {folder_id}")
        else:
            print("❌ Finance folder not found!")
            print("   Make sure to share your Finance folder with the service account")
            return False
        
        # List Excel files
        print("\n4️⃣ Listing Excel files...")
        excel_files = drive_service.list_excel_files(folder_id)
        
        print(f"✅ Found {len(excel_files)} Excel files:")
        for i, file in enumerate(excel_files[:5], 1):  # Show first 5 files
            print(f"   {i}. {file['name']}")
            print(f"      Modified: {file['modified_time']}")
            print(f"      Size: {file['size']} bytes")
        
        if len(excel_files) > 5:
            print(f"   ... and {len(excel_files) - 5} more files")
        
        # Test quota info
        print("\n5️⃣ Checking Google Drive quota...")
        quota_info = drive_service.get_quota_info()
        
        if quota_info:
            usage_gb = quota_info.get('usage', 0) / (1024**3)
            limit_gb = quota_info.get('limit', 0) / (1024**3)
            print(f"✅ Drive usage: {usage_gb:.2f} GB / {limit_gb:.2f} GB")
        
        print("\n🎉 All Google Drive tests passed!")
        return True
        
    except FileNotFoundError as e:
        print(f"❌ Credentials file not found: {str(e)}")
        print("   Make sure google_credentials.json is in backend/ directory")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    test_google_drive_connection()








