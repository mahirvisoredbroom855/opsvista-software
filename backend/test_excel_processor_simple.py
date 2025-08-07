import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

from app.features.finance.google_drive_service import GoogleDriveService

# Mock database session for testing
class MockDBSession:
    """Mock database session for testing"""
    def __init__(self):
        self.added_items = []
        self.committed = False
    
    def add(self, item):
        self.added_items.append(item)
        print(f"📝 Mock DB: Added {type(item).__name__}")
    
    def flush(self):
        print("💾 Mock DB: Flushed to database")
    
    def commit(self):
        self.committed = True
        print("✅ Mock DB: Committed transaction")
    
    def close(self):
        print("🔒 Mock DB: Session closed")

def test_excel_processing_logic():
    """Test Excel processing logic without database"""
    print("🧪 Testing Excel Processing Logic (No Database)...")
    print("=" * 60)
    
    try:
        # Import after path setup
        from app.features.finance.excel_processor import ExcelProcessor
        
        # Create mock database session
        mock_db = MockDBSession()
        
        # Initialize Excel processor with mock DB
        excel_processor = ExcelProcessor(mock_db)
        print("✅ Excel processor initialized")
        
        # Test file type detection
        print("\n1️⃣ Testing file type detection...")
        test_files = [
            "1.Cash Book_2025.xlsx",
            "Cash Party Due Bill_2024-2025.xlsx", 
            "PTIL Expenditure LC & Other 2019-2020-2021-22-23-24.xlsx",
            "Unknown File.xlsx"
        ]
        
        for test_file in test_files:
            file_type = excel_processor.detect_file_type(test_file, b"dummy content")
            print(f"   '{test_file}' → {file_type}")
        
        # Test date parsing
        print("\n2️⃣ Testing date parsing...")
        test_dates = [
            "01.06.2025",    # Your format
            "2025-06-01",    # ISO format
            "01/06/2025",    # Slash format
            44927.0,         # Excel number
            "",              # Empty
            None,            # None
            "invalid"        # Invalid
        ]
        
        for test_date in test_dates:
            parsed = excel_processor.smart_date_parsing(test_date)
            print(f"   '{test_date}' → {parsed}")
        
        # Test number parsing
        print("\n3️⃣ Testing number parsing...")
        test_numbers = [
            40225,           # Integer
            "40,225",        # With comma
            "40225.50",      # Decimal string
            " 40225 ",       # With spaces
            "",              # Empty
            None,            # None
            "abc123"         # Mixed
        ]
        
        for test_num in test_numbers:
            parsed = excel_processor.safe_decimal(test_num)
            print(f"   '{test_num}' → {parsed}")
        
        # Test with real Google Drive file (if available)
        print("\n4️⃣ Testing with real Google Drive file...")
        try:
            drive_service = GoogleDriveService()
            folder_id = drive_service.find_finance_folder("Md. Mizanur Rahman (PTIL)")
            
            if folder_id:
                excel_files = drive_service.list_excel_files(folder_id)
                
                if excel_files:
                    # Test with first file
                    test_file = excel_files[0]
                    print(f"   📥 Downloading: {test_file['name']}")
                    
                    file_content = drive_service.download_file(test_file['id'])
                    
                    if file_content:
                        print(f"   📊 File size: {len(file_content)} bytes")
                        
                        # Test file type detection with real content
                        file_type = excel_processor.detect_file_type(test_file['name'], file_content)
                        print(f"   🔍 Detected type: {file_type}")
                        
                        # Test actual processing (without saving to database)
                        print(f"   ⚙️ Testing processing pipeline...")
                        result = excel_processor.process_file(file_content, test_file['name'], 1)
                        
                        print(f"   📊 Processing result: {result['status']}")
                        if result['status'] == 'success':
                            stats = result['stats']
                            print(f"   ✅ Rows processed: {stats['rows_processed']}")
                            print(f"   ✅ Successful: {stats['rows_successful']}")
                            print(f"   ❌ Failed: {stats['rows_failed']}")
                        else:
                            print(f"   ❌ Error: {result.get('error')}")
                    else:
                        print("   ❌ Failed to download file")
                else:
                    print("   ❌ No Excel files found")
            else:
                print("   ❌ PTIL folder not found")
                
        except Exception as e:
            print(f"   ⚠️ Google Drive test skipped: {str(e)}")
        
        print(f"\n📊 Mock Database Summary:")
        print(f"   Items added: {len(mock_db.added_items)}")
        print(f"   Committed: {mock_db.committed}")
        
        print("\n🎉 Excel processing logic tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("📋 Excel Processor Logic Test")
    print("🎯 Testing without database dependencies")
    print("=" * 50)
    test_excel_processing_logic()
