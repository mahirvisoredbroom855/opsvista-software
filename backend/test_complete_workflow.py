import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

from app.features.finance.google_drive_service import GoogleDriveService
from app.features.finance.excel_processor import ExcelProcessor
from datetime import datetime

# Simulate real database operations
class WorkflowMockDB:
    def __init__(self):
        self.operations = []
        self.data_summary = {
            'cash_receipts': [],
            'due_bills': [], 
            'expenditures': []
        }
        self.transaction_count = 0
    
    def add(self, item):
        self.operations.append(f"ADD: {type(item).__name__}")
        
        # Simulate data categorization
        if hasattr(item, 'transaction_type'):
            if item.transaction_type == 'cash_receipt':
                self.data_summary['cash_receipts'].append({
                    'date': getattr(item, 'transaction_date', None),
                    'amount': getattr(item, 'amount_bdt', 0)
                })
            elif item.transaction_type == 'due_bill':
                self.data_summary['due_bills'].append({
                    'party': getattr(item, 'party_name', ''),
                    'amount': getattr(item, 'amount_bdt', 0)
                })
            elif item.transaction_type == 'yearly_summary':
                self.data_summary['expenditures'].append({
                    'year': getattr(item, 'transaction_date', None),
                    'amount': getattr(item, 'amount_bdt', 0)
                })
            
            self.transaction_count += 1
    
    def flush(self):
        self.operations.append("FLUSH")
    
    def commit(self):
        self.operations.append("COMMIT")

def test_complete_workflow():
    """Test complete workflow from Google Drive to processed data"""
    print("🔄 Complete Workflow Test")
    print("Testing: Google Drive → Download → Process → Database")
    print("=" * 60)
    
    try:
        # Initialize all services
        print("1️⃣ Initializing services...")
        drive_service = GoogleDriveService()
        mock_db = WorkflowMockDB()
        processor = ExcelProcessor(mock_db)
        
        print("   ✅ Google Drive Service initialized")
        print("   ✅ Excel Processor initialized")
        print("   ✅ Mock Database initialized")
        
        # Step 1: Google Drive Connection
        print("\n2️⃣ Testing Google Drive connection...")
        connection_test = drive_service.test_connection()
        
        if not connection_test['connected']:
            print("❌ Google Drive connection failed!")
            return False
        
        print("   ✅ Google Drive connected successfully")
        
        # Step 2: Find target files
        print("\n3️⃣ Finding target files...")
        folder_id = drive_service.find_finance_folder("Md. Mizanur Rahman (PTIL)")
        target_files = drive_service.list_target_finance_files(folder_id)
        
        if not target_files:
            print("   ❌ No target files found!")
            return False
        
        print(f"   ✅ Found {len(target_files)} target files")
        for file in target_files:
            print(f"      📄 {file['name']}")
        
        # Step 3: Process each file completely
        print("\n4️⃣ Processing complete workflow...")
        
        workflow_results = {
            'files_processed': 0,
            'total_transactions': 0,
            'cash_receipts': 0,
            'due_bills': 0,
            'expenditures': 0,
            'errors': []
        }
        
        for file in target_files:
            file_name = file['name']
            print(f"\n   📊 Processing: {file_name}")
            
            try:
                # Download
                print("      📥 Downloading...")
                file_content = drive_service.download_file(file['id'])
                
                if not file_content:
                    workflow_results['errors'].append(f"{file_name}: Download failed")
                    continue
                
                # Process  
                print("      ⚙️ Processing...")
                result = processor.process_file(file_content, file_name, 1)
                
                if result['status'] == 'success':
                    workflow_results['files_processed'] += 1
                    stats = result['stats']
                    
                    print(f"      ✅ Success: {stats['rows_successful']} transactions")
                    
                    # Count transaction types
                    cash_count = len(mock_db.data_summary['cash_receipts'])
                    due_count = len(mock_db.data_summary['due_bills'])
                    exp_count = len(mock_db.data_summary['expenditures'])
                    
                    workflow_results['cash_receipts'] = cash_count
                    workflow_results['due_bills'] = due_count  
                    workflow_results['expenditures'] = exp_count
                    workflow_results['total_transactions'] = mock_db.transaction_count
                    
                else:
                    workflow_results['errors'].append(f"{file_name}: {result.get('error')}")
                    print(f"      ❌ Failed: {result.get('error')}")
                
            except Exception as e:
                workflow_results['errors'].append(f"{file_name}: Exception - {str(e)}")
                print(f"      💥 Exception: {str(e)}")
        
        # Step 4: Analyze results
        print(f"\n5️⃣ Workflow Analysis:")
        print(f"   📊 Files processed: {workflow_results['files_processed']}/{len(target_files)}")
        print(f"   💰 Total transactions: {workflow_results['total_transactions']}")
        print(f"   📈 Cash receipts: {workflow_results['cash_receipts']}")
        print(f"   💳 Due bills: {workflow_results['due_bills']}")
        print(f"   📋 Expenditures: {workflow_results['expenditures']}")
        
        if workflow_results['errors']:
            print(f"   ❌ Errors: {len(workflow_results['errors'])}")
            for error in workflow_results['errors']:
                print(f"      • {error}")
        
        # Step 5: Simulate dashboard queries
        print(f"\n6️⃣ Simulating dashboard queries...")
        
        # Calculate totals (like dashboard would)
        total_cash = sum(item['amount'] for item in mock_db.data_summary['cash_receipts'])
        total_due = sum(item['amount'] for item in mock_db.data_summary['due_bills'])
        total_exp = sum(item['amount'] for item in mock_db.data_summary['expenditures'])
        
        print(f"   💰 Total cash received: ৳{total_cash:,.2f}")
        print(f"   💳 Total due bills: ৳{total_due:,.2f}")
        print(f"   📋 Total expenditures: ৳{total_exp:,.2f}")
        print(f"   📊 Net cash flow: ৳{total_cash - total_exp:,.2f}")
        
        # Step 6: Database operations summary
        print(f"\n7️⃣ Database operations summary:")
        print(f"   🔄 Total operations: {len(mock_db.operations)}")
        
        operation_counts = {}
        for op in mock_db.operations:
            operation_counts[op] = operation_counts.get(op, 0) + 1
        
        for op, count in operation_counts.items():
            print(f"   📝 {op}: {count}")
        
        # Success criteria
        success = (
            workflow_results['files_processed'] > 0 and
            workflow_results['total_transactions'] > 0 and
            len(workflow_results['errors']) == 0
        )
        
        if success:
            print(f"\n🎉 Complete workflow test PASSED!")
            print(f"   ✅ All files processed successfully")
            print(f"   ✅ {workflow_results['total_transactions']} transactions extracted")
            print(f"   ✅ No errors encountered")
            print(f"   ✅ Dashboard data ready")
        else:
            print(f"\n⚠️ Workflow test had issues:")
            if workflow_results['files_processed'] == 0:
                print(f"   ❌ No files were processed successfully")
            if workflow_results['total_transactions'] == 0:
                print(f"   ❌ No transactions were extracted")
            if len(workflow_results['errors']) > 0:
                print(f"   ❌ {len(workflow_results['errors'])} errors occurred")
        
        return success
        
    except Exception as e:
        print(f"❌ Complete workflow test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_complete_workflow()
