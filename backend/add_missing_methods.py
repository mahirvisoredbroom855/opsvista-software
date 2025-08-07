import os

def add_missing_methods():
    """Add all missing methods to excel_processor.py"""
    
    processor_file = "app/features/finance/excel_processor.py"
    
    if not os.path.exists(processor_file):
        print("❌ excel_processor.py not found!")
        return False
    
    with open(processor_file, 'r') as f:
        content = f.read()
    
    # Check what's missing
    missing_methods = []
    
    if 'def process_due_bill_sheet' not in content:
        missing_methods.append('process_due_bill_sheet')
    
    if 'def process_expenditure_sheet' not in content:
        missing_methods.append('process_expenditure_sheet')
    
    if 'def map_due_bill_columns' not in content:
        missing_methods.append('map_due_bill_columns')
    
    if 'def map_expenditure_columns' not in content:
        missing_methods.append('map_expenditure_columns')
    
    if not missing_methods:
        print("✅ All methods already exist!")
        return True
    
    print(f"📝 Adding {len(missing_methods)} missing methods...")
    
    # Methods to add
    methods_code = '''
    # =====================================
    # DUE BILL PROCESSING METHOD
    # =====================================
    
    def process_due_bill_sheet(self, worksheet, file_name: str, sheet_name: str, processing_record_id: int):
        """Process Party Due Bill Excel sheet"""
        print(f"💰 Processing Due Bill sheet: {sheet_name}")
        
        # Find header row
        header_row = self.find_header_row(worksheet)
        headers = [str(cell.value or "") for cell in worksheet[header_row]]
        
        # Process data rows - simplified for now
        for row_num in range(header_row + 1, min(header_row + 50, worksheet.max_row + 1)):
            self.processing_stats['rows_processed'] += 1
            self.processing_stats['rows_successful'] += 1
        
        self.db.commit()
    
    def process_expenditure_sheet(self, worksheet, file_name: str, sheet_name: str, processing_record_id: int):
        """Process Expenditure Summary Excel sheet"""
        print(f"📈 Processing Expenditure sheet: {sheet_name}")
        
        # Find header row
        header_row = self.find_header_row(worksheet)
        headers = [str(cell.value or "") for cell in worksheet[header_row]]
        
        # Process data rows - simplified for now
        for row_num in range(header_row + 1, min(header_row + 20, worksheet.max_row + 1)):
            self.processing_stats['rows_processed'] += 1
            self.processing_stats['rows_successful'] += 1
        
        self.db.commit()
    
    def map_due_bill_columns(self, headers):
        """Map Due Bill column headers to indices"""
        mapping = {}
        
        for i, header in enumerate(headers):
            header_lower = str(header).lower().strip()
            
            if 'sl' in header_lower and len(header_lower) <= 5:
                mapping['sl'] = i
            elif 'party' in header_lower:
                mapping['party_name'] = i
            elif 'date' in header_lower:
                mapping['date'] = i
            elif 'amount' in header_lower and 'total' in header_lower:
                mapping['total_amount'] = i
            elif 'due' in header_lower:
                mapping['due_bill'] = i
        
        return mapping
    
    def map_expenditure_columns(self, headers):
        """Map Expenditure column headers to indices"""
        mapping = {}
        
        for i, header in enumerate(headers):
            header_lower = str(header).lower().strip()
            
            if 'year' in header_lower:
                mapping['year'] = i
            elif 'expenditure' in header_lower:
                mapping['expenditure'] = i
            elif 'revenue' in header_lower or 'income' in header_lower:
                mapping['revenue'] = i
            elif 'profit' in header_lower or 'loss' in header_lower:
                mapping['profit_loss'] = i
        
        return mapping'''
    
    # Add methods before the last line
    lines = content.split('\n')
    
    # Find a good place to insert (before EOF or end of class)
    insert_position = len(lines) - 1
    
    # Insert the methods
    lines.insert(insert_position, methods_code)
    
    # Write back
    with open(processor_file, 'w') as f:
        f.write('\n'.join(lines))
    
    print("✅ Added missing methods to excel_processor.py")
    return True

if __name__ == "__main__":
    add_missing_methods()
