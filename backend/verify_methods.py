import os
import sys
sys.path.append('app')

from app.features.finance.excel_processor import ExcelProcessor

# Mock DB
class MockDB:
    def add(self, item): pass
    def flush(self): pass  
    def commit(self): pass

def verify_methods():
    """Verify all required methods exist"""
    print("🔍 Verifying Excel Processor Methods...")
    
    processor = ExcelProcessor(MockDB())
    
    required_methods = [
        'detect_file_type',
        'smart_date_parsing', 
        'safe_decimal',
        'map_cash_book_columns',
        'map_due_bill_columns',
        'map_expenditure_columns',
        'process_file',
        'calculate_quality_score'
    ]
    
    missing_methods = []
    
    for method_name in required_methods:
        if hasattr(processor, method_name):
            print(f"   ✅ {method_name}")
        else:
            print(f"   ❌ {method_name} - MISSING!")
            missing_methods.append(method_name)
    
    if missing_methods:
        print(f"\n❌ {len(missing_methods)} methods are missing!")
        return False
    else:
        print(f"\n✅ All {len(required_methods)} methods are available!")
        return True

if __name__ == "__main__":
    verify_methods()
