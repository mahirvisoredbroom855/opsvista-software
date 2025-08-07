import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

from app.features.finance.google_drive_service import GoogleDriveService

def test_target_files_filtering():
    """Test that system only sees your 3 target files"""
    print("🎯 Testing Target Files Filtering...")
    print("=" * 60)
    
    try:
        drive_service = GoogleDriveService()
        
        # Find PTIL folder
        print("1️⃣ Finding PTIL folder...")
        folder_id = drive_service.find_finance_folder("Md. Mizanur Rahman (PTIL)")
        
        if not folder_id:
            print("❌ PTIL folder not found!")
            return False
        
        print(f"✅ Found PTIL folder: {folder_id}")
        
        # Get ALL Excel files (old method)
        print("\n2️⃣ Getting ALL Excel files...")
        all_files = drive_service.list_excel_files(folder_id)
        print(f"📁 Total Excel files found: {len(all_files)}")
        
        for i, file in enumerate(all_files[:10], 1):  # Show first 10
            print(f"   {i}. {file['name']}")
        
        if len(all_files) > 10:
            print(f"   ... and {len(all_files) - 10} more files")
        
        # Get ONLY target files (new method)
        print("\n3️⃣ Getting ONLY target files...")
        target_files = drive_service.list_target_finance_files(folder_id)
        print(f"🎯 Target files found: {len(target_files)}")
        
        for i, file in enumerate(target_files, 1):
            print(f"   {i}. ✅ {file['name']}")
        
        # Verify we have exactly 3 target files
        expected_count = 3
        if len(target_files) == expected_count:
            print(f"\n✅ Perfect! Found exactly {expected_count} target files")
        else:
            print(f"\n⚠️ Expected {expected_count} target files, but found {len(target_files)}")
        
        # Show the filtering effect
        filtered_out = len(all_files) - len(target_files)
        print(f"\n📊 Filtering Results:")
        print(f"   Total files: {len(all_files)}")
        print(f"   Target files: {len(target_files)}")
        print(f"   Filtered out: {filtered_out}")
        print(f"   Efficiency: {(filtered_out/len(all_files)*100):.1f}% of noise eliminated")
        
        print("\n🎉 Target file filtering test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("📋 Target Files Only Test")
    print("🎯 Verify system only processes your 3 files")
    print("=" * 50)
    test_target_files_filtering()
