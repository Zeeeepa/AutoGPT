"""
Data models for the Chat Proxy system.
Handles multiple chat service accounts, load balancing, and session management.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, SecretStr
from backend.data.model import BaseDbModel


class ChatServiceType(str, Enum):
    """Supported chat services"""
    ZAI = "z.ai"
    QWEN = "qwen.ai"
    DEEPSEEK = "deepseek.com"
    K2THINK = "k2think.ai"
    GROK = "grok.com"


class AccountStatus(str, Enum):
    """Account status for health monitoring"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_USED = "least_used"
    HEALTH_BASED = "health_based"
    WEIGHTED = "weighted"


class ChatAccount(BaseDbModel):
    """Model for storing chat service account credentials"""
    
    service_type: ChatServiceType = Field(..., description="Type of chat service")
    email: str = Field(..., description="Account email/username")
    password: SecretStr = Field(..., description="Account password")
    
    # Service-specific configuration
    extra_config: Dict[str, Any] = Field(default_factory=dict, description="Service-specific configuration")
    
    # Session management
    session_data: Optional[Dict[str, Any]] = Field(default=None, description="Persistent session data")
    browserbase_session_id: Optional[str] = Field(default=None, description="Browserbase session ID")
    
    # Health monitoring
    status: AccountStatus = Field(default=AccountStatus.ACTIVE, description="Account status")
    last_used: Optional[datetime] = Field(default=None, description="Last time account was used")
    last_health_check: Optional[datetime] = Field(default=None, description="Last health check")
    error_count: int = Field(default=0, description="Consecutive error count")
    
    # Usage tracking
    request_count: int = Field(default=0, description="Total requests made with this account")
    success_count: int = Field(default=0, description="Successful requests")
    
    # Rate limiting
    rate_limit_reset: Optional[datetime] = Field(default=None, description="When rate limit resets")
    daily_usage: int = Field(default=0, description="Daily usage count")
    
    # Load balancing
    weight: float = Field(default=1.0, description="Weight for load balancing")
    priority: int = Field(default=0, description="Priority (higher = preferred)")


class ChatServiceConfig(BaseDbModel):
    """Configuration for each chat service"""
    
    service_type: ChatServiceType = Field(..., description="Type of chat service")
    base_url: str = Field(..., description="Base URL for the service")
    
    # Authentication configuration
    login_url: str = Field(..., description="Login page URL")
    chat_url: str = Field(..., description="Chat interface URL")
    
    # Dynamic element detection instructions
    login_instructions: Dict[str, str] = Field(
        default_factory=dict,
        description="Instructions for AI to find login elements"
    )
    chat_instructions: Dict[str, str] = Field(
        default_factory=dict,
        description="Instructions for AI to find chat elements"
    )
    
    # Service limits
    max_requests_per_hour: int = Field(default=100, description="Max requests per hour per account")
    max_requests_per_day: int = Field(default=1000, description="Max requests per day per account")
    
    # Load balancing
    load_balancing_strategy: LoadBalancingStrategy = Field(
        default=LoadBalancingStrategy.ROUND_ROBIN,
        description="Load balancing strategy for this service"
    )
    
    # Health check configuration
    health_check_interval: int = Field(default=300, description="Health check interval in seconds")
    max_consecutive_errors: int = Field(default=3, description="Max errors before marking inactive")
    
    # Session configuration
    session_timeout: int = Field(default=3600, description="Session timeout in seconds")
    max_concurrent_sessions: int = Field(default=5, description="Max concurrent sessions per account")


class ChatProxyRequest(BaseModel):
    """Internal request model for chat proxy"""
    
    service_type: ChatServiceType
    account_id: str
    message: str
    conversation_id: Optional[str] = None
    stream: bool = False
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    
    # Request metadata
    request_id: str = Field(default_factory=lambda: f"req_{datetime.now().timestamp()}")
    user_id: Optional[str] = None
    client_ip: Optional[str] = None


class ChatProxyResponse(BaseModel):
    """Internal response model for chat proxy"""
    
    request_id: str
    service_type: ChatServiceType
    account_id: str
    
    # Response data
    content: str
    conversation_id: Optional[str] = None
    model: Optional[str] = None
    
    # Metadata
    response_time: float
    tokens_used: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.now)


class LoadBalancerState(BaseModel):
    """State for load balancer"""
    
    service_type: ChatServiceType
    strategy: LoadBalancingStrategy
    
    # Round robin state
    current_index: int = 0
    
    # Usage tracking
    account_usage: Dict[str, int] = Field(default_factory=dict)
    
    # Health tracking
    healthy_accounts: List[str] = Field(default_factory=list)
    unhealthy_accounts: List[str] = Field(default_factory=list)
    
    # Last update
    last_updated: datetime = Field(default_factory=datetime.now)


