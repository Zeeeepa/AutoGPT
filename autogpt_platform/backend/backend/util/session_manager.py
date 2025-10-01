"""
Session Manager for Persistent Authentication and Cookie Management.

This module provides comprehensive session management to avoid repeated authentication
by saving and restoring cookies, local storage, and session data.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import pickle
import base64
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


@dataclass
class SessionCookie:
    """Represents a browser cookie."""
    name: str
    value: str
    domain: str
    path: str = "/"
    expires: Optional[datetime] = None
    secure: bool = False
    http_only: bool = False
    same_site: Optional[str] = None


@dataclass
class SessionData:
    """Complete session data for a provider."""
    provider_id: str
    provider_name: str
    url: str
    username: str
    
    # Session state
    cookies: List[SessionCookie] = field(default_factory=list)
    local_storage: Dict[str, str] = field(default_factory=dict)
    session_storage: Dict[str, str] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    last_validated: Optional[datetime] = None
    is_valid: bool = True
    validation_failures: int = 0
    
    # Browser state
    user_agent: Optional[str] = None
    viewport: Optional[Tuple[int, int]] = None
    timezone: Optional[str] = None
    language: Optional[str] = None


class SessionEncryption:
    """Handles encryption/decryption of session data."""
    
    def __init__(self, key_file: str = "config/session_encryption.key"):
        self.key_file = Path(key_file)
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        self._key = self._load_or_create_key()
        self._cipher = Fernet(self._key)
    
    def _load_or_create_key(self) -> bytes:
        """Load existing key or create a new one."""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            logger.info(f"Created new session encryption key: {self.key_file}")
            return key
    
    def encrypt_session(self, session_data: SessionData) -> str:
        """Encrypt session data."""
        try:
            # Convert to dict and serialize
            session_dict = {
                'provider_id': session_data.provider_id,
                'provider_name': session_data.provider_name,
                'url': session_data.url,
                'username': session_data.username,
                'cookies': [
                    {
                        'name': cookie.name,
                        'value': cookie.value,
                        'domain': cookie.domain,
                        'path': cookie.path,
                        'expires': cookie.expires.isoformat() if cookie.expires else None,
                        'secure': cookie.secure,
                        'http_only': cookie.http_only,
                        'same_site': cookie.same_site
                    }
                    for cookie in session_data.cookies
                ],
                'local_storage': session_data.local_storage,
                'session_storage': session_data.session_storage,
                'created_at': session_data.created_at.isoformat(),
                'last_used': session_data.last_used.isoformat(),
                'last_validated': session_data.last_validated.isoformat() if session_data.last_validated else None,
                'is_valid': session_data.is_valid,
                'validation_failures': session_data.validation_failures,
                'user_agent': session_data.user_agent,
                'viewport': session_data.viewport,
                'timezone': session_data.timezone,
                'language': session_data.language
            }
            
            # Serialize and encrypt
            serialized = pickle.dumps(session_dict)
            encrypted = self._cipher.encrypt(serialized)
            return base64.urlsafe_b64encode(encrypted).decode()
            
        except Exception as e:
            logger.error(f"Failed to encrypt session data: {e}")
            raise
    
    def decrypt_session(self, encrypted_data: str) -> SessionData:
        """Decrypt session data."""
        try:
            # Decode and decrypt
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            session_dict = pickle.loads(decrypted)
            
            # Convert back to SessionData
            cookies = []
            for cookie_data in session_dict.get('cookies', []):
                cookies.append(SessionCookie(
                    name=cookie_data['name'],
                    value=cookie_data['value'],
                    domain=cookie_data['domain'],
                    path=cookie_data['path'],
                    expires=datetime.fromisoformat(cookie_data['expires']) if cookie_data['expires'] else None,
                    secure=cookie_data['secure'],
                    http_only=cookie_data['http_only'],
                    same_site=cookie_data['same_site']
                ))
            
            return SessionData(
                provider_id=session_dict['provider_id'],
                provider_name=session_dict['provider_name'],
                url=session_dict['url'],
                username=session_dict['username'],
                cookies=cookies,
                local_storage=session_dict.get('local_storage', {}),
                session_storage=session_dict.get('session_storage', {}),
                created_at=datetime.fromisoformat(session_dict['created_at']),
                last_used=datetime.fromisoformat(session_dict['last_used']),
                last_validated=datetime.fromisoformat(session_dict['last_validated']) if session_dict.get('last_validated') else None,
                is_valid=session_dict.get('is_valid', True),
                validation_failures=session_dict.get('validation_failures', 0),
                user_agent=session_dict.get('user_agent'),
                viewport=session_dict.get('viewport'),
                timezone=session_dict.get('timezone'),
                language=session_dict.get('language')
            )
            
        except Exception as e:
            logger.error(f"Failed to decrypt session data: {e}")
            raise


class SessionManager:
    """
    Manages persistent sessions for providers to avoid repeated authentication.
    """
    
    def __init__(self, storage_path: str = "data/sessions"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Session cache
        self.sessions: Dict[str, SessionData] = {}
        
        # Configuration
        self.session_timeout_hours = 24  # Sessions expire after 24 hours
        self.validation_interval_minutes = 30  # Validate sessions every 30 minutes
        self.max_validation_failures = 3  # Mark invalid after 3 failures
        
        # Encryption
        self.encryption = SessionEncryption()
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._validation_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the session manager."""
        logger.info("Starting session manager")
        
        # Load existing sessions
        await self._load_sessions()
        
        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._validation_task = asyncio.create_task(self._validation_loop())
        
        logger.info(f"Session manager started with {len(self.sessions)} sessions")
    
    async def stop(self):
        """Stop the session manager."""
        logger.info("Stopping session manager")
        
        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._validation_task:
            self._validation_task.cancel()
        
        # Save all sessions
        await self._save_all_sessions()
        
        logger.info("Session manager stopped")
    
    async def get_session(self, provider_id: str, username: str) -> Optional[SessionData]:
        """Get a valid session for the provider and username."""
        session_key = f"{provider_id}_{username}"
        
        session = self.sessions.get(session_key)
        if not session:
            return None
        
        # Check if session is still valid
        if not self._is_session_valid(session):
            logger.info(f"Session for {provider_id}/{username} is expired or invalid")
            await self.remove_session(provider_id, username)
            return None
        
        # Update last used time
        session.last_used = datetime.now()
        await self._save_session(session)
        
        return session
    
    async def save_session(self, session_data: SessionData):
        """Save a session."""
        session_key = f"{session_data.provider_id}_{session_data.username}"
        
        # Update metadata
        session_data.last_used = datetime.now()
        session_data.is_valid = True
        session_data.validation_failures = 0
        
        # Store in cache
        self.sessions[session_key] = session_data
        
        # Save to disk
        await self._save_session(session_data)
        
        logger.info(f"Saved session for {session_data.provider_id}/{session_data.username}")
    
    async def remove_session(self, provider_id: str, username: str):
        """Remove a session."""
        session_key = f"{provider_id}_{username}"
        
        # Remove from cache
        if session_key in self.sessions:
            del self.sessions[session_key]
        
        # Remove from disk
        session_file = self.storage_path / f"{session_key}.session"
        if session_file.exists():
            session_file.unlink()
        
        logger.info(f"Removed session for {provider_id}/{username}")
    
    async def validate_session(self, session_data: SessionData, browser_instance) -> bool:
        """Validate that a session is still working."""
        try:
            # Restore session to browser
            await self._restore_session_to_browser(session_data, browser_instance)
            
            # Navigate to the provider URL
            await browser_instance.navigate(session_data.url)
            await asyncio.sleep(2)
            
            # Check if we're still logged in (provider-specific logic)
            is_valid = await self._check_login_status(session_data, browser_instance)
            
            # Update validation status
            session_data.last_validated = datetime.now()
            if is_valid:
                session_data.validation_failures = 0
                session_data.is_valid = True
            else:
                session_data.validation_failures += 1
                if session_data.validation_failures >= self.max_validation_failures:
                    session_data.is_valid = False
            
            await self._save_session(session_data)
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error validating session for {session_data.provider_id}: {e}")
            session_data.validation_failures += 1
            if session_data.validation_failures >= self.max_validation_failures:
                session_data.is_valid = False
            await self._save_session(session_data)
            return False
    
    async def capture_session_from_browser(self, 
                                         provider_id: str,
                                         provider_name: str,
                                         url: str,
                                         username: str,
                                         browser_instance) -> SessionData:
        """Capture session data from a browser instance."""
        try:
            # Get cookies
            cookies = []
            browser_cookies = await browser_instance.get_cookies()
            
            for cookie in browser_cookies:
                cookies.append(SessionCookie(
                    name=cookie.get('name', ''),
                    value=cookie.get('value', ''),
                    domain=cookie.get('domain', ''),
                    path=cookie.get('path', '/'),
                    expires=datetime.fromtimestamp(cookie['expires']) if cookie.get('expires') else None,
                    secure=cookie.get('secure', False),
                    http_only=cookie.get('httpOnly', False),
                    same_site=cookie.get('sameSite')
                ))
            
            # Get storage data
            local_storage = await browser_instance.get_local_storage() or {}
            session_storage = await browser_instance.get_session_storage() or {}
            
            # Get browser state
            user_agent = await browser_instance.get_user_agent()
            viewport = await browser_instance.get_viewport()
            
            # Create session data
            session_data = SessionData(
                provider_id=provider_id,
                provider_name=provider_name,
                url=url,
                username=username,
                cookies=cookies,
                local_storage=local_storage,
                session_storage=session_storage,
                user_agent=user_agent,
                viewport=viewport
            )
            
            # Save the session
            await self.save_session(session_data)
            
            logger.info(f"Captured session for {provider_id}/{username} with {len(cookies)} cookies")
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to capture session for {provider_id}: {e}")
            raise
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions with their status."""
        sessions_info = []
        
        for session in self.sessions.values():
            sessions_info.append({
                'provider_id': session.provider_id,
                'provider_name': session.provider_name,
                'username': session.username,
                'url': session.url,
                'created_at': session.created_at.isoformat(),
                'last_used': session.last_used.isoformat(),
                'last_validated': session.last_validated.isoformat() if session.last_validated else None,
                'is_valid': session.is_valid,
                'validation_failures': session.validation_failures,
                'cookies_count': len(session.cookies),
                'has_local_storage': len(session.local_storage) > 0,
                'has_session_storage': len(session.session_storage) > 0
            })
        
        return sessions_info
    
    def _is_session_valid(self, session: SessionData) -> bool:
        """Check if a session is still valid."""
        if not session.is_valid:
            return False
        
        # Check if session has expired
        age = datetime.now() - session.created_at
        if age > timedelta(hours=self.session_timeout_hours):
            return False
        
        # Check validation failures
        if session.validation_failures >= self.max_validation_failures:
            return False
        
        return True
    
    async def _restore_session_to_browser(self, session_data: SessionData, browser_instance):
        """Restore session data to a browser instance."""
        try:
            # Navigate to domain first
            await browser_instance.navigate(session_data.url)
            await asyncio.sleep(1)
            
            # Set cookies
            for cookie in session_data.cookies:
                try:
                    cookie_dict = {
                        'name': cookie.name,
                        'value': cookie.value,
                        'domain': cookie.domain,
                        'path': cookie.path,
                        'secure': cookie.secure,
                        'httpOnly': cookie.http_only
                    }
                    
                    if cookie.expires:
                        cookie_dict['expires'] = int(cookie.expires.timestamp())
                    
                    if cookie.same_site:
                        cookie_dict['sameSite'] = cookie.same_site
                    
                    await browser_instance.set_cookie(cookie_dict)
                    
                except Exception as e:
                    logger.warning(f"Failed to set cookie {cookie.name}: {e}")
            
            # Set local storage
            if session_data.local_storage:
                await browser_instance.set_local_storage(session_data.local_storage)
            
            # Set session storage
            if session_data.session_storage:
                await browser_instance.set_session_storage(session_data.session_storage)
            
            logger.debug(f"Restored session for {session_data.provider_id}")
            
        except Exception as e:
            logger.error(f"Failed to restore session for {session_data.provider_id}: {e}")
            raise
    
    async def _check_login_status(self, session_data: SessionData, browser_instance) -> bool:
        """Check if we're still logged in (provider-specific logic)."""
        try:
            # Get current URL
            current_url = await browser_instance.get_current_url()
            
            # Basic heuristics for login status
            login_indicators = ['login', 'signin', 'auth', 'authenticate']
            logout_indicators = ['logout', 'signout', 'dashboard', 'profile', 'chat']
            
            current_url_lower = current_url.lower()
            
            # If we're on a login page, we're probably not logged in
            if any(indicator in current_url_lower for indicator in login_indicators):
                return False
            
            # If we're on a dashboard/chat page, we're probably logged in
            if any(indicator in current_url_lower for indicator in logout_indicators):
                return True
            
            # Try to find logout button or user menu (indicates logged in)
            logout_selectors = [
                '[data-testid*="logout"]',
                '[class*="logout"]',
                '[class*="user-menu"]',
                '[class*="profile"]',
                'button:contains("Logout")',
                'button:contains("Sign out")',
                'a:contains("Logout")',
                'a:contains("Sign out")'
            ]
            
            for selector in logout_selectors:
                try:
                    element = await browser_instance.find_element(selector)
                    if element:
                        return True
                except:
                    continue
            
            # Default to invalid if we can't determine
            return False
            
        except Exception as e:
            logger.error(f"Error checking login status for {session_data.provider_id}: {e}")
            return False
    
    async def _load_sessions(self):
        """Load sessions from disk."""
        try:
            session_files = list(self.storage_path.glob("*.session"))
            
            for session_file in session_files:
                try:
                    with open(session_file, 'r') as f:
                        encrypted_data = f.read()
                    
                    session_data = self.encryption.decrypt_session(encrypted_data)
                    
                    # Only load valid sessions
                    if self._is_session_valid(session_data):
                        session_key = f"{session_data.provider_id}_{session_data.username}"
                        self.sessions[session_key] = session_data
                    else:
                        # Remove invalid session file
                        session_file.unlink()
                        
                except Exception as e:
                    logger.error(f"Failed to load session from {session_file}: {e}")
                    # Remove corrupted session file
                    try:
                        session_file.unlink()
                    except:
                        pass
            
            logger.info(f"Loaded {len(self.sessions)} valid sessions")
            
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
    
    async def _save_session(self, session_data: SessionData):
        """Save a single session to disk."""
        try:
            session_key = f"{session_data.provider_id}_{session_data.username}"
            session_file = self.storage_path / f"{session_key}.session"
            
            encrypted_data = self.encryption.encrypt_session(session_data)
            
            with open(session_file, 'w') as f:
                f.write(encrypted_data)
                
        except Exception as e:
            logger.error(f"Failed to save session for {session_data.provider_id}: {e}")
    
    async def _save_all_sessions(self):
        """Save all sessions to disk."""
        for session_data in self.sessions.values():
            await self._save_session(session_data)
    
    async def _cleanup_loop(self):
        """Background task to cleanup expired sessions."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                expired_sessions = []
                for session_key, session in self.sessions.items():
                    if not self._is_session_valid(session):
                        expired_sessions.append(session_key)
                
                for session_key in expired_sessions:
                    session = self.sessions[session_key]
                    await self.remove_session(session.provider_id, session.username)
                
                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
    
    async def _validation_loop(self):
        """Background task to validate sessions periodically."""
        while True:
            try:
                await asyncio.sleep(self.validation_interval_minutes * 60)
                
                # This would require browser instances, so we'll skip automatic validation
                # Sessions will be validated when they're actually used
                logger.debug("Session validation loop running (validation on-demand)")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session validation: {e}")


# Global instance
session_manager: Optional[SessionManager] = None


async def get_session_manager() -> SessionManager:
    """Get or create the global session manager."""
    global session_manager
    
    if session_manager is None:
        storage_path = os.getenv("SESSION_STORAGE_PATH", "data/sessions")
        session_manager = SessionManager(storage_path)
        await session_manager.start()
    
    return session_manager


async def initialize_session_manager() -> SessionManager:
    """Initialize the session management system."""
    return await get_session_manager()


async def shutdown_session_manager():
    """Shutdown the session management system."""
    global session_manager
    if session_manager:
        await session_manager.stop()
        session_manager = None
