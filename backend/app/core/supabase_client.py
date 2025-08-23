from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:54321")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "YOUR_ANON_KEY")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "YOUR_SERVICE_ROLE_KEY")

# Default clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)  # For user operations
service_supabase: Client = create_client(SUPABASE_URL, SERVICE_KEY)  # For admin operations