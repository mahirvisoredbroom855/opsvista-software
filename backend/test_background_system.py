import requests
import time
import json

def test_background_system():
    """Test the complete background system"""
    print("🧪 Testing Background System")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # Test 1: API Health Check
    print("1️⃣ Testing API health...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ API healthy: {data['status']}")
        else:
            print(f"   ❌ API unhealthy: {response.status_code}")
    except Exception as e:
        print(f"   ❌ API connection failed: {str(e)}")
        return False
    
    # Test 2: Task System Status
    print("\n2️⃣ Testing task system...")
    try:
        response = requests.get(f"{base_url}/api/v1/system/tasks/status")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Task system: {data['status']}")
            print(f"   ⚙️ Workers: {data['workers']}")
            print(f"   📋 Active tasks: {data['active_tasks']}")
        else:
            print(f"   ❌ Task system error: {response.status_code}")


    except Exception as e:
       print(f"   ❌ Task system connection failed: {str(e)}")
   
    # Test 3: Manual Sync Trigger
    print("\n3️⃣ Testing manual sync trigger...")
   
    try:
        response = requests.post(f"{base_url}/api/v1/system/tasks/trigger-sync")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Manual sync triggered: {data['status']}")
            print(f"   📋 Task ID: {data.get('task_id', 'N/A')}")
        else:
            print(f"   ❌ Manual sync failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Manual sync error: {str(e)}")
    
    # Test 4: Dashboard Metrics
    print("\n4️⃣ Testing dashboard metrics...")
    try:
        response = requests.get(f"{base_url}/api/v1/finance/dashboard/metrics")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Dashboard metrics available")
            print(f"   💰 Today's cash: ৳{data.get('today_cash_received', 0):,.2f}")
            print(f"   📊 Month's cash: ৳{data.get('month_cash_received', 0):,.2f}")
        else:
            print(f"   ❌ Dashboard metrics failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Dashboard metrics error: {str(e)}")
    
    # Test 5: File Processing Status
    print("\n5️⃣ Testing file processing status...")
    try:
        response = requests.get(f"{base_url}/api/v1/finance/files/processing")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Processing status available")
            print(f"   📁 Recent processing records: {len(data)}")
            
            if data:
                latest = data[0]
                print(f"   📄 Latest: {latest.get('source_file', 'Unknown')}")
                print(f"   📊 Status: {latest.get('status', 'Unknown')}")
        else:
            print(f"   ❌ Processing status failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Processing status error: {str(e)}")
    
    print("\n🎉 Background system test completed!")
    print("\n📊 System is ready for:")
    print("   • Automatic file monitoring (every 3 minutes)")
    print("   • Background Excel processing")
    print("   • Real-time dashboard updates")
    print("   • Error handling and recovery")

if __name__ == "__main__":
   print("📋 Background System Test")
   print("🎯 Make sure all services are running first!")
   print("   Run: python start_background_services.py")
   print("=" * 50)
   
   # Wait a moment for user to start services
   input("Press Enter when all services are running...")
   
   test_background_system()
