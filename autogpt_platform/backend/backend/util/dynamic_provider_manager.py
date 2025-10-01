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
import uuid
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

    async def _health_check_monitor(self):
        """Background task to monitor provider health."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                for provider_id, provider in self.providers.items():
                    if not provider.is_enabled:
                        continue
                    
                    try:
                        # Perform health check
                        is_healthy = await self._check_provider_health(provider_id)
                        
                        if is_healthy:
                            provider.status = ProviderStatus.ACTIVE
                            provider.metrics.consecutive_failures = 0
                            provider.metrics.last_success_time = datetime.now()
                        else:
                            provider.metrics.consecutive_failures += 1
                            
                            # Update status based on failure count
                            if provider.metrics.consecutive_failures >= 3:
                                provider.status = ProviderStatus.ERROR
                                logger.warning(f"Provider {provider.name} marked as ERROR after {provider.metrics.consecutive_failures} consecutive failures")
                            elif provider.metrics.consecutive_failures >= 1:
                                provider.status = ProviderStatus.DEGRADED
                    
                    except Exception as e:
                        logger.error(f"Health check failed for provider {provider.name}: {e}")
                        provider.metrics.consecutive_failures += 1
                        provider.status = ProviderStatus.ERROR
                
            except Exception as e:
                logger.error(f"Health check monitor error: {e}")

    async def _session_cleanup_monitor(self):
        """Background task to cleanup expired sessions."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                current_time = datetime.now()
                
                for provider in self.providers.values():
                    if not provider.session_data:
                        continue
                    
                    # Check if session is expired (24 hours default)
                    session_age = current_time - provider.session_data.created_at
                    if session_age > timedelta(hours=24):
                        logger.info(f"Cleaning up expired session for provider {provider.name}")
                        provider.session_data = None
                        provider.status = ProviderStatus.INACTIVE
                    
                    # Check if session is marked as invalid
                    elif not provider.session_data.is_valid:
                        logger.info(f"Cleaning up invalid session for provider {provider.name}")
                        provider.session_data = None
                        provider.status = ProviderStatus.INACTIVE
                
            except Exception as e:
                logger.error(f"Session cleanup monitor error: {e}")

    async def _load_existing_providers(self):
        """Load existing providers from persistent storage."""
        try:
            # In a production system, this would load from database
            # For now, we'll create some default providers if none exist
            
            if not self.providers:
                logger.info("No existing providers found, initializing with default configuration")
                
                # This would typically load from database or configuration file
                # For demo purposes, we'll leave this empty and let providers be added dynamically
                pass
            else:
                logger.info(f"Loaded {len(self.providers)} existing providers")
                
                # Restore sessions for existing providers
                for provider in self.providers.values():
                    try:
                        # Try to load saved cookies
                        cookies_loaded = await self.cookie_manager.load_cookies(provider)
                        if cookies_loaded:
                            logger.info(f"Restored session for provider {provider.name}")
                        else:
                            # Mark for re-authentication if auto-authenticate is enabled
                            if self.system_config.auto_authenticate:
                                asyncio.create_task(self._authenticate_provider_async(provider.id))
                    except Exception as e:
                        logger.warning(f"Failed to restore session for provider {provider.name}: {e}")
                
        except Exception as e:
            logger.error(f"Failed to load existing providers: {e}")

    async def _check_provider_health(self, provider_id: str) -> bool:
        """Check if a provider is healthy and responsive."""
        try:
            provider = self.providers.get(provider_id)
            if not provider:
                return False
            
            # Use circuit breaker to check health
            circuit_breaker = self.circuit_breakers.get(provider_id)
            if circuit_breaker and circuit_breaker.is_open():
                return False
            
            # Check if provider has valid session
            if not provider.session_data or not provider.session_data.is_valid:
                return False
            
            # Check if provider is enabled
            if not provider.is_enabled:
                return False
            
            # Check recent error rate
            if provider.metrics.consecutive_failures >= 5:
                return False
            
            # Check success rate
            if (provider.metrics.total_requests > 10 and 
                provider.metrics.calculate_success_rate() < 0.5):
                return False
            
            # Additional health checks could be added here
            # For example, making a test request to the provider
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed for provider {provider_id}: {e}")
            return False

    async def _authenticate_provider_async(self, provider_id: str):
        """Asynchronously authenticate a provider."""
        try:
            provider = self.providers.get(provider_id)
            if not provider:
                logger.error(f"Provider {provider_id} not found for authentication")
                return
            
            logger.info(f"Starting async authentication for provider {provider.name}")
            
            # This would typically get a browser instance from the browser manager
            # For now, we'll simulate the authentication process
            
            # Mark provider as authenticating
            provider.status = ProviderStatus.AUTHENTICATING
            
            # Simulate authentication delay
            await asyncio.sleep(2)
            
            # Use the authenticator to perform authentication
            # In a real implementation, this would use a browser instance
            success = await self._simulate_authentication(provider)
            
            if success:
                provider.status = ProviderStatus.ACTIVE
                provider.metrics.last_success_time = datetime.now()
                provider.metrics.consecutive_failures = 0
                logger.info(f"Successfully authenticated provider {provider.name}")
            else:
                provider.status = ProviderStatus.AUTH_FAILED
                provider.metrics.consecutive_failures += 1
                logger.error(f"Authentication failed for provider {provider.name}")
            
        except Exception as e:
            logger.error(f"Async authentication failed for provider {provider_id}: {e}")
            if provider_id in self.providers:
                self.providers[provider_id].status = ProviderStatus.ERROR

    async def _simulate_authentication(self, provider: DynamicProvider) -> bool:
        """Simulate authentication process for a provider."""
        try:
            # This is a simplified simulation
            # In a real implementation, this would use the StagehandAuthenticator
            # with an actual browser instance
            
            # Check if provider has authentication configuration
            if not provider.auth_config or not provider.auth_config.email:
                logger.warning(f"Provider {provider.name} has no authentication configuration")
                return False
            
            # Simulate authentication success/failure based on configuration
            # In reality, this would attempt to log in to the actual service
            
            # Create mock session data
            provider.session_data = SessionData(
                session_id=f"sim_{provider.id}_{int(time.time())}",
                cookies=[],
                local_storage={},
                session_storage={},
                created_at=datetime.now(),
                last_used=datetime.now(),
                is_valid=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Simulated authentication failed for provider {provider.name}: {e}")
            return False

    async def authenticate_provider(self, provider_id: str, browser_instance=None) -> Tuple[bool, Optional[str]]:
        """Authenticate a provider using browser automation."""
        try:
            provider = self.providers.get(provider_id)
            if not provider:
                return False, f"Provider {provider_id} not found"
            
            if not browser_instance:
                return False, "Browser instance is required for authentication"
            
            # Use the authenticator to perform authentication
            success, error_message = await self.authenticator.authenticate_provider(provider, browser_instance)
            
            if success:
                provider.status = ProviderStatus.ACTIVE
                provider.metrics.last_success_time = datetime.now()
                provider.metrics.consecutive_failures = 0
                
                # Save cookies
                await self.cookie_manager.save_cookies(provider)
                
                logger.info(f"Successfully authenticated provider {provider.name}")
            else:
                provider.status = ProviderStatus.AUTH_FAILED
                provider.metrics.consecutive_failures += 1
                logger.error(f"Authentication failed for provider {provider.name}: {error_message}")
            
            return success, error_message
            
        except Exception as e:
            error_message = f"Authentication error for provider {provider_id}: {str(e)}"
            logger.error(error_message)
            
            if provider_id in self.providers:
                self.providers[provider_id].status = ProviderStatus.ERROR
                self.providers[provider_id].metrics.consecutive_failures += 1
            
            return False, error_message

    async def get_provider_for_model(self, model_name: str) -> Optional[DynamicProvider]:
        """Get the best available provider for a specific model."""
        try:
            # Find providers that support this model
            matching_providers = []
            
            for provider in self.providers.values():
                if (provider.is_enabled and 
                    provider.status == ProviderStatus.ACTIVE and
                    model_name in provider.supported_models):
                    matching_providers.append(provider)
            
            if not matching_providers:
                return None
            
            # Use load balancer to select best provider
            provider_ids = [p.id for p in matching_providers]
            selected_id = await self.load_balancer.select_server(provider_ids)
            
            return next((p for p in matching_providers if p.id == selected_id), None)
            
        except Exception as e:
            logger.error(f"Failed to get provider for model {model_name}: {e}")
            return None

    async def execute_request(self, provider_id: str, request_data: dict, browser_instance=None) -> dict:
        """Execute a request using a specific provider."""
        try:
            provider = self.providers.get(provider_id)
            if not provider:
                raise Exception(f"Provider {provider_id} not found")
            
            if not provider.is_enabled or provider.status != ProviderStatus.ACTIVE:
                raise Exception(f"Provider {provider.name} is not available")
            
            # Use circuit breaker
            circuit_breaker = self.circuit_breakers.get(provider_id)
            if circuit_breaker and circuit_breaker.is_open():
                raise Exception(f"Provider {provider.name} circuit breaker is open")
            
            start_time = time.time()
            
            try:
                # Update metrics
                provider.metrics.total_requests += 1
                provider.metrics.last_request_time = datetime.now()
                
                # Restore session if needed
                if browser_instance and provider.session_data:
                    await self.cookie_manager.restore_cookies_to_browser(provider, browser_instance)
                
                # Execute the actual request (simplified)
                # In a real implementation, this would interact with the browser instance
                # to navigate to the provider's chat interface and send the message
                
                response_data = {
                    "id": f"req-{uuid.uuid4().hex[:8]}",
                    "provider": provider.name,
                    "model": request_data.get("model", "unknown"),
                    "response": f"Response from {provider.name}",
                    "timestamp": datetime.now().isoformat()
                }
                
                # Update success metrics
                response_time = time.time() - start_time
                provider.metrics.response_times.append(response_time)
                provider.metrics.last_success_time = datetime.now()
                
                # Reset consecutive failures on success
                provider.metrics.consecutive_failures = 0
                
                return response_data
                
            except Exception as e:
                # Update error metrics
                provider.metrics.error_count += 1
                provider.metrics.consecutive_failures += 1
                
                # Update circuit breaker
                if circuit_breaker:
                    circuit_breaker.record_failure()
                
                raise
            
        except Exception as e:
            logger.error(f"Request execution failed for provider {provider_id}: {e}")
            raise

    def get_all_providers(self) -> List[DynamicProvider]:
        """Get all registered providers."""
        return list(self.providers.values())

    def get_active_providers(self) -> List[DynamicProvider]:
        """Get all active providers."""
        return [p for p in self.providers.values() 
                if p.is_enabled and p.status == ProviderStatus.ACTIVE]

    def get_provider_metrics(self, provider_id: str) -> Optional[ProviderMetrics]:
        """Get metrics for a specific provider."""
        provider = self.providers.get(provider_id)
        return provider.metrics if provider else None

    def get_system_status(self) -> dict:
        """Get overall system status."""
        total_providers = len(self.providers)
        active_providers = len(self.get_active_providers())
        
        return {
            "total_providers": total_providers,
            "active_providers": active_providers,
            "inactive_providers": total_providers - active_providers,
            "system_config": {
                "auto_authenticate": self.system_config.auto_authenticate,
                "max_concurrent_requests": self.system_config.max_concurrent_requests,
                "default_timeout": self.system_config.default_timeout_seconds
            },
            "providers": {
                provider.id: {
                    "name": provider.name,
                    "status": provider.status.value,
                    "is_enabled": provider.is_enabled,
                    "supported_models": provider.supported_models,
                    "metrics": {
                        "total_requests": provider.metrics.total_requests,
                        "error_count": provider.metrics.error_count,
                        "success_rate": provider.metrics.calculate_success_rate(),
                        "avg_response_time": provider.metrics.calculate_avg_response_time(),
                        "consecutive_failures": provider.metrics.consecutive_failures
                    }
                }
                for provider in self.providers.values()
            }
        }
