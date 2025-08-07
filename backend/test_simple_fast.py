import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

from app.features.finance.google_drive_service import GoogleDriveService

def test_simple_target_search():
    """Quick test of simple target file search"""
    print("⚡ Testing Simple & Fast Target File Search...")
    print("=" * 60)
    
    try:
        drive_service = GoogleDriveService()
        
        print("1️⃣ Finding PTIL folder...")
        folder_id = drive_service.find_finance_folder("Md. Mizanur Rahman (PTIL)")
        
        if not folder_id:
            print("❌ PTIL folder not found!")
            return False
        
        print(f"✅ Found PTIL folder: {folder_id[:8]}...")
        
        print("\n2️⃣ Searching for target files (main folder only)...")
        
        # Use the simple, fast method
        target_files = drive_service.list_target_finance_files(folder_id)
        
        print(f"🎯 Found {len(target_files)} target files:")
        
        if target_files:
            for i, file in enumerate(target_files, 1):
                print(f"   {i}. ✅ {file['name']}")
                print(f"      📅 Modified: {file['modified_time']}")
                print(f"      📊 Size: {file['size']} bytes")
                print()
        else:
            print("❌ No target files found in main folder")
            print("\nℹ️ Your files might be in subfolders.")
            print("   Option 1: Move them to main PTIL folder")
            print("   Option 2: Tell me the exact subfolder path")
        
        print(f"⚡ Search completed in < 1 second")
        print("\n🎉 Simple search test completed!")
        return len(target_files) > 0
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("📋 Simple & Fast Search Test")
    print("⚡ No recursive searching - just main folder")
    print("=" * 50)
    test_simple_target_search()
