"""
Chat Proxy blocks for dynamic web chat automation.
Uses AI-powered Stagehand for element detection instead of hardcoded selectors.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.blocks.chat_proxy._config import chat_proxy as chat_proxy_provider
from backend.blocks.stagehand._config import stagehand as stagehand_provider
from backend.data.chat_proxy_models import (
    ChatServiceType,
    ChatAccount,
    AccountStatus,
    DEFAULT_SERVICE_CONFIGS,
)
from backend.util.load_balancer import load_balancer
from backend.util.flareprox_integration import get_proxied_url
from backend.sdk import (
    APIKeyCredentials,
    Block,
    BlockCategory,
    BlockOutput,
    BlockSchema,
    CredentialsMetaInput,
    SchemaField,
)

# Import Stagehand for browser automation
from stagehand import Stagehand

logger = logging.getLogger(__name__)


class ChatProxyLoginBlock(Block):
    """
    Block for logging into chat services using AI-powered element detection.
    Maintains persistent sessions via Browserbase.
    """
    
    class Input(BlockSchema):
        # Credentials
        stagehand_credentials: CredentialsMetaInput = (
            stagehand_provider.credentials_field(
                description="Stagehand/Browserbase API key for browser automation"
            )
        )
        
        browserbase_project_id: str = SchemaField(
            description="Browserbase project ID for session persistence",
            default=""
        )
        
        # Service configuration
        service_type: ChatServiceType = SchemaField(
            description="Chat service to login to",
            default=ChatServiceType.ZAI
        )
        
        email: str = SchemaField(
            description="Account email/username",
            default=""
        )
        
        password: str = SchemaField(
            description="Account password",
            default=""
        )
        
        # AI model for element detection
        model: str = SchemaField(
            description="LLM model for AI-powered element detection",
            default="claude-3-5-sonnet-20241022"
        )
        
        # Timeout settings
        timeout: int = SchemaField(
            description="Login timeout in seconds",
            default=60
        )
        
        # FlareProx integration
        use_flareprox: bool = SchemaField(
            description="Use FlareProx for IP rotation",
            default=True
        )
        
    class Output(BlockSchema):
        success: bool = SchemaField(description="Whether login was successful")
        session_id: str = SchemaField(description="Browser session ID for reuse")
        error_message: str = SchemaField(description="Error message if login failed", default="")
        login_time: float = SchemaField(description="Time taken to login in seconds")
        
    def __init__(self):
        super().__init__(
            id=str(uuid.uuid4()),
            description="Login to chat services with AI-powered element detection",
            categories={BlockCategory.AI},
            input_schema=ChatProxyLoginBlock.Input,
            output_schema=ChatProxyLoginBlock.Output,
        )
        
    async def run(
        self, input_data: Input, **kwargs
    ) -> BlockOutput:
        start_time = time.time()
        
        try:
            # Get service configuration
            service_config = DEFAULT_SERVICE_CONFIGS.get(input_data.service_type)
            if not service_config:
                raise ValueError(f"Unsupported service type: {input_data.service_type}")
                
            logger.info(f"Starting login for {input_data.service_type} with email {input_data.email}")
            
            # Initialize Stagehand with Browserbase
            stagehand = Stagehand(
                api_key=input_data.stagehand_credentials.api_key.get_secret_value(),
                project_id=input_data.browserbase_project_id,
                model_name=input_data.model,
            )
            
            await stagehand.init()
            page = stagehand.page
            
            if not page:
                raise RuntimeError("Failed to initialize Stagehand browser page")
                
            # Navigate to login page (with optional FlareProx)
            login_url = service_config.login_url
            if input_data.use_flareprox:
                try:
                    login_url = await get_proxied_url(service_config.login_url, use_random=True)
                    logger.info(f"Using FlareProx for login: {login_url}")
                except Exception as e:
                    logger.warning(f"FlareProx failed, using direct URL: {e}")
                    login_url = service_config.login_url
            
            logger.info(f"Navigating to login page: {login_url}")
            await page.goto(login_url)
            
            # Wait for page to load
            await page.wait_for_load_state("networkidle")
            
            # Use AI to find and fill email field
            email_instruction = service_config.login_instructions.get(
                "email_field", 
                "Find the email or username input field"
            )
            
            logger.info("Using AI to find email field...")
            await page.act(f"{email_instruction} and type '{input_data.email}'")
            
            # Use AI to find and fill password field
            password_instruction = service_config.login_instructions.get(
                "password_field",
                "Find the password input field"
            )
            
            logger.info("Using AI to find password field...")
            await page.act(f"{password_instruction} and type '{input_data.password}'")
            
            # Use AI to find and click login button
            login_button_instruction = service_config.login_instructions.get(
                "login_button",
                "Find and click the login or sign in button"
            )
            
            logger.info("Using AI to find and click login button...")
            await page.act(login_button_instruction)
            
            # Wait for login to complete and check for success
            success_instruction = service_config.login_instructions.get(
                "success_indicator",
                "Look for indicators that login was successful, such as a chat interface or user profile"
            )
            
            logger.info("Checking for successful login...")
            
            # Wait a bit for the page to respond
            await asyncio.sleep(3)
            
            # Use AI to observe if login was successful
            observe_results = await page.observe(
                f"{success_instruction}. Return true if login appears successful, false otherwise.",
                domSettleTimeoutMs=5000
            )
            
            # Determine if login was successful based on AI observation
            success = False
            for result in observe_results:
                if "success" in result.description.lower() or "chat" in result.description.lower():
                    success = True
                    break
                    
            # Also check URL change as indicator
            current_url = page.url
            if current_url != service_config.login_url and "login" not in current_url.lower():
                success = True
                
            login_time = time.time() - start_time
            
            if success:
                logger.info(f"Login successful for {input_data.service_type} in {login_time:.2f}s")
                
                # Get session ID from Browserbase
                session_id = input_data.browserbase_project_id  # Use project ID as session identifier
                
                yield "success", True
                yield "session_id", session_id
                yield "error_message", ""
                yield "login_time", login_time
                
            else:
                error_msg = f"Login failed for {input_data.service_type} - AI could not detect successful login"
                logger.error(error_msg)
                
                yield "success", False
                yield "session_id", ""
                yield "error_message", error_msg
                yield "login_time", login_time
                
        except Exception as e:
            login_time = time.time() - start_time
            error_msg = f"Login error for {input_data.service_type}: {str(e)}"
            logger.error(error_msg)
            
            yield "success", False
            yield "session_id", ""
            yield "error_message", error_msg
            yield "login_time", login_time


class ChatProxySendMessageBlock(Block):
    """
    Block for sending messages to chat services and getting responses.
    Uses AI-powered element detection for dynamic web interaction.
    """
    
    class Input(BlockSchema):
        # Credentials
        stagehand_credentials: CredentialsMetaInput = (
            stagehand_provider.credentials_field(
                description="Stagehand/Browserbase API key for browser automation"
            )
        )
        
        browserbase_project_id: str = SchemaField(
            description="Browserbase project ID for session persistence",
            default=""
        )
        
        # Service configuration
        service_type: ChatServiceType = SchemaField(
            description="Chat service to send message to",
            default=ChatServiceType.ZAI
        )
        
        message: str = SchemaField(
            description="Message to send to the chat service",
            default=""
        )
        
        # AI model for element detection
        model: str = SchemaField(
            description="LLM model for AI-powered element detection",
            default="claude-3-5-sonnet-20241022"
        )
        
        # Timeout settings
        response_timeout: int = SchemaField(
            description="Timeout for waiting for AI response in seconds",
            default=120
        )
        
        # FlareProx integration
        use_flareprox: bool = SchemaField(
            description="Use FlareProx for IP rotation",
            default=True
        )
        
    class Output(BlockSchema):
        success: bool = SchemaField(description="Whether message was sent and response received")
        response: str = SchemaField(description="AI response from the chat service", default="")
        error_message: str = SchemaField(description="Error message if operation failed", default="")
        response_time: float = SchemaField(description="Time taken to get response in seconds")
        
    def __init__(self):
        super().__init__(
            id=str(uuid.uuid4()),
            description="Send messages to chat services and get AI responses",
            categories={BlockCategory.AI},
            input_schema=ChatProxySendMessageBlock.Input,
            output_schema=ChatProxySendMessageBlock.Output,
        )
        
    async def run(
        self, input_data: Input, **kwargs
    ) -> BlockOutput:
        start_time = time.time()
        
        try:
            # Get service configuration
            service_config = DEFAULT_SERVICE_CONFIGS.get(input_data.service_type)
            if not service_config:
                raise ValueError(f"Unsupported service type: {input_data.service_type}")
                
            logger.info(f"Sending message to {input_data.service_type}: {input_data.message[:100]}...")
            
            # Initialize Stagehand with existing session
            stagehand = Stagehand(
                api_key=input_data.stagehand_credentials.api_key.get_secret_value(),
                project_id=input_data.browserbase_project_id,
                model_name=input_data.model,
            )
            
            await stagehand.init()
            page = stagehand.page
            
            if not page:
                raise RuntimeError("Failed to initialize Stagehand browser page")
                
            # Navigate to chat page if not already there (with optional FlareProx)
            current_url = page.url
            if service_config.chat_url not in current_url:
                chat_url = service_config.chat_url
                if input_data.use_flareprox:
                    try:
                        chat_url = await get_proxied_url(service_config.chat_url, use_random=True)
                        logger.info(f"Using FlareProx for chat: {chat_url}")
                    except Exception as e:
                        logger.warning(f"FlareProx failed, using direct URL: {e}")
                        chat_url = service_config.chat_url
                
                logger.info(f"Navigating to chat page: {chat_url}")
                await page.goto(chat_url)
                await page.wait_for_load_state("networkidle")
                
            # Use AI to find message input field and type message
            message_input_instruction = service_config.chat_instructions.get(
                "message_input",
                "Find the main text input area where users type their messages"
            )
            
            logger.info("Using AI to find message input and type message...")
            await page.act(f"{message_input_instruction} and clear it, then type: {input_data.message}")
            
            # Use AI to find and click send button
            send_button_instruction = service_config.chat_instructions.get(
                "send_button",
                "Find and click the send button to submit the message"
            )
            
            logger.info("Using AI to find and click send button...")
            await page.act(send_button_instruction)
            
            # Wait for AI to start responding
            await asyncio.sleep(2)
            
            # Use AI to monitor for response completion
            response_area_instruction = service_config.chat_instructions.get(
                "response_area",
                "Find the area where AI responses appear, usually the latest message"
            )
            
            loading_instruction = service_config.chat_instructions.get(
                "loading_indicator",
                "Look for loading indicators while AI is generating response"
            )
            
            logger.info("Waiting for AI response...")
            
            # Poll for response completion
            max_wait_time = input_data.response_timeout
            poll_interval = 3
            waited_time = 0
            response_text = ""
            
            while waited_time < max_wait_time:
                await asyncio.sleep(poll_interval)
                waited_time += poll_interval
                
                # Check if AI is still generating (loading indicators present)
                loading_results = await page.observe(
                    f"{loading_instruction}. Return true if AI is still generating response, false if complete.",
                    domSettleTimeoutMs=2000
                )
                
                still_loading = False
                for result in loading_results:
                    if "loading" in result.description.lower() or "generating" in result.description.lower():
                        still_loading = True
                        break
                        
                if not still_loading:
                    # Try to extract the response
                    response_results = await page.observe(
                        f"{response_area_instruction}. Extract the latest AI response text.",
                        domSettleTimeoutMs=3000
                    )
                    
                    for result in response_results:
                        if result.description and len(result.description) > 10:
                            response_text = result.description
                            break
                            
                    if response_text:
                        break
                        
                logger.info(f"Still waiting for response... ({waited_time}s)")
                
            response_time = time.time() - start_time
            
            if response_text:
                logger.info(f"Got response from {input_data.service_type} in {response_time:.2f}s")
                
                yield "success", True
                yield "response", response_text
                yield "error_message", ""
                yield "response_time", response_time
                
            else:
                error_msg = f"Timeout waiting for response from {input_data.service_type} after {waited_time}s"
                logger.error(error_msg)
                
                yield "success", False
                yield "response", ""
                yield "error_message", error_msg
                yield "response_time", response_time
                
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = f"Error sending message to {input_data.service_type}: {str(e)}"
            logger.error(error_msg)
            
            yield "success", False
            yield "response", ""
            yield "error_message", error_msg
            yield "response_time", response_time


class ChatProxyHealthCheckBlock(Block):
    """
    Block for checking the health status of chat service accounts.
    """
    
    class Input(BlockSchema):
        # Credentials
        stagehand_credentials: CredentialsMetaInput = (
            stagehand_provider.credentials_field(
                description="Stagehand/Browserbase API key for browser automation"
            )
        )
        
        browserbase_project_id: str = SchemaField(
            description="Browserbase project ID for session persistence",
            default=""
        )
        
        # Service configuration
        service_type: ChatServiceType = SchemaField(
            description="Chat service to check health for",
            default=ChatServiceType.ZAI
        )
        
        # AI model for element detection
        model: str = SchemaField(
            description="LLM model for AI-powered element detection",
            default="claude-3-5-sonnet-20241022"
        )
        
        # FlareProx integration
        use_flareprox: bool = SchemaField(
            description="Use FlareProx for IP rotation",
            default=True
        )
        
    class Output(BlockSchema):
        healthy: bool = SchemaField(description="Whether the account/session is healthy")
        status_message: str = SchemaField(description="Health status description", default="")
        error_message: str = SchemaField(description="Error message if health check failed", default="")
        check_time: float = SchemaField(description="Time taken for health check in seconds")
        
    def __init__(self):
        super().__init__(
            id=str(uuid.uuid4()),
            description="Check health status of chat service accounts",
            categories={BlockCategory.AI},
            input_schema=ChatProxyHealthCheckBlock.Input,
            output_schema=ChatProxyHealthCheckBlock.Output,
        )
        
    async def run(
        self, input_data: Input, **kwargs
    ) -> BlockOutput:
        start_time = time.time()
        
        try:
            # Get service configuration
            service_config = DEFAULT_SERVICE_CONFIGS.get(input_data.service_type)
            if not service_config:
                raise ValueError(f"Unsupported service type: {input_data.service_type}")
                
            logger.info(f"Checking health for {input_data.service_type}")
            
            # Initialize Stagehand with existing session
            stagehand = Stagehand(
                api_key=input_data.stagehand_credentials.api_key.get_secret_value(),
                project_id=input_data.browserbase_project_id,
                model_name=input_data.model,
            )
            
            await stagehand.init()
            page = stagehand.page
            
            if not page:
                raise RuntimeError("Failed to initialize Stagehand browser page")
                
            # Navigate to chat page (with optional FlareProx)
            chat_url = service_config.chat_url
            if input_data.use_flareprox:
                try:
                    chat_url = await get_proxied_url(service_config.chat_url, use_random=True)
                    logger.info(f"Using FlareProx for health check: {chat_url}")
                except Exception as e:
                    logger.warning(f"FlareProx failed, using direct URL: {e}")
                    chat_url = service_config.chat_url
            
            logger.info(f"Navigating to chat page: {chat_url}")
            await page.goto(chat_url)
            await page.wait_for_load_state("networkidle")
            
            # Use AI to check if we're logged in and can access chat
            health_check_instruction = (
                "Check if this page shows a working chat interface where the user is logged in. "
                "Look for message input fields, chat history, or user profile indicators. "
                "Return true if the chat service appears to be working and accessible, false otherwise."
            )
            
            observe_results = await page.observe(
                health_check_instruction,
                domSettleTimeoutMs=5000
            )
            
            healthy = False
            status_message = "Unknown status"
            
            for result in observe_results:
                description = result.description.lower()
                if "chat" in description and ("input" in description or "message" in description):
                    healthy = True
                    status_message = "Chat interface is accessible and working"
                    break
                elif "login" in description or "sign in" in description:
                    status_message = "Session expired - login required"
                    break
                elif "error" in description:
                    status_message = f"Error detected: {result.description}"
                    break
                    
            check_time = time.time() - start_time
            
            logger.info(f"Health check for {input_data.service_type}: {'healthy' if healthy else 'unhealthy'} - {status_message}")
            
            yield "healthy", healthy
            yield "status_message", status_message
            yield "error_message", ""
            yield "check_time", check_time
            
        except Exception as e:
            check_time = time.time() - start_time
            error_msg = f"Health check error for {input_data.service_type}: {str(e)}"
            logger.error(error_msg)
            
            yield "healthy", False
            yield "status_message", "Health check failed"
            yield "error_message", error_msg
            yield "check_time", check_time
