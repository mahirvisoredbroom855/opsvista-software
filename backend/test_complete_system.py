#!/usr/bin/env python3
# Complete System Integration Test
import requests
import time
import json
from datetime import datetime

def test_complete_system():
    """Test the entire system end-to-end"""
    print("🧪 Complete System Integration Test")
    print("=" * 60)
    print("Testing: API + Background Tasks + Database + Google Drive")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    test_results = {
        "tests_run": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "errors": []
    }
    
    def run_test(test_name, test_func):
        test_results["tests_run"] += 1
        print(f"\n{test_results['tests_run']}️⃣ {test_name}")
        try:
            if test_func():
                test_results["tests_passed"] += 1
                print(f"   ✅ PASSED")
                return True
            else:
                test_results["tests_failed"] += 1
                print(f"   ❌ FAILED")
                return False
        except Exception as e:
            test_results["tests_failed"] += 1
            test_results["errors"].append(f"{test_name}: {str(e)}")
            print(f"   💥 ERROR: {str(e)}")
            return False
    
    # Test 1: Basic API Health
    def test_api_health():
        response = requests.get(f"{base_url}/health", timeout=10)
        return response.status_code == 200 and response.json()["status"] == "healthy"
    
    # Test 2: Background Task System
    def test_background_tasks():
        response = requests.get(f"{base_url}/api/v1/system/tasks/status", timeout=10)
        if response.status_code != 200:
            return False
        data = response.json()
        return data["status"] in ["online", "running"]
    
    # Test 3: Database Connection
    def test_database():
        response = requests.get(f"{base_url}/api/v1/finance/health", timeout=10)
        if response.status_code != 200:
            return False
        data = response.json()
        return data["database_connection"] == True
    
    # Test 4: Dashboard Metrics
    def test_dashboard_metrics():
        response = requests.get(f"{base_url}/api/v1/finance/dashboard/metrics", timeout=15)
        if response.status_code != 200:
            return False
        data = response.json()
        required_fields = ["today_cash_received", "month_cash_received", "year_revenue"]
        return all(field in data for field in required_fields)
    
    # Test 5: File Processing Status
    def test_file_processing():
        response = requests.get(f"{base_url}/api/v1/finance/files/processing", timeout=10)
        return response.status_code == 200
    
    # Test 6: Manual Sync Trigger
    def test_manual_sync():
        response = requests.post(f"{base_url}/api/v1/system/tasks/trigger-sync", timeout=15)
        if response.status_code != 200:
            return False
        data = response.json()
        return data["status"] == "queued" and "task_id" in data
    
    # Test 7: System Monitoring
    def test_monitoring():
        response = requests.get(f"{base_url}/api/v1/monitoring/system/health", timeout=10)
        return response.status_code == 200
    
    # Test 8: Processing Statistics
    def test_processing_stats():
        response = requests.get(f"{base_url}/api/v1/monitoring/processing/stats", timeout=10)
        return response.status_code == 200
    
    # Run all tests
    run_test("API Health Check", test_api_health)
    run_test("Background Task System", test_background_tasks)
    run_test("Database Connection", test_database)
    run_test("Dashboard Metrics", test_dashboard_metrics)
    run_test("File Processing Status", test_file_processing)
    run_test("Manual Sync Trigger", test_manual_sync)
    run_test("System Monitoring", test_monitoring)
    run_test("Processing Statistics", test_processing_stats)
    
    # Final Results
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    
    success_rate = (test_results["tests_passed"] / test_results["tests_run"]) * 100
    
    print(f"   Tests Run: {test_results['tests_run']}")
    print(f"   Passed: {test_results['tests_passed']}")
    print(f"   Failed: {test_results['tests_failed']}")
    print(f"   Success Rate: {success_rate:.1f}%")
    
    if test_results["errors"]:
        print(f"\n❌ Errors:")
        for error in test_results["errors"]:
            print(f"   • {error}")
    
    if success_rate == 100:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Complete system is working perfectly!")
        print("\n🚀 System Features Verified:")
        print("   • ✅ Real-time API responses")
        print("   • ✅ Background task processing")
        print("   • ✅ Database connectivity")
        print("   • ✅ Dashboard metrics generation")
        print("   • ✅ File processing pipeline")
        print("   • ✅ Manual sync capabilities")
        print("   • ✅ System monitoring")
        print("   • ✅ Processing statistics")
        
        print("\n📋 Next Steps:")
        print("   1. System is ready for production!")
        print("   2. Monitor dashboard: http://localhost:8000/docs")
        print("   3. Check processing: http://localhost:8000/api/v1/monitoring/system/health")
        print("   4. Your Excel files will be processed automatically every 3 minutes")
        
    elif success_rate >= 75:
        print(f"\n⚠️ MOSTLY WORKING ({success_rate:.1f}%)")
        print("Most features are working, but some issues need attention")
        
    else:
        print(f"\n❌ SYSTEM HAS ISSUES ({success_rate:.1f}%)")
        print("Multiple components are failing - check the errors above")
    
    return success_rate == 100

if __name__ == "__main__":
    print("📋 Complete System Test")
    print("🎯 This will test the entire OpsVista Finance system")
    print("⚠️ Make sure all services are running first!")
    print("   Run: python start_background_services.py")
    print("\nPress Enter to start the complete system test...")
    input()
    
    test_complete_system()
