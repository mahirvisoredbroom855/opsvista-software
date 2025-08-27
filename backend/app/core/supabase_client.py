from supabase import create_client, Client
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:54321")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "YOUR_ANON_KEY")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "YOUR_SERVICE_ROLE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Default clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)  # For user operations
service_supabase: Client = create_client(SUPABASE_URL, SERVICE_KEY)  # For admin operations

# Database session setup (if using PostgreSQL directly)
engine = None
SessionLocal = None

if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_supabase_session() -> Session:
    """
    Get a database session for SQLAlchemy operations.
    This is the missing function that finance router is trying to import.
    """
    if not SessionLocal:
        raise RuntimeError("Database not configured. Set DATABASE_URL environment variable.")
    
    return SessionLocal()

def get_db():
    """
    Dependency to get database session with proper cleanup.
    Use this in FastAPI route dependencies.
    """
    if not SessionLocal:
        raise RuntimeError("Database not configured. Set DATABASE_URL environment variable.")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()