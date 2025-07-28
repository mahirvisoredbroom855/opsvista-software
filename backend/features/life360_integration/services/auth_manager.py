"""
Life360 Authentication Manager

Handles OAuth 2.0 authentication flow with Life360 API:
1. Initial authentication with username/password
2. Token storage and retrieval
3. Automatic token refresh
4. Authentication state management
"""

import os
import time
import json
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.core.supabase_client import service_supabase
import logging

logger = logging.getLogger(__name__)

class AuthToken(BaseModel):
    """Model for Life360 authentication token"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int  # Seconds until expiration
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None  # Calculated expiration time

class Life360AuthManager:
    """
    Manages Life360 API authentication using OAuth 2.0
    
    Architecture:
    - Stores credentials securely in environment variables
    - Caches tokens in database with expiration tracking
    - Automatically refreshes tokens before expiration
    - Handles authentication failures gracefully
    """
    
    def __init__(self):
        # Life360 API endpoints
        self.auth_url = "https://api.life360.com/v3/oauth2/token.json"
        self.base_url = "https://api.life360.com/v3"
        
        # Credentials from environment
        self.username = os.getenv("LIFE360_USERNAME")
        self.password = os.getenv("LIFE360_PASSWORD")
        
        # OAuth client credentials (hardcoded for Life360)
        # These are public client credentials used by Life360 mobile apps
        self.client_id = "b89ba580-cea7-4d8c-b564-8b45c6e6a9a7"
        self.client_secret = "89bbbbb9-b79c-4a5e-9c25-5a4d4b5bf0f9"
        
        # Token caching
        self.current_token: Optional[AuthToken] = None
        self.token_refresh_threshold = 300  # Refresh 5 minutes before expiry
        
        # HTTP client with timeout and retry configuration
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        if not self.username or not self.password:
            raise ValueError("Life360 credentials not found in environment variables")
    
    async def get_valid_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary
        
        Returns:
            str: Valid access token
            
        Raises:
            AuthenticationError: If authentication fails
        """
        logger.info("🔑 Requesting valid Life360 access token")
        
        # Check if we have a cached token
        if self.current_token:
            if self._is_token_valid(self.current_token):
                logger.info("✅ Using cached token")
                return self.current_token.access_token
            
            # Try to refresh if we have a refresh token
            if self.current_token.refresh_token:
                logger.info("🔄 Refreshing expired token")
                try:
                    new_token = await self._refresh_token(self.current_token.refresh_token)
                    await self._cache_token(new_token)
                    return new_token.access_token
                except Exception as e:
                    logger.warning(f"Token refresh failed: {e}")
        
        # Authenticate fresh
        logger.info("🆕 Performing fresh authentication")
        token = await self._authenticate()
        await self._cache_token(token)
        return token.access_token
    
    async def _authenticate(self) -> AuthToken:
        """
        Perform initial authentication with Life360
        
        Uses OAuth 2.0 Resource Owner Password Credentials Grant
        This is the flow Life360 mobile apps use
        """
        auth_data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        logger.info("📡 Sending authentication request to Life360")
        
        try:
            response = await self.client.post(
                self.auth_url,
                data=auth_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "SafetyMapKoko/22.6.0.175 CFNetwork/1240.0.4 Darwin/20.6.0"
                }
            )
            
            response.raise_for_status()
            token_data = response.json()
            
            logger.info("✅ Authentication successful")
            
            # Create token object with calculated expiration
            token = AuthToken(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in", 3600),
                refresh_token=token_data.get("refresh_token"),
                expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
            )
            
            return token
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("❌ Authentication failed: Invalid credentials")
                raise AuthenticationError("Invalid Life360 credentials")
            elif e.response.status_code == 429:
                logger.error("❌ Authentication failed: Rate limited")
                raise AuthenticationError("Rate limited by Life360 API")
            else:
                logger.error(f"❌ Authentication failed: HTTP {e.response.status_code}")
                raise AuthenticationError(f"Life360 API error: {e.response.status_code}")
        
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            raise AuthenticationError(f"Authentication error: {e}")
    
    async def _refresh_token(self, refresh_token: str) -> AuthToken:
        """Refresh an expired access token"""
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        response = await self.client.post(self.auth_url, data=refresh_data)
        response.raise_for_status()
        token_data = response.json()
        
        return AuthToken(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 3600),
            refresh_token=token_data.get("refresh_token", refresh_token),
            expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
        )
    
    def _is_token_valid(self, token: AuthToken) -> bool:
        """Check if token is still valid (not expired)"""
        if not token.expires_at:
            return False
        
        # Consider token invalid if it expires within the threshold
        threshold_time = datetime.utcnow() + timedelta(seconds=self.token_refresh_threshold)
        return token.expires_at > threshold_time
    
    async def _cache_token(self, token: AuthToken) -> None:
        """Cache token in database for reuse across requests"""
        token_data = {
            "service": "life360",
            "token_data": token.dict(),
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
            "created_at": datetime.utcnow().isoformat()
        }
        
        try:
            # Upsert token (update if exists, insert if not)
            result = service_supabase.table("api_tokens").upsert(
                token_data,
                on_conflict="service"
            ).execute()
            
            self.current_token = token
            logger.info("💾 Token cached successfully")
            
        except Exception as e:
            logger.warning(f"Failed to cache token: {e}")
            # Don't fail the whole operation if caching fails
            self.current_token = token
    
    async def _load_cached_token(self) -> Optional[AuthToken]:
        """Load token from database cache"""
        try:
            result = service_supabase.table("api_tokens").select("*").eq("service", "life360").execute()
            
            if result.data:
                token_data = result.data[0]["token_data"]
                return AuthToken(**token_data)
                
        except Exception as e:
            logger.warning(f"Failed to load cached token: {e}")
        
        return None
    
    async def test_authentication(self) -> bool:
        """Test if authentication is working"""
        try:
            token = await self.get_valid_token()
            
            # Test token by making a simple API call
            response = await self.client.get(
                f"{self.base_url}/circles",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            response.raise_for_status()
            logger.info("✅ Authentication test successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ Authentication test failed: {e}")
            return False
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.aclose()

class AuthenticationError(Exception):
    """Custom exception for authentication failures"""
    pass