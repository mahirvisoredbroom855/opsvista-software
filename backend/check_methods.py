import os

def check_processor_methods():
    """Check what methods exist in excel_processor.py"""
    print("📝 Checking Excel Processor Methods")
    print("=" * 50)
    
    processor_file = "app/features/finance/excel_processor.py"
    
    if not os.path.exists(processor_file):
        print("❌ excel_processor.py not found!")
        return False
    
    with open(processor_file, 'r') as f:
        content = f.read()
    
    # Find all method definitions
    methods = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        if line.strip().startswith('def ') and 'self' in line:
            method_name = line.strip().split('(')[0].replace('def ', '')
            methods.append((method_name, i+1))
    
    print(f"Found {len(methods)} methods:")
    for method, line_num in methods:
        print(f"   Line {line_num:3d}: {method}")
    
    # Check for specific methods we need
    required = [
        'detect_file_type',
        'smart_date_parsing',
        'safe_decimal',
        'map_cash_book_columns',
        'map_due_bill_columns',
        'map_expenditure_columns'
    ]
    
    print(f"\nRequired methods check:")
    missing = []
    for req in required:
        found = any(method for method, _ in methods if method == req)
        status = "✅" if found else "❌"
        print(f"   {status} {req}")
        if not found:
            missing.append(req)
    
    if missing:
        print(f"\n❌ Missing {len(missing)} required methods")
        return False
    else:
        print(f"\n✅ All required methods found!")
        return True

if __name__ == "__main__":
    check_processor_methods()
