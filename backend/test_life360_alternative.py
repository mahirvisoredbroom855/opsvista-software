"""
Alternative Life360 authentication approach
"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def test_alternative_auth():
    username = os.getenv("LIFE360_USERNAME")
    password = os.getenv("LIFE360_PASSWORD")
    
    # Some users report these work better
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Life360/22.6.0.175 CFNetwork/1240.0.4 Darwin/20.6.0",
        "Accept": "application/json",
        "Authorization": "Basic " + "base64_encoded_client_credentials"
    }
    
    # Alternative 1: Try without client credentials
    auth_data_v1 = {
        "grant_type": "password",
        "username": username,
        "password": password
    }
    
    # Alternative 2: Try with different grant type
    auth_data_v2 = {
        "grant_type": "client_credentials",
        "username": username,
        "password": password
    }
    
    async with httpx.AsyncClient() as client:
        for i, data in enumerate([auth_data_v1, auth_data_v2], 1):
            print(f"\n🧪 Testing approach {i}...")
            
            try:
                response = await client.post(
                    "https://api.life360.com/v3/oauth2/token.json",
                    data=data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "Life360/22.6.0 (iPhone; iOS 15.0)"
                    }
                )
                
                print(f"   Status: {response.status_code}")
                print(f"   Headers: {dict(response.headers)}")
                print(f"   Response: {response.text}")
                
            except Exception as e:
                print(f"   Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_alternative_auth())