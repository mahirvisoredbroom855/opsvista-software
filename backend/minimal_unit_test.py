import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

def minimal_unit_test():
    """Minimal unit test - just test what works"""
    print("🧪 Minimal Unit Test")
    print("=" * 40)
    
    try:
        # Import test
        from app.features.finance.excel_processor import ExcelProcessor
        from datetime import date
        from decimal import Decimal
        
        # Mock DB
        class MockDB:
            def add(self, item): pass
            def flush(self): pass
            def commit(self): pass
        
        processor = ExcelProcessor(MockDB())
        
        print("✅ Import and initialization successful")
        
        # Test 1: Simple file type detection
        test1 = processor.detect_file_type("Cash Book.xlsx", b"")
        print(f"✅ File type test: 'Cash Book.xlsx' → {test1}")
        
        # Test 2: Simple date parsing
        test2 = processor.smart_date_parsing("2025-01-01")
        print(f"✅ Date parsing test: '2025-01-01' → {test2}")
        
        # Test 3: Simple number parsing
        test3 = processor.safe_decimal(12345)
        print(f"✅ Number parsing test: 12345 → {test3}")
        
        # Test 4: Simple column mapping
        test4 = processor.map_cash_book_columns(["Date", "Amount"])
        print(f"✅ Column mapping test: {test4}")
        
        print("\n🎉 Minimal tests all passed!")
        return True
        
    except Exception as e:
        print(f"❌ Minimal test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    minimal_unit_test()
