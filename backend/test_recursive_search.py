import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

from app.features.finance.google_drive_service import GoogleDriveService

def test_recursive_file_search():
    """Test recursive search for target files"""
    print("🔍 Testing Recursive File Search...")
    print("=" * 60)
    
    try:
        drive_service = GoogleDriveService()
        
        print("1️⃣ Searching in main folder only...")
        
        # Find base folder
        folder_id = drive_service.find_finance_folder("Md. Mizanur Rahman (PTIL)")
        
        if not folder_id:
            print("❌ PTIL folder not found!")
            return False
        
        # Search main folder only
        main_folder_files = drive_service.list_target_finance_files(folder_id)
        print(f"📁 Files in main folder: {len(main_folder_files)}")
        
        for file in main_folder_files:
            print(f"   ✅ {file['name']}")
        
        print("\n2️⃣ Searching recursively in all subfolders...")
        
        # Search recursively
        all_files_recursive = drive_service.find_target_files_anywhere("Md. Mizanur Rahman (PTIL)")
        print(f"🔍 Files found recursively: {len(all_files_recursive)}")
        
        for file in all_files_recursive:
            folder_info = file.get('parent_folder', 'main')
            print(f"   ✅ {file['name']} (folder: {folder_info})")
        
        print("\n3️⃣ Comparison:")
        print(f"   Main folder only: {len(main_folder_files)} files")
        print(f"   Recursive search: {len(all_files_recursive)} files")
        print(f"   Additional files found: {len(all_files_recursive) - len(main_folder_files)}")
        
        if len(all_files_recursive) > len(main_folder_files):
            print("✅ Recursive search found additional files in subfolders!")
        elif len(all_files_recursive) == len(main_folder_files):
            print("ℹ️ All files are in the main folder")
        else:
            print("⚠️ Something unexpected happened")
        
        # Show which files are where
        print("\n4️⃣ File locations:")
        for file in all_files_recursive:
            folder_id = file.get('parent_folder', 'main')
            folder_name = 'Main PTIL folder' if folder_id == 'main' else f'Subfolder ({folder_id[:8]}...)'
            print(f"   📄 {file['name']}")
            print(f"      📂 Located in: {folder_name}")
        
        print("\n�� Recursive search test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("📋 Recursive File Search Test")
    print("🔍 Finding files in main folder AND subfolders")
    print("=" * 50)
    test_recursive_file_search()