# Default service configurations
DEFAULT_SERVICE_CONFIGS = {
    ChatServiceType.ZAI: ChatServiceConfig(
        service_type=ChatServiceType.ZAI,
        base_url="https://chat.z.ai",
        login_url="https://chat.z.ai/login",
        chat_url="https://chat.z.ai",
        login_instructions={
            "email_field": "Find the email input field, usually labeled 'Email' or 'Username'",
            "password_field": "Find the password input field, usually labeled 'Password'",
            "login_button": "Find the login or sign in button to submit the form",
            "success_indicator": "Look for successful login indicators like chat interface or user profile"
        },
        chat_instructions={
            "message_input": "Find the main text input area where users type their messages",
            "send_button": "Find the send button or enter key to submit the message",
            "response_area": "Find the area where AI responses appear, usually the latest message",
            "loading_indicator": "Look for loading indicators while AI is generating response"
        }
    ),
    
    ChatServiceType.QWEN: ChatServiceConfig(
        service_type=ChatServiceType.QWEN,
        base_url="https://chat.qwen.ai",
        login_url="https://chat.qwen.ai/login",
        chat_url="https://chat.qwen.ai",
        login_instructions={
            "email_field": "Find the email input field for Qwen login",
            "password_field": "Find the password input field for Qwen login",
            "login_button": "Find the login button to authenticate with Qwen",
            "success_indicator": "Check for successful login to Qwen chat interface"
        },
        chat_instructions={
            "message_input": "Find the message input field in Qwen chat interface",
            "send_button": "Find the send button to submit message to Qwen",
            "response_area": "Find where Qwen's AI responses are displayed",
            "loading_indicator": "Look for Qwen's response generation indicators"
        }
    ),
    
    ChatServiceType.DEEPSEEK: ChatServiceConfig(
        service_type=ChatServiceType.DEEPSEEK,
        base_url="https://chat.deepseek.com",
        login_url="https://chat.deepseek.com/sign_in",
        chat_url="https://chat.deepseek.com",
        login_instructions={
            "email_field": "Find the email input field for DeepSeek login",
            "password_field": "Find the password input field for DeepSeek login",
            "login_button": "Find the login button to authenticate with DeepSeek",
            "success_indicator": "Check for successful login to DeepSeek chat interface"
        },
        chat_instructions={
            "message_input": "Find the message input field in DeepSeek chat interface",
            "send_button": "Find the send button to submit message to DeepSeek",
            "response_area": "Find where DeepSeek's AI responses are displayed",
            "loading_indicator": "Look for DeepSeek's response generation indicators"
        }
    ),
    
    ChatServiceType.K2THINK: ChatServiceConfig(
        service_type=ChatServiceType.K2THINK,
        base_url="https://www.k2think.ai",
        login_url="https://www.k2think.ai/login",
        chat_url="https://www.k2think.ai/chat",
        login_instructions={
            "email_field": "Find the email input field for K2Think login",
            "password_field": "Find the password input field for K2Think login",
            "login_button": "Find the login button to authenticate with K2Think",
            "success_indicator": "Check for successful login to K2Think chat interface"
        },
        chat_instructions={
            "message_input": "Find the message input field in K2Think chat interface",
            "send_button": "Find the send button to submit message to K2Think",
            "response_area": "Find where K2Think's AI responses are displayed",
            "loading_indicator": "Look for K2Think's response generation indicators"
        }
    ),
    
    ChatServiceType.GROK: ChatServiceConfig(
        service_type=ChatServiceType.GROK,
        base_url="https://grok.com",
        login_url="https://grok.com/login",
        chat_url="https://grok.com",
        login_instructions={
            "email_field": "Find the email input field for Grok login",
            "password_field": "Find the password input field for Grok login",
            "login_button": "Find the login button to authenticate with Grok",
            "success_indicator": "Check for successful login to Grok chat interface"
        },
        chat_instructions={
            "message_input": "Find the message input field in Grok chat interface",
            "send_button": "Find the send button to submit message to Grok",
            "response_area": "Find where Grok's AI responses are displayed",
            "loading_indicator": "Look for Grok's response generation indicators"
        }
    )
}


# Real accounts for the 5 target services
DEFAULT_ACCOUNTS = {
    ChatServiceType.ZAI: [
        ChatAccount(
            id="zai_real_1",
            service_type=ChatServiceType.ZAI,
            email="developer@pixelium.uk",
            password="developer123?",
            status=AccountStatus.ACTIVE
        )
    ],
    ChatServiceType.QWEN: [
        ChatAccount(
            id="qwen_real_1", 
            service_type=ChatServiceType.QWEN,
            email="developer@pixelium.uk",
            password="developer1?",
            status=AccountStatus.ACTIVE
        )
    ],
    ChatServiceType.DEEPSEEK: [
        ChatAccount(
            id="deepseek_real_1",
            service_type=ChatServiceType.DEEPSEEK,
            email="zeeeepa+1@gmail.com", 
            password="developer123??",
            status=AccountStatus.ACTIVE
        )
    ],
    ChatServiceType.K2THINK: [
        ChatAccount(
            id="k2think_real_1",
            service_type=ChatServiceType.K2THINK,
            email="developer@pixelium.uk",
            password="developer123?",
            status=AccountStatus.ACTIVE
        )
    ],
    ChatServiceType.GROK: [
        ChatAccount(
            id="grok_real_1",
            service_type=ChatServiceType.GROK,
            email="developer@pixelium.uk",
            password="developer123??",
            status=AccountStatus.ACTIVE
        )
    ]
}
