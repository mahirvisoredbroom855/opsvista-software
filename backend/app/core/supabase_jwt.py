import os
from pathlib import Path
from dotenv import load_dotenv
from jose import jwt, JWTError
from fastapi import HTTPException
from typing import Dict, Any
from dotenv import load_dotenv

# # Load .env from TWO levels above this file (main root)
# env_path = Path(__file__).resolve().parents[2] / ".env"
# load_dotenv(dotenv_path=env_path)



# Load .env from the main root directory
load_dotenv()

JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("SUPABASE_JWT_SECRET is not set in the environment")



ALGORITHM = "HS256"  # Supabase uses HS256 for legacy tokens

def verify_supabase_token(token: str) -> dict:
    try:
        print("🔍 Verifying token:", token[:30], "...")
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False}  # ✅ disable audience check
        )
        print("✅ Payload:", payload)
        return payload
    except JWTError as e:
        print("❌ JWT Decode Error:", str(e))
        raise HTTPException(status_code=401, detail="Invalid or expired Supabase JWT")

