import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

from app.features.finance.google_drive_service import GoogleDriveService
from app.features.finance.excel_processor import ExcelProcessor

# Enhanced mock database that tracks what's happening
class DetailedMockDB:
    def __init__(self):
        self.raw_records = []
        self.fact_records = []
        self.commits = 0
        self.flushes = 0
    
    def add(self, item):
        item_type = type(item).__name__
        if 'Raw' in item_type:
            self.raw_records.append(item)
            print(f"   📝 Added Raw Record: {item_type}")
        else:
            self.fact_records.append(item)
            print(f"   💾 Added Fact Record: {item_type}")
    
    def flush(self):
        self.flushes += 1
        print(f"   💾 Database flush #{self.flushes}")
    
    def commit(self):
        self.commits += 1
        print(f"   ✅ Database commit #{self.commits}")

def test_excel_integration():
    """Test Excel processor with real Google Drive files"""
    print("🔗 Excel Processor Integration Tests")
    print("=" * 60)
    
    try:
        # Initialize services
        drive_service = GoogleDriveService()
        mock_db = DetailedMockDB()
        processor = ExcelProcessor(mock_db)
        
        print("1️⃣ Connecting to Google Drive...")
        folder_id = drive_service.find_finance_folder("Md. Mizanur Rahman (PTIL)")
        
        if not folder_id:
            print("❌ Cannot find PTIL folder!")
            return False
        
        print(f"✅ Connected to PTIL folder")
        
        print("\n2️⃣ Getting target files...")
        target_files = drive_service.list_target_finance_files(folder_id)
        
        if not target_files:
            print("❌ No target files found!")
            return False
        
        print(f"✅ Found {len(target_files)} target files")
        
        # Test each file type
        results = {}
        
        print("\n3️⃣ Testing each file...")
        for i, file in enumerate(target_files, 1):
            file_name = file['name']
            print(f"\n📊 Testing File {i}/{len(target_files)}: {file_name}")
            print("-" * 50)
            
            try:
                # Download file
                print("   📥 Downloading...")
                file_content = drive_service.download_file(file['id'])
                
                if not file_content:
                    print("   ❌ Download failed!")
                    results[file_name] = "download_failed"
                    continue
                
                print(f"   ✅ Downloaded: {len(file_content):,} bytes")
                
                # Test file type detection
                print("   🔍 Detecting file type...")
                file_type = processor.detect_file_type(file_name, file_content)
                print(f"   📋 Detected: {file_type}")
                
                # Reset mock DB for this file
                mock_db.raw_records.clear()
                mock_db.fact_records.clear()
                mock_db.commits = 0
                mock_db.flushes = 0
                
                # Process the file
                print("   ⚙️ Processing...")
                result = processor.process_file(file_content, file_name, i)
                
                # Analyze results
                if result['status'] == 'success':
                    stats = result['stats']
                    print(f"   ✅ SUCCESS!")
                    print(f"      File type: {result['file_type']}")
                    print(f"      Rows processed: {stats['rows_processed']}")
                    print(f"      Successful: {stats['rows_successful']}")
                    print(f"      Failed: {stats['rows_failed']}")
                    print(f"      Raw records created: {len(mock_db.raw_records)}")
                    print(f"      Fact records created: {len(mock_db.fact_records)}")
                    print(f"      Database commits: {mock_db.commits}")
                    
                    # Show sample data
                    if mock_db.fact_records:
                        sample = mock_db.fact_records[0]
                        print(f"      Sample transaction: {getattr(sample, 'amount_bdt', 'N/A')} BDT")
                    
                    if stats['errors']:
                        print(f"      Sample error: {stats['errors'][0]}")
                    
                    results[file_name] = "success"
                    
                else:
                    print(f"   ❌ FAILED: {result.get('error')}")
                    results[file_name] = f"failed: {result.get('error')}"
                
            except Exception as e:
                print(f"   💥 EXCEPTION: {str(e)}")
                results[file_name] = f"exception: {str(e)}"
        
        # Overall summary
        print(f"\n📊 Integration Test Summary:")
        print(f"   Files tested: {len(target_files)}")
        
        success_count = sum(1 for result in results.values() if result == "success")
        print(f"   Successful: {success_count}")
        print(f"   Failed: {len(results) - success_count}")
        
        print(f"\n📋 Detailed Results:")
        for file_name, result in results.items():
            status_icon = "✅" if result == "success" else "❌"
            print(f"   {status_icon} {file_name}: {result}")
        
        if success_count == len(target_files):
            print("\n🎉 All integration tests passed!")
            return True
        else:
            print(f"\n⚠️ {len(target_files) - success_count} files failed processing")
            return False
        
    except Exception as e:
        print(f"❌ Integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_excel_integration()
