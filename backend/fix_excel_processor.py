import os

def fix_excel_processor():
    """Remove raw_data_id references from Excel processor"""
    
    processor_file = "app/features/finance/excel_processor.py"
    
    if not os.path.exists(processor_file):
        print("❌ excel_processor.py not found!")
        return False
    
    with open(processor_file, 'r') as f:
        content = f.read()
    
    # Remove raw_data_id parameter from FactFinance creation
    updated_content = content.replace(
        'raw_data_id=raw_record.id',
        '# raw_data_id removed - not needed'
    )
    
    # Also remove any other raw_data_id references
    updated_content = updated_content.replace(
        ', raw_data_id=raw_record.id',
        ''
    )
    
    # Write back
    with open(processor_file, 'w') as f:
        f.write(updated_content)
    
    print("✅ Removed raw_data_id references from Excel processor")
    return True

if __name__ == "__main__":
    fix_excel_processor()
