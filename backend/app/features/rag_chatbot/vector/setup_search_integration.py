#!/usr/bin/env python3
"""
Setup script to integrate search modules with vector database infrastructure.
Run this to set up the complete search system.
"""

import os
import shutil
import sys
from pathlib import Path

def setup_search_integration():
    """Set up search integration by copying files and creating symlinks."""
    
    print("🔧 Setting up Search Integration")
    print("=" * 50)
    
    # Get current directory (should be vector directory)
    current_dir = Path.cwd()
    vector_dir = current_dir
    
    # Check if we're in the right directory
    if not (vector_dir / "enhanced_vector_client.py").exists():
        print("❌ Error: Please run this script from the vector directory")
        print("   Expected: backend/app/features/rag_chatbot/vector/")
        return False
    
    # Find search directory
    search_dir = vector_dir.parent / "search"
    
    if not search_dir.exists():
        print(f"❌ Error: Search directory not found at {search_dir}")
        print("   Please ensure the search directory exists with the search modules")
        return False
    
    print(f"✅ Found vector directory: {vector_dir}")
    print(f"✅ Found search directory: {search_dir}")
    
    # List of search files to integrate
    search_files = [
        "query_engine.py",
        "vector_search_optimizer.py", 
        "business_context_integration.py"
    ]
    
    # Check if search files exist
    missing_files = []
    for file in search_files:
        if not (search_dir / file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing search files: {missing_files}")
        return False
    
    print("✅ All search files found")
    
    # Create search module import setup
    print("\n📁 Creating search module access...")
    
    # Option 1: Create symbolic links (Unix/Linux/Mac)
    if os.name != 'nt':  # Not Windows
        try:
            for file in search_files:
                source = search_dir / file
                target = vector_dir / file
                
                # Remove existing file/link if it exists
                if target.exists() or target.is_symlink():
                    target.unlink()
                
                # Create symbolic link
                target.symlink_to(source)
                print(f"   🔗 Linked {file}")
            
            print("✅ Symbolic links created successfully")
            
        except Exception as e:
            print(f"❌ Failed to create symbolic links: {e}")
            print("   Falling back to copying files...")
            return copy_files_method(search_dir, vector_dir, search_files)
    
    else:
        # Windows - copy files
        return copy_files_method(search_dir, vector_dir, search_files)
    
    # Create __init__.py if it doesn't exist
    init_file = vector_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# Vector search package\n")
        print("✅ Created __init__.py")
    
    # Test the integration
    print("\n🧪 Testing integration...")
    
    test_code = '''
import sys
sys.path.insert(0, ".")

try:
    from query_engine import BusinessQueryEngine
    print("✅ query_engine imported successfully")
except ImportError as e:
    print(f"❌ query_engine import failed: {e}")

try:
    from vector_search_optimizer import VectorSearchOptimizer
    print("✅ vector_search_optimizer imported successfully")
except ImportError as e:
    print(f"❌ vector_search_optimizer import failed: {e}")

try:
    from business_context_integration import BusinessContextIntegrationEngine
    print("✅ business_context_integration imported successfully")
except ImportError as e:
    print(f"❌ business_context_integration import failed: {e}")

try:
    from integrated_search_system import ComprehensiveSearchSystem
    print("✅ integrated_search_system imported successfully")
except ImportError as e:
    print(f"❌ integrated_search_system import failed: {e}")
'''
    
    # Write test script
    test_file = vector_dir / "test_imports.py"
    test_file.write_text(test_code)
    
    # Run test
    import subprocess
    try:
        result = subprocess.run([sys.executable, "test_imports.py"], 
                              cwd=vector_dir, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr)
        
        # Clean up test file
        test_file.unlink()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    print("\n🎉 SEARCH INTEGRATION SETUP COMPLETE!")
    print("=" * 50)
    print("✅ Search modules are now accessible from vector directory")
    print("✅ integrated_search_system.py provides comprehensive search")
    print("✅ search_integration.py updated with enhanced capabilities")
    print("\n📋 Next steps:")
    print("1. Update your DATABASE_URL in .env with actual password")
    print("2. Run the database schema SQL in Supabase")
    print("3. Test with: python test_supa.py")
    print("4. Use the comprehensive search system in your application")
    
    return True


def copy_files_method(search_dir, vector_dir, search_files):
    """Fallback method to copy files instead of linking."""
    print("   📁 Copying search files...")
    
    try:
        for file in search_files:
            source = search_dir / file
            target = vector_dir / file
            
            # Copy file
            shutil.copy2(source, target)
            print(f"   📄 Copied {file}")
        
        print("✅ Files copied successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to copy files: {e}")
        return False


def create_usage_example():
    """Create a usage example file."""
    
    usage_code = '''#!/usr/bin/env python3
"""
Example usage of the integrated search system.
"""

import asyncio
from integrated_search_system import ComprehensiveSearchSystem

async def main():
    """Example of using the comprehensive search system."""
    
    # Initialize the search system
    search_system = ComprehensiveSearchSystem()
    await search_system.initialize()
    
    # Get system status
    status = await search_system.get_system_status()
    print(f"System ready: {status['integration_status']['ready_for_production']}")
    
    # Perform a comprehensive search
    results = await search_system.comprehensive_search(
        query="Find RB Knit orders above $5000 from last quarter",
        business_filters={
            "department": "commercial",
            "has_financial_data": True
        }
    )
    
    if results['status'] == 'success':
        print(f"Query analyzed: {results['query_analysis']['parsed_intent']}")
        print(f"Found {len(results['results'])} results")
        print(f"Processing time: {results['performance_metrics']['total_processing_time']:.3f}s")
        
        # Show business intelligence
        bi = results['business_intelligence']
        print(f"Business insights: {len(bi.get('top_insights', []))} insights generated")
    
    # Close the system
    await search_system.close()

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    # Write usage example
    usage_file = Path.cwd() / "search_usage_example.py"
    usage_file.write_text(usage_code)
    print(f"📝 Created usage example: {usage_file}")


if __name__ == "__main__":
    if setup_search_integration():
        create_usage_example()
        print("\n🚀 Ready to use comprehensive search system!")
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)