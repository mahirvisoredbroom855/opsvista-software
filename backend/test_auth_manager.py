"""
Test Life360 Authentication Manager
Run this to verify your Life360 credentials work
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.features.life360_integration.services.auth_manager import Life360AuthManager, AuthenticationError

async def test_authentication():
    """Test Life360 authentication step by step"""
    
    print("🧪 Testing Life360 Authentication Manager")
    print("=" * 50)
    
    # Step 1: Check environment variables
    print("Step 1: Checking environment variables...")
    username = os.getenv("LIFE360_USERNAME")
    password = os.getenv("LIFE360_PASSWORD")
    
    if not username or not password:
        print("❌ Missing Life360 credentials in .env file")
        print("   Add LIFE360_USERNAME and LIFE360_PASSWORD to your .env")
        return False
    
    print(f"✅ Username: {username}")
    print(f"✅ Password: {'*' * len(password)}")
    
    # Step 2: Create auth manager
    print("\nStep 2: Creating authentication manager...")
    try:
        auth_manager = Life360AuthManager()
        print("✅ Auth manager created successfully")
    except Exception as e:
        print(f"❌ Failed to create auth manager: {e}")
        return False
    
    # Step 3: Test authentication
    print("\nStep 3: Testing authentication...")
    try:
        async with auth_manager:
            token = await auth_manager.get_valid_token()
            print(f"✅ Authentication successful!")
            print(f"   Token: {token[:20]}...")
            
            # Step 4: Test token validity
            print("\nStep 4: Testing token with API call...")
            is_valid = await auth_manager.test_authentication()
            
            if is_valid:
                print("✅ Token works with Life360 API!")
                return True
            else:
                print("❌ Token doesn't work with API")
                return False
                
    except AuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_authentication())
    if success:
        print("\n🎉 All authentication tests passed!")
    else:
        print("\n💥 Authentication tests failed!")
        sys.exit(1)