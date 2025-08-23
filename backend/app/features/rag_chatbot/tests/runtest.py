#!/usr/bin/env python3
"""
Script to install dependencies and run the vector search optimization tests.

This script will:
1. Install required dependencies
2. Run the tests with proper async support
3. Generate a test report
"""

import subprocess
import sys
import os
from pathlib import Path

def install_dependencies():
    """Install required dependencies for testing."""
    print("📦 Installing required dependencies...")
    
    dependencies = [
        "pytest",
        "pytest-asyncio", 
        "anyio",
        "numpy",
        "pandas"
    ]
    
    for dep in dependencies:
        try:
            print(f"Installing {dep}...")
            subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                         check=True, capture_output=True)
            print(f"✅ {dep} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {dep}: {e}")
            return False
    
    print("✅ All dependencies installed successfully!")
    return True

def run_tests():
    """Run the vector search optimization tests."""
    print("\n🧪 Running Vector Search Optimization Tests...")
    
    # Get the test file path
    test_file = Path(__file__).parent / "test_vector_search_optimization.py"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    # Run pytest with async support
    try:
        cmd = [
            sys.executable, "-m", "pytest", 
            str(test_file),
            "-v",                        # Verbose output
            "--asyncio-mode=auto",       # Enable async support automatically
            "--tb=short",               # Short traceback format
            "--durations=10",           # Show slowest 10 tests
            "--color=yes"               # Colored output
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=False)
        
        if result.returncode == 0:
            print("\n🎉 All tests passed successfully!")
            return True
        else:
            print(f"\n❌ Tests failed with exit code: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def main():
    """Main function to orchestrate dependency installation and test execution."""
    print("🚀 Vector Search Optimization Test Runner")
    print("=" * 50)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Failed to install dependencies. Exiting.")
        sys.exit(1)
    
    # Run tests
    if not run_tests():
        print("❌ Tests failed. Please check the output above for details.")
        sys.exit(1)
    
    print("\n✅ All operations completed successfully!")
    print("\n📋 Next steps:")
    print("1. Review test results above")
    print("2. Check for any warnings or failed tests")
    print("3. If tests pass, the vector search optimization is ready!")

if __name__ == "__main__":
    main()