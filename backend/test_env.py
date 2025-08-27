import os
from dotenv import load_dotenv
from pathlib import Path

# Load from repo root
load_dotenv(Path(__file__).parent.parent / ".env")

print("Environment Variables:")
print(f"SUPABASE_JWT_SECRET: {'✅ SET' if os.getenv('SUPABASE_JWT_SECRET') else '❌ NOT SET'}")
print(f"SUPABASE_URL: {'✅ SET' if os.getenv('SUPABASE_URL') else '❌ NOT SET'}")  
print(f"OPENAI_API_KEY: {'✅ SET' if os.getenv('OPENAI_API_KEY') else '❌ NOT SET'}")
