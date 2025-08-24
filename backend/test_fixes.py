import os
import sys
sys.path.append('app')
import openpyxl

<<<<<<< HEAD

=======
>>>>>>> origin/feat/finances-dashboard
from app.features.finance.excel_processor import ExcelProcessor

# Mock DB
class MockDB:
    def __init__(self):
        self.items = []
    def add(self, item): 
        self.items.append(item)
    def flush(self): pass  
    def commit(self): pass

def test_fixes():
    """Test that all methods exist and basic functionality works"""
    print("🔧 Testing Fixes...")
    print("=" * 50)
    
    try:
        processor = ExcelProcessor(MockDB())
        
        # Test all methods exist
        required_methods = [
            'process_cash_book_sheet',
            'process_due_bill_sheet', 
            'process_expenditure_sheet',
            'map_cash_book_columns',
            'map_due_bill_columns',
            'map_expenditure_columns'
        ]
        
        print("1️⃣ Checking required methods...")
        missing = []
        for method in required_methods:
            if hasattr(processor, method):
                print(f"   ✅ {method}")
            else:
                print(f"   ❌ {method} - MISSING!")
                missing.append(method)
<<<<<<< HEAD

=======
        
>>>>>>> origin/feat/finances-dashboard
        if missing:
            print(f"\n❌ {len(missing)} methods still missing!")
            return False
        
        print("\n2️⃣ Testing column mappings...")
        
        # Test Due Bill mapping (based on your file)
        due_bill_headers = ["SL", "Description of Goods/Payment/Other", "Party Name", "Date", "Bill No", "Quantity", "Unite Prise", "Amount", "Total Amount", "Advance TK", "Due Bill"]
        due_mapping = processor.map_due_bill_columns(due_bill_headers)
        print(f"   Due Bill mapping: {due_mapping}")
        
        # Test Expenditure mapping (based on your file)
        expenditure_headers = ["SL", "Year", "Expenditure", "Expenditure Fixed Cost", "PTIL-Total TK", "LC USD", "Bill USD", "Due USD", "Total USD", "BD TK", "Loss", "Profit"]
        exp_mapping = processor.map_expenditure_columns(expenditure_headers)
        print(f"   Expenditure mapping: {exp_mapping}")
        
        print("\n✅ All fixes appear to be working!")
        return True
        
    except Exception as e:
        print(f"❌ Fix test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_fixes()
