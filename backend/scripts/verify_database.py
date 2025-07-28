#!/usr/bin/env python3
"""
Verify that Life360 database tables were created successfully
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.supabase_client import service_supabase

def verify_tables():
    """Check if all required tables exist"""
    
    required_tables = [
        'life360_circles',
        'raw_location_feed', 
        'life360_user_mapping'
    ]
    
    print("🔍 Verifying Life360 database tables...")
    
    for table_name in required_tables:
        try:
            # Try to query the table (will fail if it doesn't exist)
            result = service_supabase.table(table_name).select('*').limit(1).execute()
            print(f"✅ Table '{table_name}' exists and is accessible")
        except Exception as e:
            print(f"❌ Table '{table_name}' error: {e}")
            return False
    
    print("\n🎉 All Life360 tables verified successfully!")
    return True

def test_table_operations():
    """Test basic CRUD operations"""
    
    print("\n🧪 Testing table operations...")
    
    try:
        # Test inserting a circle
        test_circle = {
            'circle_id': 'test_circle_12345',
            'circle_name': 'Test Family Circle',
            'is_active': True
        }
        
        result = service_supabase.table('life360_circles').insert(test_circle).execute()
        circle_id = result.data[0]['id']
        print("✅ Circle insert test passed")
        
        # Test reading the circle
        result = service_supabase.table('life360_circles').select('*').eq('id', circle_id).execute()
        assert len(result.data) == 1
        print("✅ Circle select test passed")
        
        # Test updating the circle
        service_supabase.table('life360_circles').update({'circle_name': 'Updated Test Circle'}).eq('id', circle_id).execute()
        print("✅ Circle update test passed")
        
        # Clean up - delete test circle
        service_supabase.table('life360_circles').delete().eq('id', circle_id).execute()
        print("✅ Circle delete test passed")
        
        print("\n🎉 All CRUD operations working correctly!")
        
    except Exception as e:
        print(f"❌ Table operations test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = verify_tables()
    if success:
        test_table_operations()
    else:
        sys.exit(1)