import os
import sys

def test_method_existence():
    """Simple test to check if methods exist without importing models"""
    print("🔧 Simple Fix Test (No Database)")
    print("=" * 50)
    
    # Check if excel_processor.py exists and has the methods
    processor_file = "app/features/finance/excel_processor.py"
    
    if not os.path.exists(processor_file):
        print("❌ excel_processor.py not found!")
        return False
    
    with open(processor_file, 'r') as f:
        content = f.read()
    
    # Check for required method definitions
    required_methods = [
        'def process_cash_book_sheet',
        'def process_due_bill_sheet', 
        'def process_expenditure_sheet',
        'def map_cash_book_columns',
        'def map_due_bill_columns',
        'def map_expenditure_columns'
    ]
    
    print("1️⃣ Checking method definitions in file...")
    missing = []
    for method in required_methods:
        if method in content:
            print(f"   ✅ {method.replace('def ', '')}")
        else:
            print(f"   ❌ {method.replace('def ', '')} - MISSING!")
            missing.append(method)
    
    # Check if raw_data_id was removed
    print("\n2️⃣ Checking if raw_data_id was removed...")
    if 'raw_data_id=' in content:
        print("   ⚠️ raw_data_id still found in code")
        print("   This will cause database errors")
    else:
        print("   ✅ raw_data_id references removed")
    
    # Check file size (should be substantial with all methods)
    file_size = len(content)
    print(f"\n3️⃣ File analysis:")
    print(f"   File size: {file_size:,} characters")
    print(f"   Lines of code: {content.count('def ')}")
    
    if missing:
        print(f"\n❌ {len(missing)} methods still missing!")
        print("Need to add these methods to excel_processor.py")
        return False
    else:
        print("\n✅ All methods appear to be defined!")
        return True

if __name__ == "__main__":
    test_method_existence()
