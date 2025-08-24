import asyncio
from app.features.rag_chatbot.discovery.scanner import test_scanner_setup
from app.core.database import get_supabase_client
import os
from dotenv import load_dotenv
# app.core.database
load_dotenv()



async def test_setup():
    credentials_path = "credentials/google_credentials.json"
    db_client = get_supabase_client()
    
    results = await test_scanner_setup(credentials_path, db_client)
    print("Test Results:", results)


if __name__ == "__main__":
    asyncio.run(test_setup())