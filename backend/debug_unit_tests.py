import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

from datetime import date, datetime
from decimal import Decimal

# Mock database for unit testing
class MockDB:
    def __init__(self):
        self.items = []
        self.committed = False
    
    def add(self, item):
        self.items.append(item)
    
    def flush(self):
        pass
    
    def commit(self):
        self.committed = True

def debug_unit_tests():
    """Debug what's failing in unit tests"""
    print("🔍 Debugging Unit Test Failures")
    print("=" * 60)
    
    try:
        # Test import first
        print("1️⃣ Testing imports...")
        try:
            from app.features.finance.excel_processor import ExcelProcessor
            print("   ✅ ExcelProcessor imported successfully")
        except Exception as e:
            print(f"   ❌ Import failed: {str(e)}")
            return False
        
        # Initialize processor
        print("\n2️⃣ Initializing processor...")
        try:
            mock_db = MockDB()
            processor = ExcelProcessor(mock_db)
            print("   ✅ Processor initialized successfully")
        except Exception as e:
            print(f"   ❌ Initialization failed: {str(e)}")
            return False
        
        # Test each function individually
        print("\n3️⃣ Testing individual functions...")
        
        # Test file type detection
        print("   🔍 Testing file type detection...")
        try:
            result = processor.detect_file_type("1.Cash Book_2025.xlsx", b"dummy content")
            print(f"      ✅ detect_file_type works: {result}")
        except Exception as e:
            print(f"      ❌ detect_file_type failed: {str(e)}")
        
        # Test date parsing
        print("   📅 Testing date parsing...")
        try:
            result = processor.smart_date_parsing("01.06.2025")
            print(f"      ✅ smart_date_parsing works: {result}")
            
            # Test different inputs
            test_dates = ["01.06.2025", "2025-06-01", "", None, "invalid"]
            for test_date in test_dates:
                try:
                    result = processor.smart_date_parsing(test_date)
                    print(f"         '{test_date}' → {result}")
                except Exception as e:
                    print(f"         '{test_date}' → ERROR: {str(e)}")
                    
        except Exception as e:
            print(f"      ❌ smart_date_parsing failed: {str(e)}")
        
        # Test number parsing
        print("   🔢 Testing number parsing...")
        try:
            result = processor.safe_decimal(40225)
            print(f"      ✅ safe_decimal works: {result}")
            
            # Test different inputs
            test_numbers = [40225, "40,225", "", None, "abc"]
            for test_num in test_numbers:
                try:
                    result = processor.safe_decimal(test_num)
                    print(f"         '{test_num}' → {result}")
                except Exception as e:
                    print(f"         '{test_num}' → ERROR: {str(e)}")
                    
        except Exception as e:
            print(f"      ❌ safe_decimal failed: {str(e)}")
        
        # Test column mapping
        print("   ��️ Testing column mapping...")
        try:
            headers = ["Date", "Cash Received", "Factory", "Particulars"]
            result = processor.map_cash_book_columns(headers)
            print(f"      ✅ map_cash_book_columns works: {result}")
        except Exception as e:
            print(f"      ❌ map_cash_book_columns failed: {str(e)}")
        
        # Test due bill mapping
        try:
            headers = ["SL", "Description", "Party Name", "Date", "Total Amount", "Due Bill"]
            result = processor.map_due_bill_columns(headers)
            print(f"      ✅ map_due_bill_columns works: {result}")
        except Exception as e:
            print(f"      ❌ map_due_bill_columns failed: {str(e)}")
        
        print("\n✅ Debug completed - check above for specific failures!")
        return True
        
    except Exception as e:
        print(f"❌ Overall debug failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_unit_tests()
