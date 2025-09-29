"""
Dynamic Provider Management Service.

Handles runtime addition, authentication, and management of webchat providers
with automatic cookie persistence and Stagehand integration.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

from backend.data.dynamic_provider_models import (
    DynamicProvider,
    ProviderStatus,
    AuthenticationMethod,
    SessionData,
    CookieData,
    ProviderTestResult,
    SystemConfiguration,
    ModelMapping,
    ProviderMetrics
)
from backend.util.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from backend.util.intelligent_load_balancer import IntelligentLoadBalancer


logger = logging.getLogger(__name__)


class StagehandAuthenticator:
    """Handles automatic authentication using Stagehand"""
    
    def __init__(self, stagehand_api_key: Optional[str] = None):
        self.api_key = stagehand_api_key or os.getenv("STAGEHAND_API_KEY")
        if not self.api_key:
            logger.warning("No Stagehand API key provided - authentication will be limited")
    
    async def authenticate_provider(self, provider: DynamicProvider, browser_instance) -> Tuple[bool, Optional[str]]:
        """
        Authenticate provider using Stagehand automation.
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            logger.info(f"Starting authentication for provider '{provider.name}'")
            
            # Navigate to login URL or base URL
            login_url = provider.auth_config.login_url or provider.base_url
            await browser_instance.navigate(login_url)
            
            # Wait for page to load
            await asyncio.sleep(2)
            
            # Auto-detect login form if selectors not provided
            if not provider.auth_config.email_selector:
                await self._auto_detect_login_form(provider, browser_instance)
            
            # Fill in credentials
            success = await self._fill_credentials(provider, browser_instance)
            if not success:
                return False, "Failed to fill credentials"
            
            # Submit form
            success = await self._submit_login_form(provider, browser_instance)
            if not success:
                return False, "Failed to submit login form"
            
            # Wait for authentication result
            await asyncio.sleep(3)
            
            # Check authentication success
            is_authenticated = await self._check_authentication_success(provider, browser_instance)
            
            if is_authenticated:
                # Save cookies and session data
                await self._save_session_data(provider, browser_instance)
                logger.info(f"Successfully authenticated provider '{provider.name}'")
                return True, None
            else:
                error_msg = await self._get_authentication_error(provider, browser_instance)
                logger.error(f"Authentication failed for provider '{provider.name}': {error_msg}")
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Authentication error: {str(e)}"
            logger.error(f"Authentication failed for provider '{provider.name}': {error_msg}")
            return False, error_msg
    
    async def _auto_detect_login_form(self, provider: DynamicProvider, browser_instance):
        """Auto-detect login form elements"""
        try:
            # Common email/username selectors
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[name="username"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="username" i]',
                '#email',
                '#username',
                '.email-input',
                '.username-input'
            ]
            
            # Common password selectors
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                '#password',
                '.password-input'
            ]
            
            # Common submit button selectors
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:contains("Login")',
                'button:contains("Sign in")',
                'button:contains("Log in")',
                '.login-button',
                '.submit-button'
            ]
            
            # Try to find email/username field
            for selector in email_selectors:
                try:
                    element = await browser_instance.find_element(selector)
                    if element:
                        provider.auth_config.email_selector = selector
                        logger.info(f"Auto-detected email selector: {selector}")
                        break
                except:
                    continue
            
            # Try to find password field
            for selector in password_selectors:
                try:
                    element = await browser_instance.find_element(selector)
                    if element:
                        provider.auth_config.password_selector = selector
                        logger.info(f"Auto-detected password selector: {selector}")
                        break
                except:
                    continue
            
            # Try to find submit button
            for selector in submit_selectors:
                try:
                    element = await browser_instance.find_element(selector)
                    if element:
                        provider.auth_config.submit_selector = selector
                        logger.info(f"Auto-detected submit selector: {selector}")
                        break
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"Auto-detection failed for provider '{provider.name}': {e}")
    
    async def _fill_credentials(self, provider: DynamicProvider, browser_instance) -> bool:
        """Fill in login credentials"""
        try:
            # Fill email/username
            if provider.auth_config.email_selector and provider.auth_config.email:
                await browser_instance.type(
                    provider.auth_config.email_selector,
                    provider.auth_config.email
                )
                await asyncio.sleep(0.5)
            
            # Fill password
            if provider.auth_config.password_selector and provider.auth_config.password:
                await browser_instance.type(
                    provider.auth_config.password_selector,
                    provider.auth_config.password.get_secret_value()
                )
                await asyncio.sleep(0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to fill credentials for provider '{provider.name}': {e}")
            return False
    
    async def _submit_login_form(self, provider: DynamicProvider, browser_instance) -> bool:
        """Submit the login form"""
        try:
            if provider.auth_config.submit_selector:
                await browser_instance.click(provider.auth_config.submit_selector)
            else:
                # Try pressing Enter on password field
                if provider.auth_config.password_selector:
                    await browser_instance.press_key(provider.auth_config.password_selector, "Enter")
                else:
                    # Fallback: try common submit methods
                    await browser_instance.press_key("body", "Enter")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to submit login form for provider '{provider.name}': {e}")
            return False
    
    async def _check_authentication_success(self, provider: DynamicProvider, browser_instance) -> bool:
        """Check if authentication was successful"""
        try:
            current_url = await browser_instance.get_current_url()
            
            # Check success indicators
            if provider.auth_config.success_indicators:
                for indicator in provider.auth_config.success_indicators:
                    try:
                        element = await browser_instance.find_element(indicator)
                        if element:
                            return True
                    except:
                        continue
            
            # Check failure indicators
            if provider.auth_config.failure_indicators:
                for indicator in provider.auth_config.failure_indicators:
                    try:
                        element = await browser_instance.find_element(indicator)
                        if element:
                            return False
                    except:
                        continue
            
            # Fallback: check if URL changed (usually indicates success)
            login_url = provider.auth_config.login_url or provider.base_url
            if current_url != login_url and "login" not in current_url.lower():
                return True
            
            # Check for common error indicators
            error_selectors = [
                '.error',
                '.alert-danger',
                '.login-error',
                '[class*="error"]',
                '[id*="error"]'
            ]
            
            for selector in error_selectors:
                try:
                    element = await browser_instance.find_element(selector)
                    if element:
                        return False
                except:
                    continue
            
            # If no clear indicators, assume success if we're not on login page
            return "login" not in current_url.lower()
            
        except Exception as e:
            logger.error(f"Failed to check authentication success for provider '{provider.name}': {e}")
            return False
    
    async def _get_authentication_error(self, provider: DynamicProvider, browser_instance) -> str:
        """Get authentication error message"""
        try:
            error_selectors = [
                '.error',
                '.alert-danger',
                '.login-error',
                '.error-message',
                '[class*="error"]',
                '[id*="error"]'
            ]
            
            for selector in error_selectors:
                try:
                    element = await browser_instance.find_element(selector)
                    if element:
                        error_text = await browser_instance.get_text(element)
                        if error_text:
                            return error_text.strip()
                except:
                    continue
            
            return "Authentication failed - no specific error message found"
            
        except Exception as e:
            return f"Failed to get error message: {str(e)}"
    
    async def _save_session_data(self, provider: DynamicProvider, browser_instance):
        """Save session data including cookies"""
        try:
            # Get cookies
            cookies = await browser_instance.get_cookies()
            cookie_data = []
            
            for cookie in cookies:
                cookie_data.append(CookieData(
                    name=cookie.get('name', ''),
                    value=cookie.get('value', ''),
                    domain=cookie.get('domain', ''),
                    path=cookie.get('path', '/'),
                    expires=datetime.fromtimestamp(cookie['expires']) if cookie.get('expires') else None,
                    secure=cookie.get('secure', False),
                    http_only=cookie.get('httpOnly', False),
                    same_site=cookie.get('sameSite')
                ))
            
            # Get local storage
            local_storage = await browser_instance.get_local_storage()
            
            # Get session storage
            session_storage = await browser_instance.get_session_storage()
            
            # Create session data
            session_data = SessionData(
                session_id=f"{provider.id}_{int(time.time())}",
                cookies=cookie_data,
                local_storage=local_storage or {},
                session_storage=session_storage or {},
                user_agent=await browser_instance.get_user_agent(),
                viewport=await browser_instance.get_viewport(),
                created_at=datetime.now(),
                last_used=datetime.now(),
                is_valid=True
            )
            
            provider.session_data = session_data
            logger.info(f"Saved session data for provider '{provider.name}' with {len(cookie_data)} cookies")
            
        except Exception as e:
            logger.error(f"Failed to save session data for provider '{provider.name}': {e}")


class CookieManager:
    """Manages cookie persistence and restoration"""
    
    def __init__(self, storage_path: str = "data/cookies"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
    
    async def save_cookies(self, provider: DynamicProvider):
        """Save provider cookies to disk"""
        try:
            if not provider.session_data or not provider.session_data.cookies:
                return
            
            cookie_file = os.path.join(self.storage_path, f"{provider.id}_cookies.json")
            
            # Convert cookies to serializable format
            cookies_data = {
                'provider_id': provider.id,
                'provider_name': provider.name,
                'saved_at': datetime.now().isoformat(),
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
                    for cookie in provider.session_data.cookies
                ],
                'local_storage': provider.session_data.local_storage,
                'session_storage': provider.session_data.session_storage
            }
            
            with open(cookie_file, 'w') as f:
                json.dump(cookies_data, f, indent=2)
            
            logger.info(f"Saved cookies for provider '{provider.name}' to {cookie_file}")
            
        except Exception as e:
            logger.error(f"Failed to save cookies for provider '{provider.name}': {e}")
    
    async def load_cookies(self, provider: DynamicProvider) -> bool:
        """Load provider cookies from disk"""
        try:
            cookie_file = os.path.join(self.storage_path, f"{provider.id}_cookies.json")
            
            if not os.path.exists(cookie_file):
                return False
            
            with open(cookie_file, 'r') as f:
                cookies_data = json.load(f)
            
            # Check if cookies are not too old (30 days default)
            saved_at = datetime.fromisoformat(cookies_data['saved_at'])
            if datetime.now() - saved_at > timedelta(days=30):
                logger.info(f"Cookies for provider '{provider.name}' are too old, skipping load")
                return False
            
            # Convert back to cookie objects
            cookie_objects = []
            for cookie_data in cookies_data['cookies']:
                cookie_objects.append(CookieData(
                    name=cookie_data['name'],
                    value=cookie_data['value'],
                    domain=cookie_data['domain'],
                    path=cookie_data['path'],
                    expires=datetime.fromisoformat(cookie_data['expires']) if cookie_data['expires'] else None,
                    secure=cookie_data['secure'],
                    http_only=cookie_data['http_only'],
                    same_site=cookie_data['same_site']
                ))
            
            # Create session data
            provider.session_data = SessionData(
                session_id=f"{provider.id}_restored_{int(time.time())}",
                cookies=cookie_objects,
                local_storage=cookies_data.get('local_storage', {}),
                session_storage=cookies_data.get('session_storage', {}),
                created_at=saved_at,
                last_used=datetime.now(),
                is_valid=True
            )
            
            logger.info(f"Loaded {len(cookie_objects)} cookies for provider '{provider.name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load cookies for provider '{provider.name}': {e}")
            return False
    
    async def restore_cookies_to_browser(self, provider: DynamicProvider, browser_instance):
        """Restore cookies to browser instance"""
        try:
            if not provider.session_data or not provider.session_data.cookies:
                return False
            
            # Navigate to domain first
            domain_url = provider.base_url
            await browser_instance.navigate(domain_url)
            await asyncio.sleep(1)
            
            # Set cookies
            for cookie in provider.session_data.cookies:
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
                    logger.warning(f"Failed to set cookie '{cookie.name}' for provider '{provider.name}': {e}")
            
            # Set local storage
            if provider.session_data.local_storage:
                await browser_instance.set_local_storage(provider.session_data.local_storage)
            
            # Set session storage
            if provider.session_data.session_storage:
                await browser_instance.set_session_storage(provider.session_data.session_storage)
            
            logger.info(f"Restored session data for provider '{provider.name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore cookies for provider '{provider.name}': {e}")
            return False


class DynamicProviderManager:
    """
    Main service for managing dynamic providers.
    
    Features:
    - Runtime provider addition and removal
    - Automatic authentication with Stagehand
    - Cookie persistence and restoration
    - Provider health monitoring
    - Flexible model routing
    """
    
    def __init__(self):
        self.providers: Dict[str, DynamicProvider] = {}
        self.system_config = SystemConfiguration()
        self.authenticator = StagehandAuthenticator()
        self.cookie_manager = CookieManager()
        self.load_balancer = IntelligentLoadBalancer()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._session_cleanup_task: Optional[asyncio.Task] = None
        
        logger.info("Dynamic Provider Manager initialized")
    
    async def start(self):
        """Start the provider manager and background tasks"""
        logger.info("Starting Dynamic Provider Manager")
        
        # Start load balancer
        await self.load_balancer.start()
        
        # Start background tasks
        self._health_check_task = asyncio.create_task(self._health_check_monitor())
        self._session_cleanup_task = asyncio.create_task(self._session_cleanup_monitor())
        
        # Load existing providers (from database in production)
        await self._load_existing_providers()
        
        logger.info("Dynamic Provider Manager started successfully")
    
    async def stop(self):
        """Stop the provider manager and cleanup resources"""
        logger.info("Stopping Dynamic Provider Manager")
        
        # Cancel background tasks
        for task in [self._health_check_task, self._session_cleanup_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Stop load balancer
        await self.load_balancer.stop()
        
        # Save all provider sessions
        for provider in self.providers.values():
            await self.cookie_manager.save_cookies(provider)
        
        logger.info("Dynamic Provider Manager stopped")
    
    async def add_provider(self, provider_data: Dict[str, Any]) -> DynamicProvider:
        """Add a new dynamic provider"""
        try:
            # Create provider instance
            provider = DynamicProvider(**provider_data)
            
            # Generate model names if not provided
            if not provider.supported_models:
                provider.supported_models = provider.generate_model_names()
            
            # Add to providers dict
            self.providers[provider.id] = provider
            
            # Add to load balancer
            self.load_balancer.add_server(
                server_id=provider.id,
                weight=1.0,
                health_check_callback=lambda: self._check_provider_health(provider.id)
            )
            
            # Create circuit breaker
            self.circuit_breakers[provider.id] = CircuitBreaker(
                name=f"provider_{provider.name}",
                config=CircuitBreakerConfig(
                    failure_threshold=5,
                    recovery_timeout=60,
                    timeout=provider.timeout_seconds
                )
            )
            
            # Add model mappings
            for model_name in provider.supported_models:
                self.system_config.add_model_mapping(
                    model_name=model_name,
                    provider_id=provider.id,
                    priority=1,
                    is_exact_match=True
                )
            
            logger.info(f"Added provider '{provider.name}' with {len(provider.supported_models)} model mappings")
            
            # Try to authenticate if auto-authenticate is enabled
            if self.system_config.auto_authenticate:
                asyncio.create_task(self._authenticate_provider_async(provider.id))
            
            return provider
            
        except Exception as e:
            logger.error(f"Failed to add provider: {e}")
            raise
    
    async def remove_provider(self, provider_id: str) -> bool:
        """Remove a dynamic provider"""
        try:
            if provider_id not in self.providers:
                return False
            
            provider = self.providers[provider_id]
            
            # Remove from load balancer
            self.load_balancer.remove_server(provider_id)
            
            # Remove circuit breaker
            if provider_id in self.circuit_breakers:
                del self.circuit_breakers[provider_id]
            
            # Remove model mappings
            for model_name in provider.supported_models:
                self.system_config.remove_model_mapping(model_name, provider_id)
            
            # Save cookies before removal
            await self.cookie_manager.save_cookies(provider)
            
            # Remove from providers dict
            del self.providers[provider_id]
            
            logger.info(f"Removed provider '{provider.name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove provider {provider_id}: {e}")
            return False
