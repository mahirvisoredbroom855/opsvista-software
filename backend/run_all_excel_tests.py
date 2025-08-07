import os
import sys
from dotenv import load_dotenv

sys.path.append('app')
load_dotenv()

def run_all_tests():
    """Run all Excel processor tests in sequence"""
    print("🧪 Excel Processor Complete Test Suite")
    print("=" * 70)
    print("Testing all aspects of Excel processing functionality")
    print("=" * 70)
    
    test_results = {
        'unit_tests': False,
        'integration_tests': False, 
        'workflow_tests': False
    }
    
    # Stage 1: Unit Tests
    print("\n�� STAGE 1: UNIT TESTS")
    print("Testing individual functions in isolation")
    print("-" * 50)
    
    try:
        from test_excel_processor_units import test_excel_processor_units
        test_results['unit_tests'] = test_excel_processor_units()
    except Exception as e:
        print(f"❌ Unit tests crashed: {str(e)}")
        test_results['unit_tests'] = False
    
    # Stage 2: Integration Tests  
    print("\n🔗 STAGE 2: INTEGRATION TESTS")
    print("Testing with real Google Drive files")
    print("-" * 50)
    
    try:
        from test_excel_integration import test_excel_integration
        test_results['integration_tests'] = test_excel_integration()
    except Exception as e:
        print(f"❌ Integration tests crashed: {str(e)}")
        test_results['integration_tests'] = False
    
    # Stage 3: Complete Workflow
    print("\n🔄 STAGE 3: COMPLETE WORKFLOW TESTS")
    print("Testing end-to-end workflow")
    print("-" * 50)
    
    try:
        from test_complete_workflow import test_complete_workflow
        test_results['workflow_tests'] = test_complete_workflow()
    except Exception as e:
        print(f"❌ Workflow tests crashed: {str(e)}")
        test_results['workflow_tests'] = False
    
    # Final Summary
    print("\n" + "=" * 70)
    print("📊 FINAL TEST SUMMARY")
    print("=" * 70)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)
    
    for test_name, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {status} {test_name.replace('_', ' ').title()}")
    
    success_rate = (passed_tests / total_tests) * 100
    
    print(f"\n📈 Overall Results:")
    print(f"   Tests run: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {total_tests - passed_tests}")
    print(f"   Success rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Excel processor is ready for production!")
        print("✅ Phase 4 complete - ready for Phase 5!")
    elif success_rate >= 75:
        print("\n⚠️ Most tests passed, minor issues to fix")
        print("🔧 Review failed tests above")
    else:
        print("\n❌ Significant issues found")
        print("🔧 Need to fix major problems before proceeding")
    
    return success_rate == 100

if __name__ == "__main__":
    run_all_tests()
