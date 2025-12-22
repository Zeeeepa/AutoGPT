"""
Dynamic Provider Management Models.

Supports runtime addition of webchat interfaces with automatic authentication,
cookie management, and flexible model routing.
"""

import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, SecretStr, validator
from backend.data.model import BaseDbModel


class ProviderStatus(str, Enum):
    """Dynamic provider status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    AUTHENTICATING = "authenticating"
    AUTH_FAILED = "auth_failed"
    TESTING = "testing"
    ERROR = "error"
    DISABLED = "disabled"


class AuthenticationMethod(str, Enum):
    """Authentication methods for providers"""
    EMAIL_PASSWORD = "email_password"
    USERNAME_PASSWORD = "username_password"
    API_KEY = "api_key"
    OAUTH = "oauth"
    CUSTOM = "custom"


class ProviderType(str, Enum):
    """Types of providers"""
    WEBCHAT = "webchat"
    API = "api"
    HYBRID = "hybrid"


class CookieData(BaseModel):
    """Cookie storage model"""
    name: str = Field(..., description="Cookie name")
    value: str = Field(..., description="Cookie value")
    domain: str = Field(..., description="Cookie domain")
    path: str = Field(default="/", description="Cookie path")
    expires: Optional[datetime] = Field(default=None, description="Cookie expiration")
    secure: bool = Field(default=False, description="Secure flag")
    http_only: bool = Field(default=False, description="HttpOnly flag")
    same_site: Optional[str] = Field(default=None, description="SameSite attribute")


class SessionData(BaseModel):
    """Browser session data"""
    session_id: str = Field(..., description="Unique session identifier")
    cookies: List[CookieData] = Field(default_factory=list, description="Session cookies")
    local_storage: Dict[str, Any] = Field(default_factory=dict, description="Local storage data")
    session_storage: Dict[str, Any] = Field(default_factory=dict, description="Session storage data")
    user_agent: Optional[str] = Field(default=None, description="User agent string")
    viewport: Optional[Dict[str, int]] = Field(default=None, description="Viewport dimensions")
    created_at: datetime = Field(default_factory=datetime.now, description="Session creation time")
    last_used: datetime = Field(default_factory=datetime.now, description="Last session usage")
    is_valid: bool = Field(default=True, description="Session validity status")


class AuthenticationConfig(BaseModel):
    """Authentication configuration for providers"""
    method: AuthenticationMethod = Field(..., description="Authentication method")
    email: Optional[str] = Field(default=None, description="Email/username")
    password: Optional[SecretStr] = Field(default=None, description="Password")
    api_key: Optional[SecretStr] = Field(default=None, description="API key")
    
    # Login flow configuration
    login_url: Optional[str] = Field(default=None, description="Login page URL")
    email_selector: Optional[str] = Field(default=None, description="Email input CSS selector")
    password_selector: Optional[str] = Field(default=None, description="Password input CSS selector")
    submit_selector: Optional[str] = Field(default=None, description="Submit button CSS selector")
    
    # Success detection
    success_indicators: List[str] = Field(default_factory=list, description="Success detection selectors")
    failure_indicators: List[str] = Field(default_factory=list, description="Failure detection selectors")
    
    # Additional configuration
    extra_config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific config")
    
    @validator('email')
    def validate_email_required(cls, v, values):
        if values.get('method') in [AuthenticationMethod.EMAIL_PASSWORD, AuthenticationMethod.USERNAME_PASSWORD]:
            if not v:
                raise ValueError('Email/username is required for email/username authentication')
        return v
    
    @validator('password')
    def validate_password_required(cls, v, values):
        if values.get('method') in [AuthenticationMethod.EMAIL_PASSWORD, AuthenticationMethod.USERNAME_PASSWORD]:
            if not v:
                raise ValueError('Password is required for email/password authentication')
        return v


class ProviderMetrics(BaseModel):
    """Provider performance metrics"""
    total_requests: int = Field(default=0, description="Total requests processed")
    successful_requests: int = Field(default=0, description="Successful requests")
    failed_requests: int = Field(default=0, description="Failed requests")
    avg_response_time: float = Field(default=0.0, description="Average response time in seconds")
    last_request_time: Optional[datetime] = Field(default=None, description="Last request timestamp")
    
    # Health metrics
    uptime_percentage: float = Field(default=100.0, description="Uptime percentage")
    consecutive_failures: int = Field(default=0, description="Consecutive failure count")
    last_health_check: Optional[datetime] = Field(default=None, description="Last health check time")
    
    # Performance tracking
    response_times: List[float] = Field(default_factory=list, description="Recent response times")
    error_messages: List[str] = Field(default_factory=list, description="Recent error messages")
    
    def calculate_success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0
    
    def add_request_result(self, success: bool, response_time: float, error_message: Optional[str] = None):
        """Add a request result to metrics"""
        self.total_requests += 1
        self.last_request_time = datetime.now()
        
        if success:
            self.successful_requests += 1
            self.consecutive_failures = 0
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1
            if error_message:
                self.error_messages.append(error_message)
                # Keep only last 10 error messages
                self.error_messages = self.error_messages[-10:]
        
        # Update response times (keep last 100)
        self.response_times.append(response_time)
        self.response_times = self.response_times[-100:]
        
        # Update average response time
        if self.response_times:
            self.avg_response_time = sum(self.response_times) / len(self.response_times)


class ModelMapping(BaseModel):
    """Model name to provider mapping"""
    model_name: str = Field(..., description="Model name (e.g., 'gpt-4', 'z.ai')")
    provider_id: str = Field(..., description="Target provider ID")
    priority: int = Field(default=1, description="Routing priority (higher = preferred)")
    is_exact_match: bool = Field(default=True, description="Exact match vs partial match")
    created_at: datetime = Field(default_factory=datetime.now, description="Mapping creation time")


class DynamicProvider(BaseDbModel):
    """Dynamic provider configuration model"""
    
    # Basic provider information
    name: str = Field(..., description="Provider display name")
    provider_type: ProviderType = Field(default=ProviderType.WEBCHAT, description="Provider type")
    base_url: str = Field(..., description="Base URL of the webchat interface")
    chat_url: Optional[str] = Field(default=None, description="Direct chat interface URL")
    
    # Authentication configuration
    auth_config: AuthenticationConfig = Field(..., description="Authentication configuration")
    
    # Status and health
    status: ProviderStatus = Field(default=ProviderStatus.INACTIVE, description="Current provider status")
    is_enabled: bool = Field(default=True, description="Whether provider is enabled")
    is_default: bool = Field(default=False, description="Whether this is the default provider")
    
    # Session management
    session_data: Optional[SessionData] = Field(default=None, description="Current session data")
    browser_instance_id: Optional[int] = Field(default=None, description="Assigned browser instance")
    
    # Performance and metrics
    metrics: ProviderMetrics = Field(default_factory=ProviderMetrics, description="Provider metrics")
    
    # Model mappings
    supported_models: List[str] = Field(default_factory=list, description="Supported model names")
    
    # Configuration
    timeout_seconds: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Delay between retries")
    
    # Selectors for chat interface
    chat_input_selector: Optional[str] = Field(default=None, description="Chat input CSS selector")
    send_button_selector: Optional[str] = Field(default=None, description="Send button CSS selector")
    response_selector: Optional[str] = Field(default=None, description="Response area CSS selector")
    
    # Additional metadata
    description: Optional[str] = Field(default=None, description="Provider description")
    tags: List[str] = Field(default_factory=list, description="Provider tags")
    extra_config: Dict[str, Any] = Field(default_factory=dict, description="Additional configuration")
    
    # Timestamps
    last_authenticated: Optional[datetime] = Field(default=None, description="Last successful authentication")
    last_tested: Optional[datetime] = Field(default=None, description="Last test query time")
    last_error: Optional[str] = Field(default=None, description="Last error message")
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Provider name must be at least 2 characters long')
        return v.strip()
    
    @validator('base_url')
    def validate_base_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Base URL must start with http:// or https://')
        return v
    
    def generate_model_names(self) -> List[str]:
        """Generate model names based on provider name"""
        base_name = self.name.lower().replace(' ', '-')
        return [
            base_name,
            f"{base_name}-chat",
            f"{base_name}-turbo",
            self.name.lower(),
            self.name.lower().replace(' ', ''),
        ]
    
    def is_healthy(self) -> bool:
        """Check if provider is healthy"""
        if not self.is_enabled or self.status in [ProviderStatus.ERROR, ProviderStatus.AUTH_FAILED]:
            return False
        
        # Check consecutive failures
        if self.metrics.consecutive_failures >= 5:
            return False
        
        # Check success rate
        if self.metrics.total_requests > 10 and self.metrics.calculate_success_rate() < 50:
            return False
        
        return True
    
    def needs_authentication(self) -> bool:
        """Check if provider needs authentication"""
        if self.status == ProviderStatus.AUTH_FAILED:
            return True
        
        if not self.last_authenticated:
            return True
        
        # Check if session is expired (24 hours)
        if datetime.now() - self.last_authenticated > timedelta(hours=24):
            return True
        
        return False


class ProviderTestResult(BaseModel):
    """Result of provider test query"""
    provider_id: str = Field(..., description="Provider ID")
    success: bool = Field(..., description="Test success status")
    response_time: float = Field(..., description="Response time in seconds")
    response_content: Optional[str] = Field(default=None, description="Test response content")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Test timestamp")
    
    # Additional test details
    test_query: str = Field(default="Hello, this is a test message.", description="Test query sent")
    authentication_status: bool = Field(default=False, description="Authentication status during test")
    browser_instance_id: Optional[int] = Field(default=None, description="Browser instance used")


class SystemConfiguration(BaseDbModel):
    """System-wide configuration for dynamic providers"""
    
    # Default provider settings
    default_provider_id: Optional[str] = Field(default=None, description="Default provider ID")
    fallback_provider_id: Optional[str] = Field(default=None, description="Fallback provider ID")
    
    # Model routing configuration
    model_mappings: List[ModelMapping] = Field(default_factory=list, description="Model to provider mappings")
    enable_fuzzy_matching: bool = Field(default=True, description="Enable fuzzy model name matching")
    
    # System behavior
    auto_authenticate: bool = Field(default=True, description="Auto-authenticate providers on startup")
    health_check_interval: int = Field(default=300, description="Health check interval in seconds")
    session_cleanup_interval: int = Field(default=3600, description="Session cleanup interval in seconds")
    
    # Cookie management
    cookie_retention_days: int = Field(default=30, description="Cookie retention period in days")
    auto_save_cookies: bool = Field(default=True, description="Automatically save cookies")
    
    # Performance settings
    max_concurrent_requests: int = Field(default=100, description="Maximum concurrent requests")
    request_timeout: int = Field(default=30, description="Default request timeout in seconds")
    
    # Logging and monitoring
    enable_detailed_logging: bool = Field(default=True, description="Enable detailed request logging")
    metrics_retention_days: int = Field(default=7, description="Metrics retention period in days")
    
    def get_model_mapping(self, model_name: str) -> Optional[ModelMapping]:
        """Get model mapping for a given model name"""
        # First try exact matches
        exact_matches = [m for m in self.model_mappings if m.model_name == model_name and m.is_exact_match]
        if exact_matches:
            return max(exact_matches, key=lambda x: x.priority)
        
        # Then try partial matches if fuzzy matching is enabled
        if self.enable_fuzzy_matching:
            partial_matches = [
                m for m in self.model_mappings 
                if not m.is_exact_match and (
                    model_name.lower() in m.model_name.lower() or 
                    m.model_name.lower() in model_name.lower()
                )
            ]
            if partial_matches:
                return max(partial_matches, key=lambda x: x.priority)
        
        return None
    
    def add_model_mapping(self, model_name: str, provider_id: str, priority: int = 1, is_exact_match: bool = True):
        """Add a new model mapping"""
        mapping = ModelMapping(
            model_name=model_name,
            provider_id=provider_id,
            priority=priority,
            is_exact_match=is_exact_match
        )
        self.model_mappings.append(mapping)
    
    def remove_model_mapping(self, model_name: str, provider_id: str):
        """Remove a model mapping"""
        self.model_mappings = [
            m for m in self.model_mappings 
            if not (m.model_name == model_name and m.provider_id == provider_id)
        ]
