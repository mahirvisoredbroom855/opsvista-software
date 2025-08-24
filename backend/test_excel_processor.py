import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

from app.features.finance.excel_processor import ExcelProcessor
from app.features.finance.google_drive_service import GoogleDriveService
from app.core.supabase_client import get_supabase_session

def test_excel_processing():
    """Test Excel processing with real Google Drive files"""
    print("🧪 Testing Excel Processing Engine...")
    print("=" * 60)
    
    try:
        # Get database session
        db = get_supabase_session()
        
        # Initialize services
        drive_service = GoogleDriveService()
        excel_processor = ExcelProcessor(db)
        
        # Get list of Excel files
        print("1️⃣ Getting Excel files from Google Drive...")
        folder_id = drive_service.find_finance_folder("Md. Mizanur Rahman (PTIL)")
        excel_files = drive_service.list_excel_files(folder_id)
        
        if not excel_files:
            print("❌ No Excel files found!")
            return False
        
        print(f"✅ Found {len(excel_files)} Excel files")
        
        # Test processing first file
        test_file = excel_files[0]
        print(f"\n2️⃣ Testing processing: {test_file['name']}")
        
        # Download file
        print("   📥 Downloading file...")
        file_content = drive_service.download_file(test_file['id'])
        
        if not file_content:
            print("❌ Failed to download file!")
            return False
        
        print(f"   ✅ Downloaded: {len(file_content)} bytes")
        
        # Test file type detection
        print("   🔍 Detecting file type...")
        file_type = excel_processor.detect_file_type(test_file['name'], file_content)
        print(f"   📊 Detected type: {file_type}")
        
        # Test date parsing
        print("   📅 Testing date parsing...")
        test_dates = ["01.06.2025", "2025-06-01", 44927.0, "invalid"]
        for test_date in test_dates:
            parsed = excel_processor.smart_date_parsing(test_date)
            print(f"   '{test_date}' → {parsed}")
        
        # Test number parsing
        print("   🔢 Testing number parsing...")
        test_numbers = [40225, "40,225", "40225.50", "", None]
        for test_num in test_numbers:
            parsed = excel_processor.safe_decimal(test_num)
            print(f"   '{test_num}' → {parsed}")
        
        print("\n🎉 Excel processor tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    test_excel_processing()
