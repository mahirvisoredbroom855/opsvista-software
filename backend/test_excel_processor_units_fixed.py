import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

from app.features.finance.excel_processor import ExcelProcessor
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

def test_excel_processor_units():
    """Test individual Excel processor functions"""
    print("🧪 Excel Processor Unit Tests (Fixed)")
    print("=" * 60)
    
    # Initialize processor
    mock_db = MockDB()
    processor = ExcelProcessor(mock_db)
    
    print("1️⃣ Testing File Type Detection...")
    test_files = [
        ("1.Cash Book_2025.xlsx", "cash_book"),
        ("Cash Party Due Bill_2024-2025.xlsx", "party_due_bill"),
        ("PTIL Expenditure LC & Other 2019-2020-2021-22-23-24.xlsx", "expenditure_summary"),
        ("Random File.xlsx", "unknown"),
        ("Another Cash Book 2024.xlsx", "cash_book"),
        ("Due Bill March.xlsx", "party_due_bill")
    ]
    
    passed = 0
    for file_name, expected in test_files:
        result = processor.detect_file_type(file_name, b"dummy content")
        status = "✅" if result == expected else "❌"
        print(f"   {status} '{file_name}' → {result} (expected: {expected})")
        if result == expected:
            passed += 1
    
    print(f"   📊 File type detection: {passed}/{len(test_files)} passed")
    
    print("\n2️⃣ Testing Date Parsing...")
    test_dates = [
        ("01.06.2025", date(2025, 6, 1)),
        ("2025-06-01", date(2025, 6, 1)),
        ("01/06/2025", date(2025, 6, 1)),
        ("1.6.2025", date(2025, 6, 1)),
        (44927.0, date(2023, 1, 1)),  # Excel date number
        (45000.0, date(2023, 2, 23)), # Another Excel date
        ("", None),
        (None, None),
        ("invalid", None),
        ("abc123", None)
    ]
    
    passed_dates = 0
    for test_input, expected in test_dates:
        result = processor.smart_date_parsing(test_input)
        status = "✅" if result == expected else "❌"
        print(f"   {status} '{test_input}' → {result} (expected: {expected})")
        if result == expected:
            passed_dates += 1
    
    print(f"   📊 Date parsing: {passed_dates}/{len(test_dates)} passed")
    
    print("\n3️⃣ Testing Number Parsing...")
    test_numbers = [
        (40225, Decimal('40225')),
        ("40,225", Decimal('40225')),
        ("40225.50", Decimal('40225.50')),
        (" 40225 ", Decimal('40225')),
        ("40225.00", Decimal('40225.00')),
        ("", None),
        (None, None),
        ("abc", None),
        ("123abc456", Decimal('123456')),  # Extract numbers
        ("-500", Decimal('-500')),
        ("1,000,000.50", Decimal('1000000.50'))
    ]
    
    passed_numbers = 0
    for test_input, expected in test_numbers:
        result = processor.safe_decimal(test_input)
        status = "✅" if result == expected else "❌"
        print(f"   {status} '{test_input}' → {result} (expected: {expected})")
        if result == expected:
            passed_numbers += 1
    
    print(f"   📊 Number parsing: {passed_numbers}/{len(test_numbers)} passed")
    
    print("\n4️⃣ Testing Column Mapping...")
    
    # Test Cash Book headers
    print("   📊 Cash Book Column Mapping:")
    cash_book_headers = ["Date", "Cash Received", "Factory", "Factory Cr", "Head off", "Total", "Particulars"]
    
    try:
        mapping = processor.map_cash_book_columns(cash_book_headers)
        
        expected_mapping = {
            'date': 0,
            'cash_received': 1,
            'factory': 2,
            'particulars': 6,
            'total': 5
        }
        
        cash_mapping_correct = True
        for key, expected_idx in expected_mapping.items():
            actual_idx = mapping.get(key)
            status = "✅" if actual_idx == expected_idx else "❌"
            print(f"      {status} {key}: {actual_idx} (expected: {expected_idx})")
            if actual_idx != expected_idx:
                cash_mapping_correct = False
        
    except Exception as e:
        print(f"      ❌ Cash Book mapping failed: {str(e)}")
        cash_mapping_correct = False
    
    # Test Due Bill headers
    print("   💰 Due Bill Column Mapping:")
    due_bill_headers = ["SL", "Description", "Party Name", "Date", "Bill No", "Qty", "Unit Price", "Total Amount", "Advance Tk", "Due Bill"]
    
    try:
        mapping = processor.map_due_bill_columns(due_bill_headers)
        
        expected_mapping = {
            'sl': 0,
            'party_name': 2,
            'date': 3,
            'description': 1,
            'total_amount': 7,
            'due_bill': 9
        }
        
        due_mapping_correct = True
        for key, expected_idx in expected_mapping.items():
            actual_idx = mapping.get(key)
            status = "✅" if actual_idx == expected_idx else "❌"
            print(f"      {status} {key}: {actual_idx} (expected: {expected_idx})")
            if actual_idx != expected_idx:
                due_mapping_correct = False
        
    except Exception as e:
        print(f"      ❌ Due Bill mapping failed: {str(e)}")
        due_mapping_correct = False
    
    # Test Expenditure headers
    print("   📈 Expenditure Column Mapping:")
    expenditure_headers = ["Year", "Total Expenditure", "Revenue", "Profit/Loss"]
    
    try:
        mapping = processor.map_expenditure_columns(expenditure_headers)
        
        expected_mapping = {
            'year': 0,
            'expenditure': 1,
            'revenue': 2,
            'profit_loss': 3
        }
        
        exp_mapping_correct = True
        for key, expected_idx in expected_mapping.items():
            actual_idx = mapping.get(key)
            status = "✅" if actual_idx == expected_idx else "❌"
            print(f"      {status} {key}: {actual_idx} (expected: {expected_idx})")
            if actual_idx != expected_idx:
                exp_mapping_correct = False
        
    except Exception as e:
        print(f"      ❌ Expenditure mapping failed: {str(e)}")
        exp_mapping_correct = False
    
    # Calculate overall results
    mapping_tests_passed = sum([cash_mapping_correct, due_mapping_correct, exp_mapping_correct])
    print(f"   📊 Column mapping: {mapping_tests_passed}/3 passed")
    
    # Overall summary
    total_individual_tests = len(test_files) + len(test_dates) + len(test_numbers)
    total_individual_passed = passed + passed_dates + passed_numbers
    total_tests = total_individual_tests + 3  # 3 mapping tests
    total_passed = total_individual_passed + mapping_tests_passed
    
    print(f"\n📊 Unit Test Summary:")
    print(f"   Individual function tests: {total_individual_passed}/{total_individual_tests}")
    print(f"   Column mapping tests: {mapping_tests_passed}/3")
    print(f"   Total tests: {total_passed}/{total_tests}")
    print(f"   Success rate: {(total_passed/total_tests)*100:.1f}%")
    
    if total_passed == total_tests:
        print("🎉 All unit tests passed!")
        return True
    else:
        print("⚠️ Some unit tests failed - check above for details")
        return False

if __name__ == "__main__":
    test_excel_processor_units()
