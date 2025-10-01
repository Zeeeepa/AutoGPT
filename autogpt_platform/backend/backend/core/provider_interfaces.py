"""
Core interfaces and abstractions for the AI-powered chat proxy system.

This module defines the fundamental interfaces that enable dynamic provider
management with AI-powered element detection and adaptive behavior.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import asyncio


class ProviderStatus(Enum):
    """Provider operational status."""
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class ElementType(Enum):
    """Types of UI elements the AI can detect."""
    LOGIN_EMAIL = "login_email"
    LOGIN_PASSWORD = "login_password"
    LOGIN_SUBMIT = "login_submit"
    CHAT_INPUT = "chat_input"
    SEND_BUTTON = "send_button"
    MESSAGE_CONTAINER = "message_container"
    RESPONSE_AREA = "response_area"
    ERROR_MESSAGE = "error_message"
    SUCCESS_INDICATOR = "success_indicator"


@dataclass
class ElementDetectionResult:
    """Result of AI-powered element detection."""
    element_type: ElementType
    selector: str
    confidence: float
    coordinates: Optional[Tuple[int, int]] = None
    attributes: Optional[Dict[str, str]] = None
    screenshot_path: Optional[str] = None
    detection_method: str = "ai"
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class ProviderConfiguration:
    """Configuration for a dynamic provider."""
    domain: str
    username: str
    password: str
    provider_id: Optional[str] = None
    display_name: Optional[str] = None
    base_url: Optional[str] = None
    login_url: Optional[str] = None
    chat_url: Optional[str] = None
    
    # AI detection hints (optional)
    ui_hints: Optional[Dict[str, Any]] = None
    custom_selectors: Optional[Dict[ElementType, str]] = None
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: Optional[List[str]] = None

    def __post_init__(self):
        if self.provider_id is None:
            self.provider_id = f"provider_{self.domain.replace('.', '_')}"
        if self.display_name is None:
            self.display_name = self.domain.title()
        if self.base_url is None:
            self.base_url = f"https://{self.domain}"
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class ChatMessage:
    """Represents a chat message."""
    content: str
    role: str = "user"  # user, assistant, system
    timestamp: Optional[datetime] = None
    message_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class ChatResponse:
    """Response from a chat provider."""
    content: str
    provider_id: str
    success: bool = True
    error_message: Optional[str] = None
    response_time: Optional[float] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AIElementDetector(ABC):
    """Abstract interface for AI-powered element detection."""

    @abstractmethod
    async def detect_elements(
        self, 
        page_url: str, 
        element_types: List[ElementType],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ElementDetectionResult]:
        """
        Detect UI elements on a page using AI.
        
        Args:
            page_url: URL of the page to analyze
            element_types: Types of elements to detect
            context: Additional context for detection
            
        Returns:
            List of detected elements with confidence scores
        """
        pass

    @abstractmethod
    async def verify_element(
        self, 
        page_url: str, 
        selector: str, 
        element_type: ElementType
    ) -> bool:
        """
        Verify that an element selector is still valid.
        
        Args:
            page_url: URL of the page
            selector: CSS selector to verify
            element_type: Expected element type
            
        Returns:
            True if element is valid and accessible
        """
        pass

    @abstractmethod
    async def adapt_to_changes(
        self, 
        page_url: str, 
        failed_selector: str, 
        element_type: ElementType
    ) -> Optional[ElementDetectionResult]:
        """
        Adapt to UI changes by finding new selectors.
        
        Args:
            page_url: URL of the page
            failed_selector: Selector that no longer works
            element_type: Type of element to find
            
        Returns:
            New element detection result or None if not found
        """
        pass


class ProviderAuthenticator(ABC):
    """Abstract interface for provider authentication."""

    @abstractmethod
    async def authenticate(
        self, 
        config: ProviderConfiguration,
        browser_session: Any
    ) -> Tuple[bool, Optional[str]]:
        """
        Authenticate with a provider using AI-powered automation.
        
        Args:
            config: Provider configuration
            browser_session: Browser session object
            
        Returns:
            Tuple of (success, error_message)
        """
        pass

    @abstractmethod
    async def verify_authentication(
        self, 
        config: ProviderConfiguration,
        browser_session: Any
    ) -> bool:
        """
        Verify that authentication is still valid.
        
        Args:
            config: Provider configuration
            browser_session: Browser session object
            
        Returns:
            True if authentication is valid
        """
        pass

    @abstractmethod
    async def refresh_session(
        self, 
        config: ProviderConfiguration,
        browser_session: Any
    ) -> bool:
        """
        Refresh authentication session if needed.
        
        Args:
            config: Provider configuration
            browser_session: Browser session object
            
        Returns:
            True if session was refreshed successfully
        """
        pass


class ChatProvider(ABC):
    """Abstract interface for chat providers."""

    @abstractmethod
    async def send_message(
        self, 
        message: ChatMessage,
        browser_session: Any
    ) -> ChatResponse:
        """
        Send a message to the chat provider.
        
        Args:
            message: Message to send
            browser_session: Browser session object
            
        Returns:
            Chat response from the provider
        """
        pass

    @abstractmethod
    async def get_response(
        self, 
        browser_session: Any,
        timeout: int = 30
    ) -> Optional[str]:
        """
        Get the response from the chat provider.
        
        Args:
            browser_session: Browser session object
            timeout: Maximum time to wait for response
            
        Returns:
            Response text or None if timeout
        """
        pass

    @abstractmethod
    async def is_ready(self, browser_session: Any) -> bool:
        """
        Check if the provider is ready to receive messages.
        
        Args:
            browser_session: Browser session object
            
        Returns:
            True if ready to receive messages
        """
        pass


class ProviderValidator(ABC):
    """Abstract interface for provider validation."""

    @abstractmethod
    async def validate_configuration(
        self, 
        config: ProviderConfiguration
    ) -> Tuple[bool, List[str]]:
        """
        Validate provider configuration.
        
        Args:
            config: Provider configuration to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        pass

    @abstractmethod
    async def test_provider(
        self, 
        config: ProviderConfiguration
    ) -> Dict[str, Any]:
        """
        Test provider functionality end-to-end.
        
        Args:
            config: Provider configuration to test
            
        Returns:
            Test results with success status and details
        """
        pass

    @abstractmethod
    async def health_check(
        self, 
        provider_id: str
    ) -> Dict[str, Any]:
        """
        Perform health check on a provider.
        
        Args:
            provider_id: ID of provider to check
            
        Returns:
            Health check results
        """
        pass


