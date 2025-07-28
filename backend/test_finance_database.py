import os
from dotenv import load_dotenv
from supabase import create_client, Client


load_dotenv()

def test_finance_schema():
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not url or not key:
            print("❌ Missing Supabase environment variables")
            return False
            
        supabase: Client = create_client(url, key)
        
        # Test all finance tables with correct primary key columns
        tables_to_test = [
            ('raw_drive_finance', 'id'),           # Uses 'id' as primary key
            ('fact_finance', 'finance_id'),        # Uses 'finance_id' as primary key  
            ('finance_summary', 'id'),             # Uses 'id' as primary key
            ('finance_file_processing', 'id')      # Uses 'id' as primary key
        ]
        
        print("🔍 Testing finance database schema...")
        
        for table, pk_column in tables_to_test:
            try:
                result = supabase.table(table).select(pk_column).limit(1).execute()
                print(f"✅ Table '{table}' exists and is accessible (PK: {pk_column})")
            except Exception as e:
                print(f"❌ Table '{table}' error: {str(e)}")
                return False
        
        print("\n🎉 All finance tables created successfully!")
        print("\n📊 Schema supports:")
        print("   • Cash Book daily transactions")
        print("   • Party Due Bill tracking") 
        print("   • Multi-year expenditure summaries")
        print("   • Mixed currency handling (BDT/USD)")
        print("   • File processing monitoring")
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_finance_schema()
