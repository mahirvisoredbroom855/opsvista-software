# backend/app/core/database.py
"""
Database Client Module

This module provides Supabase database clients for the application.
It creates both user-level and service-level clients for different operations.

Usage:
    from app.core.database import get_supabase_client, get_service_supabase_client
    
    # For user operations (with RLS)
    user_client = get_supabase_client()
    
    # For admin/service operations (bypasses RLS)
    service_client = get_service_supabase_client()
"""

from supabase import create_client, Client
from functools import lru_cache
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment variables with defaults
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:54321")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "YOUR_ANON_KEY") 
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "YOUR_SERVICE_ROLE_KEY")


@lru_cache()
def get_supabase_client() -> Client:
    """
    Get Supabase client for user operations.
    
    This client uses the anonymous key and respects Row Level Security (RLS) policies.
    Use this for operations that should respect user permissions.
    
    Returns:
        Client: Supabase client with anonymous key
    """
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


@lru_cache()  
def get_service_supabase_client() -> Client:
    """
    Get Supabase service client for admin operations.
    
    This client uses the service role key and bypasses Row Level Security (RLS).
    Use this for background tasks, migrations, and admin operations.
    
    Returns:
        Client: Supabase client with service role key
    """
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# Legacy compatibility - maintain your existing client instances
supabase: Client = get_supabase_client()  # For user operations
service_supabase: Client = get_service_supabase_client()  # For admin operations


# Database configuration for advanced usage
class DatabaseConfig:
    """Database configuration and connection management."""
    
    def __init__(self):
        self.url = SUPABASE_URL
        self.anon_key = SUPABASE_ANON_KEY
        self.service_key = SUPABASE_SERVICE_KEY
    
    @property
    def is_local(self) -> bool:
        """Check if using local Supabase instance."""
        return "localhost" in self.url
    
    @property
    def project_id(self) -> str:
        """Extract project ID from Supabase URL."""
        if self.is_local:
            return "local"
        # Extract from https://abc123.supabase.co format
        return self.url.split("://")[1].split(".")[0]
    
    def get_postgres_url(self) -> str:
        """Get direct PostgreSQL connection URL if needed."""
        if self.is_local:
            return "postgresql://postgres:postgres@localhost:54322/postgres"
        else:
            # For hosted Supabase, construct the direct DB URL
            project_id = self.project_id
            return f"postgresql://postgres:[password]@db.{project_id}.supabase.co:5432/postgres"


# Global database config instance
db_config = DatabaseConfig()


# Health check function
def check_database_health() -> dict:
    """
    Check database connectivity and return health status.
    
    Returns:
        dict: Health status information
    """
    try:
        # Test user client
        user_client = get_supabase_client()
        user_result = user_client.table('auth.users').select('count').limit(1).execute()
        
        # Test service client  
        service_client = get_service_supabase_client()
        service_result = service_client.table('auth.users').select('count').limit(1).execute()
        
        return {
            "status": "healthy",
            "user_client": "connected",
            "service_client": "connected", 
            "project_id": db_config.project_id,
            "is_local": db_config.is_local
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "project_id": db_config.project_id,
            "is_local": db_config.is_local
        }


# Export commonly used clients and functions
__all__ = [
    "get_supabase_client",
    "get_service_supabase_client", 
    "supabase",
    "service_supabase",
    "db_config",
    "check_database_health"
]