class ProviderManager(ABC):
    """Abstract interface for provider management."""

    @abstractmethod
    async def register_provider(
        self, 
        config: ProviderConfiguration
    ) -> str:
        """
        Register a new provider.
        
        Args:
            config: Provider configuration
            
        Returns:
            Provider ID
        """
        pass

    @abstractmethod
    async def get_provider(self, provider_id: str) -> Optional[ProviderConfiguration]:
        """Get provider configuration by ID."""
        pass

    @abstractmethod
    async def list_providers(
        self, 
        status: Optional[ProviderStatus] = None
    ) -> List[ProviderConfiguration]:
        """List all providers, optionally filtered by status."""
        pass

    @abstractmethod
    async def update_provider(
        self, 
        provider_id: str, 
        config: ProviderConfiguration
    ) -> bool:
        """Update provider configuration."""
        pass

    @abstractmethod
    async def remove_provider(self, provider_id: str) -> bool:
        """Remove a provider."""
        pass

    @abstractmethod
    async def get_provider_status(self, provider_id: str) -> ProviderStatus:
        """Get current status of a provider."""
        pass


class ScalingEngine(ABC):
    """Abstract interface for scaling engine."""

    @abstractmethod
    async def handle_request(
        self, 
        provider_id: str, 
        message: ChatMessage
    ) -> ChatResponse:
        """
        Handle a chat request with automatic scaling.
        
        Args:
            provider_id: ID of the provider to use
            message: Message to send
            
        Returns:
            Chat response
        """
        pass

    @abstractmethod
    async def get_available_capacity(self, provider_id: str) -> int:
        """Get available capacity for a provider."""
        pass

    @abstractmethod
    async def scale_up(self, provider_id: str, instances: int = 1) -> bool:
        """Scale up instances for a provider."""
        pass

    @abstractmethod
    async def scale_down(self, provider_id: str, instances: int = 1) -> bool:
        """Scale down instances for a provider."""
        pass


# Event system for provider lifecycle
class ProviderEvent(Enum):
    """Provider lifecycle events."""
    REGISTERED = "registered"
    AUTHENTICATED = "authenticated"
    AUTHENTICATION_FAILED = "authentication_failed"
    MESSAGE_SENT = "message_sent"
    MESSAGE_FAILED = "message_failed"
    SCALED_UP = "scaled_up"
    SCALED_DOWN = "scaled_down"
    ERROR = "error"
    REMOVED = "removed"


@dataclass
class ProviderEventData:
    """Data associated with provider events."""
    event: ProviderEvent
    provider_id: str
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ProviderEventHandler(ABC):
    """Abstract interface for handling provider events."""

    @abstractmethod
    async def handle_event(self, event_data: ProviderEventData) -> None:
        """Handle a provider event."""
        pass


# Configuration and settings
@dataclass
class AIProviderEngineConfig:
    """Configuration for the AI provider engine."""
    # AI detection settings
    stagehand_api_key: Optional[str] = None
    ai_detection_timeout: int = 30
    ai_confidence_threshold: float = 0.7
    
    # Browser settings
    browser_timeout: int = 60
    browser_headless: bool = True
    browser_user_agent: Optional[str] = None
    
    # Scaling settings
    max_concurrent_sessions: int = 10
    session_timeout: int = 300
    auto_scale_enabled: bool = True
    
    # Cloudflare settings
    cloudflare_api_token: Optional[str] = None
    cloudflare_account_id: Optional[str] = None
    use_cloudflare_scaling: bool = False
    
    # Storage settings
    provider_storage_path: str = "data/providers"
    session_storage_path: str = "data/sessions"
    
    # Monitoring settings
    enable_monitoring: bool = True
    metrics_collection_interval: int = 60
    health_check_interval: int = 300
