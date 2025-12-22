"""
Browser Instance Manager for handling multiple headless browser instances
with unique fingerprints and provider isolation.
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import json
import random

from backend.data.chat_proxy_models import ChatServiceType
from backend.blocks.chat_proxy.blocks import (
    ChatProxyLoginBlock,
    ChatProxySendMessageBlock,
    ChatProxyHealthCheckBlock
)


logger = logging.getLogger(__name__)


@dataclass
class BrowserFingerprint:
    """Browser fingerprint configuration for anti-detection."""
    user_agent: str
    viewport_width: int
    viewport_height: int
    timezone: str
    language: str
    platform: str
    device_memory: int
    hardware_concurrency: int
    color_depth: int
    pixel_ratio: float


@dataclass
class BrowserInstance:
    """Represents a single browser instance with its configuration."""
    instance_id: int
    fingerprint: BrowserFingerprint
    is_active: bool = False
    session_data: Dict[str, any] = None
    startup_time: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    provider_sessions: Dict[ChatServiceType, str] = None
    
    def __post_init__(self):
        if self.session_data is None:
            self.session_data = {}
        if self.provider_sessions is None:
            self.provider_sessions = {}


class BrowserInstanceManager:
    """
    Manages multiple browser instances with unique fingerprints.
    Each instance can handle multiple providers with isolated sessions.
    """
    
    def __init__(self):
        self.instances: Dict[int, BrowserInstance] = {}
        self.fingerprints = self._generate_fingerprints()
        
        # Browser automation blocks
        self.login_block = ChatProxyLoginBlock()
        self.message_block = ChatProxySendMessageBlock()
        self.health_block = ChatProxyHealthCheckBlock()
        
        # Instance locks for thread safety
        self.instance_locks: Dict[int, asyncio.Lock] = {}
    
    def _generate_fingerprints(self) -> List[BrowserFingerprint]:
        """Generate unique fingerprints for each browser instance."""
        fingerprints = []
        
        # Predefined realistic configurations
        configs = [
            {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": (1920, 1080),
                "timezone": "America/New_York",
                "language": "en-US",
                "platform": "Win32",
                "device_memory": 8,
                "hardware_concurrency": 8,
                "color_depth": 24,
                "pixel_ratio": 1.0
            },
            {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": (1440, 900),
                "timezone": "America/Los_Angeles",
                "language": "en-US",
                "platform": "MacIntel",
                "device_memory": 16,
                "hardware_concurrency": 12,
                "color_depth": 30,
                "pixel_ratio": 2.0
            },
            {
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": (1366, 768),
                "timezone": "Europe/London",
                "language": "en-GB",
                "platform": "Linux x86_64",
                "device_memory": 4,
                "hardware_concurrency": 4,
                "color_depth": 24,
                "pixel_ratio": 1.0
            }
        ]
        
        for i, config in enumerate(configs):
            fingerprint = BrowserFingerprint(
                user_agent=config["user_agent"],
                viewport_width=config["viewport"][0],
                viewport_height=config["viewport"][1],
                timezone=config["timezone"],
                language=config["language"],
                platform=config["platform"],
                device_memory=config["device_memory"],
                hardware_concurrency=config["hardware_concurrency"],
                color_depth=config["color_depth"],
                pixel_ratio=config["pixel_ratio"]
            )
            fingerprints.append(fingerprint)
        
        return fingerprints
    
    async def start_instance(self, instance_id: int) -> bool:
        """
        Start a browser instance with unique fingerprint.
        
        Args:
            instance_id: ID of the instance to start (1, 2, or 3)
            
        Returns:
            True if started successfully, False otherwise
        """
        if instance_id in self.instances and self.instances[instance_id].is_active:
            logger.warning(f"Instance {instance_id} is already active")
            return True
        
        if instance_id < 1 or instance_id > 3:
            logger.error(f"Invalid instance ID: {instance_id}. Must be 1, 2, or 3")
            return False
        
        try:
            # Get fingerprint for this instance
            fingerprint = self.fingerprints[instance_id - 1]
            
            # Create browser instance
            instance = BrowserInstance(
                instance_id=instance_id,
                fingerprint=fingerprint,
                is_active=True,
                startup_time=datetime.now(),
                last_activity=datetime.now()
            )
            
            # Create instance lock
            self.instance_locks[instance_id] = asyncio.Lock()
            
            # Initialize browser with fingerprint
            await self._initialize_browser_instance(instance)
            
            # Store instance
            self.instances[instance_id] = instance
            
            logger.info(f"Browser Instance {instance_id} started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Browser Instance {instance_id}: {e}")
            return False
    
    async def stop_instance(self, instance_id: int) -> bool:
        """
        Stop a browser instance and cleanup resources.
        
        Args:
            instance_id: ID of the instance to stop
            
        Returns:
            True if stopped successfully, False otherwise
        """
        if instance_id not in self.instances:
            logger.warning(f"Instance {instance_id} not found")
            return True
        
        try:
            instance = self.instances[instance_id]
            
            # Cleanup browser sessions
            await self._cleanup_browser_instance(instance)
            
            # Mark as inactive
            instance.is_active = False
            
            # Remove from active instances
            del self.instances[instance_id]
            
            # Remove lock
            if instance_id in self.instance_locks:
                del self.instance_locks[instance_id]
            
            logger.info(f"Browser Instance {instance_id} stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop Browser Instance {instance_id}: {e}")
            return False
    
    async def execute_request(self, instance_id: int, service_type: ChatServiceType, request_data: dict) -> dict:
        """
        Execute a request on a specific browser instance.
        
        Args:
            instance_id: ID of the browser instance
            service_type: Type of service to use
            request_data: Request payload
            
        Returns:
            Response from the provider
        """
        if instance_id not in self.instances:
            raise ValueError(f"Browser Instance {instance_id} not found")
        
        instance = self.instances[instance_id]
        if not instance.is_active:
            raise ValueError(f"Browser Instance {instance_id} is not active")
        
        # Use instance lock to prevent concurrent access
        async with self.instance_locks[instance_id]:
            try:
                # Update last activity
                instance.last_activity = datetime.now()
                
                # Check if we have a session for this provider
                session_id = instance.provider_sessions.get(service_type)
                
                if not session_id:
                    # Login to the provider
                    session_id = await self._login_to_provider(instance, service_type)
                    instance.provider_sessions[service_type] = session_id
                
                # Execute the request
                response = await self._send_message(instance, service_type, session_id, request_data)
                
                return response
                
            except Exception as e:
                logger.error(f"Request failed on Instance {instance_id} for {service_type}: {e}")
                
                # Clear session on error (will retry login next time)
                if service_type in instance.provider_sessions:
                    del instance.provider_sessions[service_type]
                
                raise
    
    async def _initialize_browser_instance(self, instance: BrowserInstance):
        """Initialize browser instance with fingerprint configuration."""
        fingerprint = instance.fingerprint
        
        # Configure browser environment variables for Stagehand
        browser_config = {
            "user_agent": fingerprint.user_agent,
            "viewport": {
                "width": fingerprint.viewport_width,
                "height": fingerprint.viewport_height
            },
            "timezone": fingerprint.timezone,
            "language": fingerprint.language,
            "platform": fingerprint.platform,
            "device_memory": fingerprint.device_memory,
            "hardware_concurrency": fingerprint.hardware_concurrency,
            "color_depth": fingerprint.color_depth,
            "device_scale_factor": fingerprint.pixel_ratio
        }
        
        # Store browser config in instance session data
        instance.session_data["browser_config"] = browser_config
        
        logger.info(f"Browser Instance {instance.instance_id} initialized with fingerprint: "
                   f"{fingerprint.platform}, {fingerprint.viewport_width}x{fingerprint.viewport_height}")
    
    async def _cleanup_browser_instance(self, instance: BrowserInstance):
        """Cleanup browser instance resources."""
        try:
            # Close all provider sessions
            for service_type, session_id in instance.provider_sessions.items():
                try:
                    # Attempt graceful logout (optional)
                    logger.debug(f"Cleaning up session {session_id} for {service_type}")
                except Exception as e:
                    logger.warning(f"Error cleaning up session for {service_type}: {e}")
            
            # Clear session data
            instance.provider_sessions.clear()
            instance.session_data.clear()
            
            logger.info(f"Browser Instance {instance.instance_id} cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error cleaning up Browser Instance {instance.instance_id}: {e}")
    
    async def _login_to_provider(self, instance: BrowserInstance, service_type: ChatServiceType) -> str:
        """Login to a specific provider on the browser instance."""
        from backend.data.chat_proxy_models import DEFAULT_ACCOUNTS, DEFAULT_SERVICE_CONFIGS
        
        try:
            # Get account credentials
            accounts = DEFAULT_ACCOUNTS.get(service_type, [])
            if not accounts:
                raise ValueError(f"No accounts configured for {service_type}")
            
            account = accounts[0]  # Use first account
            
            # Apply browser fingerprint configuration
            browser_config = instance.session_data.get("browser_config", {})
            
            # Execute login with fingerprint
            login_result = await self.login_block.run(
                service_type=service_type,
                email=account.email,
                password=account.password,
                browser_config=browser_config  # Pass fingerprint config
            )
            
            if not login_result.get("success", False):
                raise Exception(f"Login failed: {login_result.get('error', 'Unknown error')}")
            
            session_id = login_result.get("session_id")
            logger.info(f"Successfully logged into {service_type} on Instance {instance.instance_id}")
            
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to login to {service_type} on Instance {instance.instance_id}: {e}")
            raise
    
    async def _send_message(self, instance: BrowserInstance, service_type: ChatServiceType, 
                           session_id: str, request_data: dict) -> dict:
        """Send a message to the provider."""
        try:
            # Extract message from request data (OpenAI format)
            messages = request_data.get("messages", [])
            if not messages:
                raise ValueError("No messages in request")
            
            # Get the last user message
            user_message = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            if not user_message:
                raise ValueError("No user message found")
            
            # Apply browser fingerprint configuration
            browser_config = instance.session_data.get("browser_config", {})
            
            # Send message with fingerprint
            message_result = await self.message_block.run(
                service_type=service_type,
                session_id=session_id,
                message=user_message,
                max_wait_time=30,
                browser_config=browser_config  # Pass fingerprint config
            )
            
            if not message_result.get("success", False):
                raise Exception(f"Message failed: {message_result.get('error', 'Unknown error')}")
            
            # Format response in OpenAI format
            response_text = message_result.get("response", "")
            
            openai_response = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(datetime.now().timestamp()),
                "model": request_data.get("model", service_type.value),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response_text
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": len(user_message.split()),
                    "completion_tokens": len(response_text.split()),
                    "total_tokens": len(user_message.split()) + len(response_text.split())
                }
            }
            
            return openai_response
            
        except Exception as e:
            logger.error(f"Failed to send message to {service_type} on Instance {instance.instance_id}: {e}")
            raise
    
    async def health_check_instance(self, instance_id: int) -> dict:
        """Perform health check on a browser instance."""
        if instance_id not in self.instances:
            return {"healthy": False, "error": "Instance not found"}
        
        instance = self.instances[instance_id]
        if not instance.is_active:
            return {"healthy": False, "error": "Instance not active"}
        
        try:
            # Check each provider session
            provider_health = {}
            
            for service_type, session_id in instance.provider_sessions.items():
                try:
                    health_result = await self.health_block.run(
                        service_type=service_type,
                        session_id=session_id
                    )
                    provider_health[service_type.value] = health_result.get("healthy", False)
                except Exception as e:
                    provider_health[service_type.value] = False
                    logger.warning(f"Health check failed for {service_type} on Instance {instance_id}: {e}")
            
            overall_healthy = len(provider_health) > 0 and any(provider_health.values())
            
            return {
                "healthy": overall_healthy,
                "instance_id": instance_id,
                "active_sessions": len(instance.provider_sessions),
                "provider_health": provider_health,
                "last_activity": instance.last_activity.isoformat() if instance.last_activity else None,
                "uptime_minutes": (datetime.now() - instance.startup_time).total_seconds() / 60 if instance.startup_time else 0
            }
            
        except Exception as e:
            logger.error(f"Health check failed for Instance {instance_id}: {e}")
            return {"healthy": False, "error": str(e)}
    
    def get_instance_status(self, instance_id: int) -> Optional[dict]:
        """Get status information for a specific instance."""
        if instance_id not in self.instances:
            return None
        
        instance = self.instances[instance_id]
        fingerprint = instance.fingerprint
        
        return {
            "instance_id": instance_id,
            "is_active": instance.is_active,
            "startup_time": instance.startup_time.isoformat() if instance.startup_time else None,
            "last_activity": instance.last_activity.isoformat() if instance.last_activity else None,
            "active_sessions": len(instance.provider_sessions),
            "provider_sessions": [service.value for service in instance.provider_sessions.keys()],
            "fingerprint": {
                "user_agent": fingerprint.user_agent,
                "viewport": f"{fingerprint.viewport_width}x{fingerprint.viewport_height}",
                "timezone": fingerprint.timezone,
                "language": fingerprint.language,
                "platform": fingerprint.platform
            }
        }
    
    def get_all_instances_status(self) -> dict:
        """Get status for all instances."""
        return {
            str(instance_id): self.get_instance_status(instance_id)
            for instance_id in range(1, 4)
            if instance_id in self.instances
        }
