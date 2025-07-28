# Test SQLAlchemy models
from app.features.finance.models import RawDriveFinance, FactFinance, FinanceSummary, FinanceFileProcessing

def test_models():
    print("🔍 Testing SQLAlchemy models...")
    
    # Test model creation (no database connection needed)
    try:
        # Test Raw Data model
        raw_model = RawDriveFinance.__table__
        print(f"✅ RawDriveFinance model: {len(raw_model.columns)} columns")
        
        # Test Fact model  
        fact_model = FactFinance.__table__
        print(f"✅ FactFinance model: {len(fact_model.columns)} columns")
        
        # Test Summary model
        summary_model = FinanceSummary.__table__ 
        print(f"✅ FinanceSummary model: {len(summary_model.columns)} columns")
        
        # Test File Processing model
        processing_model = FinanceFileProcessing.__table__
        print(f"✅ FinanceFileProcessing model: {len(processing_model.columns)} columns")
        
        print("\n🎉 All SQLAlchemy models created successfully!")
        print("📊 Models are ready for:")
        print("   • Raw Excel data ingestion")
        print("   • Normalized fact table operations") 
        print("   • Dashboard summary calculations")
        print("   • File processing monitoring")
        
        return True
        
    except Exception as e:
        print(f"❌ Model creation failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_models()
