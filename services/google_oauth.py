"""
Google OAuth 2.0 service for Calendar API access
"""
import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import aiohttp
from cryptography.fernet import Fernet

from config import (
    GOOGLE_CLIENT_ID, 
    GOOGLE_CLIENT_SECRET, 
    GOOGLE_REDIRECT_URI,
    GOOGLE_SCOPES,
    OAUTH_STATE_EXPIRY_MINUTES,
    ENCRYPTION_KEY
)
from services.database import AsyncSessionLocal, UserSettings


class GoogleOAuthService:
    """Handle Google OAuth 2.0 flow for Calendar API"""
    
    def __init__(self):
        self.client_id = GOOGLE_CLIENT_ID
        self.client_secret = GOOGLE_CLIENT_SECRET
        self.redirect_uri = GOOGLE_REDIRECT_URI
        self.scopes = GOOGLE_SCOPES
        
        # Initialize encryption for storing refresh tokens
        if ENCRYPTION_KEY:
            self.cipher = Fernet(ENCRYPTION_KEY.encode())
        else:
            # Generate a key for this session (not persistent!)
            key = Fernet.generate_key()
            self.cipher = Fernet(key)
            print("⚠️ Warning: Using temporary encryption key. Set ENCRYPTION_KEY in .env for production!")
        
        # In-memory store for OAuth states (temporary)
        self.oauth_states: Dict[str, Dict[str, Any]] = {}
    
    def generate_auth_url(self, user_id: int) -> tuple[str, str]:
        """
        Generate Google OAuth authorization URL
        Returns: (auth_url, state)
        """
        state = secrets.token_urlsafe(32)
        
        # Store state with user info and expiry
        self.oauth_states[state] = {
            'user_id': user_id,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(minutes=OAUTH_STATE_EXPIRY_MINUTES)
        }
        
        # Build authorization URL
        auth_params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(self.scopes),
            'response_type': 'code',
            'access_type': 'offline',  # Request refresh token
            'prompt': 'consent',  # Force consent screen to get refresh token
            'state': state
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(auth_params)}"
        return auth_url, state
    
    async def exchange_code_for_tokens(self, code: str, state: str) -> Optional[Dict[str, Any]]:
        """
        Exchange authorization code for access and refresh tokens
        Returns: token_data or None if failed
        """
        # Validate state
        if state not in self.oauth_states:
            return None
        
        state_data = self.oauth_states[state]
        
        # Check if state expired
        if datetime.utcnow() > state_data['expires_at']:
            del self.oauth_states[state]
            return None
        
        user_id = state_data['user_id']
        
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        
        token_data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=token_data) as response:
                    if response.status == 200:
                        tokens = await response.json()
                        
                        # Store tokens securely in database
                        await self.store_user_tokens(user_id, tokens)
                        
                        # Clean up state
                        del self.oauth_states[state]
                        
                        return tokens
                    else:
                        error_text = await response.text()
                        print(f"Token exchange failed: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            print(f"Error during token exchange: {e}")
            return None
    
    async def store_user_tokens(self, user_id: int, tokens: Dict[str, Any]) -> bool:
        """Store encrypted tokens in database"""
        try:
            async with AsyncSessionLocal() as session:
                # Get or create user settings
                user_settings = await session.get(UserSettings, user_id)
                if not user_settings:
                    user_settings = UserSettings(user_id=user_id)
                    session.add(user_settings)
                
                # Encrypt and store refresh token
                if 'refresh_token' in tokens:
                    encrypted_token = self.cipher.encrypt(tokens['refresh_token'].encode())
                    user_settings.google_refresh_token = encrypted_token.decode()
                
                user_settings.google_calendar_connected = True
                user_settings.updated_at = datetime.utcnow()
                
                await session.commit()
                return True
                
        except Exception as e:
            print(f"Error storing tokens: {e}")
            return False
    
    async def get_access_token(self, user_id: int) -> Optional[str]:
        """Get valid access token for user (refresh if needed)"""
        try:
            async with AsyncSessionLocal() as session:
                user_settings = await session.get(UserSettings, user_id)
                
                if not user_settings or not user_settings.google_calendar_connected:
                    return None
                
                if not user_settings.google_refresh_token:
                    return None
                
                # Decrypt refresh token
                encrypted_token = user_settings.google_refresh_token.encode()
                refresh_token = self.cipher.decrypt(encrypted_token).decode()
                
                # Use refresh token to get new access token
                return await self.refresh_access_token(refresh_token)
                
        except Exception as e:
            print(f"Error getting access token: {e}")
            return None
    
    async def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Use refresh token to get new access token"""
        token_url = "https://oauth2.googleapis.com/token"
        
        token_data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=token_data) as response:
                    if response.status == 200:
                        tokens = await response.json()
                        return tokens.get('access_token')
                    else:
                        error_text = await response.text()
                        print(f"Token refresh failed: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return None
    
    async def revoke_user_access(self, user_id: int) -> bool:
        """Revoke user's Google Calendar access"""
        try:
            # Get access token first to revoke it
            access_token = await self.get_access_token(user_id)
            
            if access_token:
                # Revoke token with Google
                revoke_url = f"https://oauth2.googleapis.com/revoke?token={access_token}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(revoke_url) as response:
                        # Continue even if revocation fails - clean up our data
                        pass
            
            # Clean up database
            async with AsyncSessionLocal() as db_session:
                user_settings = await db_session.get(UserSettings, user_id)
                if user_settings:
                    user_settings.google_calendar_connected = False
                    user_settings.google_refresh_token = None
                    user_settings.calendar_id = None
                    user_settings.updated_at = datetime.utcnow()
                    await db_session.commit()
            
            return True
            
        except Exception as e:
            print(f"Error revoking access: {e}")
            return False
    
    async def check_user_connected(self, user_id: int) -> bool:
        """Check if user has connected Google Calendar"""
        try:
            async with AsyncSessionLocal() as session:
                user_settings = await session.get(UserSettings, user_id)
                return (
                    user_settings and 
                    user_settings.google_calendar_connected and 
                    user_settings.google_refresh_token is not None
                )
        except Exception as e:
            print(f"Error checking connection: {e}")
            return False
    
    def cleanup_expired_states(self):
        """Clean up expired OAuth states"""
        current_time = datetime.utcnow()
        expired_states = [
            state for state, data in self.oauth_states.items()
            if current_time > data['expires_at']
        ]
        
        for state in expired_states:
            del self.oauth_states[state]
        
        if expired_states:
            print(f"Cleaned up {len(expired_states)} expired OAuth states")


# Global instance
google_oauth = GoogleOAuthService()


# Background task for cleanup
async def oauth_cleanup_task():
    """Background task to cleanup expired OAuth states"""
    while True:
        try:
            google_oauth.cleanup_expired_states()
            await asyncio.sleep(300)  # Clean up every 5 minutes
        except Exception as e:
            print(f"Error in OAuth cleanup task: {e}")
            await asyncio.sleep(60)  # Retry in 1 minute if error 