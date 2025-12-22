"""
Webchat-to-API Proxy Router

Provides OpenAI-compatible API endpoints that route requests to webchat interfaces
using dynamic provider management and Stagehand automation.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from backend.data.dynamic_provider_models import (
    DynamicProvider,
    ProviderStatus,
    ProviderMetrics
)
from backend.util.dynamic_provider_manager import DynamicProviderManager
from backend.util.intelligent_load_balancer import IntelligentLoadBalancer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["webchat-proxy"])

# Global provider manager instance
provider_manager: Optional[DynamicProviderManager] = None
load_balancer: Optional[IntelligentLoadBalancer] = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request"""
    model: str = Field(..., description="Model name to route to appropriate provider")
    messages: List[Dict[str, str]] = Field(..., description="Chat messages")
    max_tokens: Optional[int] = Field(default=150, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(default=0.7, description="Sampling temperature")
    stream: Optional[bool] = Field(default=False, description="Stream response")
    user: Optional[str] = Field(default=None, description="User identifier")


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response"""
    id: str = Field(..., description="Unique response ID")
    object: str = Field(default="chat.completion", description="Response object type")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: List[Dict[str, Any]] = Field(..., description="Response choices")
    usage: Dict[str, int] = Field(..., description="Token usage statistics")
    provider_info: Optional[Dict[str, Any]] = Field(default=None, description="Provider metadata")


class ModelInfo(BaseModel):
    """Model information"""
    id: str = Field(..., description="Model ID")
    object: str = Field(default="model", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    owned_by: str = Field(..., description="Provider name")
    provider_url: Optional[str] = Field(default=None, description="Provider base URL")


class ModelsResponse(BaseModel):
    """Models list response"""
    object: str = Field(default="list", description="Response object type")
    data: List[ModelInfo] = Field(..., description="Available models")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Check timestamp")
    providers: Dict[str, str] = Field(..., description="Provider statuses")
    version: str = Field(default="1.0.0", description="API version")


class StatsResponse(BaseModel):
    """Statistics response"""
    total_requests: int = Field(..., description="Total requests processed")
    active_providers: int = Field(..., description="Number of active providers")
    average_response_time: float = Field(..., description="Average response time in seconds")
    uptime: float = Field(..., description="Service uptime in seconds")
    provider_metrics: Dict[str, Dict[str, Any]] = Field(..., description="Per-provider metrics")


def get_provider_manager() -> DynamicProviderManager:
    """Get the global provider manager instance"""
    global provider_manager
    if not provider_manager:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Provider manager not initialized"
        )
    return provider_manager


def get_load_balancer() -> IntelligentLoadBalancer:
    """Get the global load balancer instance"""
    global load_balancer
    if not load_balancer:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Load balancer not initialized"
        )
    return load_balancer


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    manager: DynamicProviderManager = Depends(get_provider_manager),
    balancer: IntelligentLoadBalancer = Depends(get_load_balancer)
):
    """
    Create a chat completion using webchat providers.
    
    Routes the request to an appropriate webchat provider based on the model name,
    performs authentication if needed, sends the message, and returns the response
    in OpenAI-compatible format.
    """
    start_time = time.time()
    request_id = f"chatcmpl-{int(time.time() * 1000)}"
    
    try:
        logger.info(f"Processing chat completion request: {request_id}")
        logger.info(f"Model: {request.model}, Messages: {len(request.messages)}")
        
        # Find appropriate provider using load balancer
        provider = await balancer.select_provider(request.model)
        if not provider:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"No provider available for model: {request.model}"
            )
        
        logger.info(f"Selected provider: {provider.name} for model: {request.model}")
        
        # Check provider status
        if provider.status != ProviderStatus.ACTIVE:
            logger.warning(f"Provider {provider.name} is not active (status: {provider.status})")
            
            # Try to reactivate provider
            if provider.status == ProviderStatus.AUTH_FAILED:
                logger.info(f"Attempting to re-authenticate provider: {provider.name}")
                auth_success, error_msg = await manager.authenticator.authenticate_provider(
                    provider, manager.browser_manager.get_browser_instance()
                )
                if not auth_success:
                    raise HTTPException(
                        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Provider authentication failed: {error_msg}"
                    )
                provider.status = ProviderStatus.ACTIVE
        
        # Extract user message
        user_message = ""
        for message in request.messages:
            if message.get("role") == "user":
                user_message = message.get("content", "")
                break
        
        if not user_message:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="No user message found in request"
            )
        
        # Send message to webchat provider
        logger.info(f"Sending message to {provider.name}: {user_message[:100]}...")
        
        response_text = await _send_message_to_provider(provider, user_message, manager)
        
        # Record metrics
        response_time = time.time() - start_time
        background_tasks.add_task(_record_metrics, provider, response_time, True)
        
        # Format OpenAI-compatible response
        response = ChatCompletionResponse(
            id=request_id,
            created=int(time.time()),
            model=request.model,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ],
            usage={
                "prompt_tokens": len(user_message.split()),
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(user_message.split()) + len(response_text.split())
            },
            provider_info={
                "provider_name": provider.name,
                "provider_url": provider.base_url,
                "response_time": response_time,
                "model_mapping": request.model
            }
        )
        
        logger.info(f"Chat completion successful: {request_id} ({response_time:.2f}s)")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Record failed metrics
        response_time = time.time() - start_time
        if 'provider' in locals():
            background_tasks.add_task(_record_metrics, provider, response_time, False)
        
        logger.error(f"Chat completion failed: {request_id} - {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/models", response_model=ModelsResponse)
async def list_models(
    manager: DynamicProviderManager = Depends(get_provider_manager)
):
    """List all available models from active providers"""
    try:
        models = []
        
        for provider_id, provider in manager.providers.items():
            if provider.status == ProviderStatus.ACTIVE:
                for model_name in provider.model_mappings:
                    models.append(ModelInfo(
                        id=model_name,
                        created=int(time.time()),
                        owned_by=provider.name,
                        provider_url=provider.base_url
                    ))
        
        logger.info(f"Listed {len(models)} available models")
        return ModelsResponse(data=models)
        
    except Exception as e:
        logger.error(f"Failed to list models: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}"
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(
    manager: DynamicProviderManager = Depends(get_provider_manager)
):
    """Health check endpoint"""
    try:
        provider_statuses = {}
        for provider_id, provider in manager.providers.items():
            provider_statuses[provider.name] = provider.status.value
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            providers=provider_statuses
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now().isoformat(),
            providers={}
        )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    manager: DynamicProviderManager = Depends(get_provider_manager),
    balancer: IntelligentLoadBalancer = Depends(get_load_balancer)
):
    """Get service statistics"""
    try:
        # Get system metrics
        active_providers = len([p for p in manager.providers.values() if p.status == ProviderStatus.ACTIVE])
        
        # Get load balancer stats
        balancer_stats = balancer.get_statistics()
        
        # Get provider metrics
        provider_metrics = {}
        for provider_id, provider in manager.providers.items():
            if hasattr(provider, 'metrics'):
                provider_metrics[provider.name] = {
                    "total_requests": provider.metrics.total_requests,
                    "successful_requests": provider.metrics.successful_requests,
                    "failed_requests": provider.metrics.failed_requests,
                    "average_response_time": provider.metrics.average_response_time,
                    "last_used": provider.metrics.last_used.isoformat() if provider.metrics.last_used else None
                }
        
        return StatsResponse(
            total_requests=balancer_stats.get("total_requests", 0),
            active_providers=active_providers,
            average_response_time=balancer_stats.get("average_response_time", 0.0),
            uptime=balancer_stats.get("uptime", 0.0),
            provider_metrics=provider_metrics
        )
        
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


async def _send_message_to_provider(
    provider: DynamicProvider,
    message: str,
    manager: DynamicProviderManager
) -> str:
    """Send message to webchat provider and get response"""
    try:
        # Get browser instance
        browser_instance = manager.browser_manager.get_browser_instance()
        
        # Navigate to chat interface
        await browser_instance.navigate(provider.base_url)
        await asyncio.sleep(2)  # Wait for page load
        
        # Find and fill input field
        input_selector = provider.chat_config.get("input_selector", "textarea, input[type='text']")
        await browser_instance.type(input_selector, message)
        
        # Click send button
        send_selector = provider.chat_config.get("send_selector", "button[type='submit']")
        await browser_instance.click(send_selector)
        
        # Wait for response
        wait_time = provider.chat_config.get("wait_for_response", 10)
        await asyncio.sleep(wait_time)
        
        # Extract response
        response_selector = provider.chat_config.get("response_selector", ".message:last-child")
        response_element = await browser_instance.query_selector(response_selector)
        
        if response_element:
            response_text = await response_element.text_content()
            return response_text.strip()
        else:
            logger.warning(f"No response found for provider {provider.name}")
            return "I apologize, but I couldn't generate a response at this time."
            
    except Exception as e:
        logger.error(f"Failed to send message to provider {provider.name}: {str(e)}")
        return f"Error communicating with {provider.name}: {str(e)}"


async def _record_metrics(provider: DynamicProvider, response_time: float, success: bool):
    """Record metrics for provider"""
    try:
        if not hasattr(provider, 'metrics'):
            provider.metrics = ProviderMetrics(
                provider_id=provider.id,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                average_response_time=0.0,
                last_used=datetime.now()
            )
        
        # Update metrics
        provider.metrics.total_requests += 1
        if success:
            provider.metrics.successful_requests += 1
        else:
            provider.metrics.failed_requests += 1
        
        # Update average response time
        total_successful = provider.metrics.successful_requests
        if total_successful > 0:
            current_avg = provider.metrics.average_response_time
            provider.metrics.average_response_time = (
                (current_avg * (total_successful - 1) + response_time) / total_successful
            )
        
        provider.metrics.last_used = datetime.now()
        
        logger.debug(f"Updated metrics for {provider.name}: {provider.metrics.total_requests} total requests")
        
    except Exception as e:
        logger.error(f"Failed to record metrics for {provider.name}: {str(e)}")


def set_provider_manager(manager: DynamicProviderManager):
    """Set the global provider manager instance"""
    global provider_manager
    provider_manager = manager
    logger.info("Provider manager set for webchat proxy")


def set_load_balancer(balancer: IntelligentLoadBalancer):
    """Set the global load balancer instance"""
    global load_balancer
    load_balancer = balancer
    logger.info("Load balancer set for webchat proxy")


# Startup event handler
async def initialize_webchat_proxy():
    """Initialize the webchat proxy system"""
    try:
        logger.info("Initializing webchat proxy system...")
        
        # Initialize provider manager
        global provider_manager, load_balancer
        
        if not provider_manager:
            provider_manager = DynamicProviderManager()
            await provider_manager.start()
        
        if not load_balancer:
            load_balancer = IntelligentLoadBalancer()
        
        # Add default providers
        await _add_default_providers()
        
        logger.info("Webchat proxy system initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize webchat proxy: {str(e)}")
        raise


async def _add_default_providers():
    """Add default provider configurations"""
    try:
        default_providers = [
            {
                "name": "Mistral AI Chat",
                "description": "Mistral AI webchat interface",
                "base_url": "https://chat.mistral.ai",
                "provider_type": "webchat",
                "auth_config": {
                    "method": "email_password",
                    "email": "developer@pixelium.uk",
                    "password": "develooper123?",
                    "login_url": "https://chat.mistral.ai/login",
                    "email_selector": 'input[type="email"]',
                    "password_selector": 'input[type="password"]',
                    "submit_selector": 'button[type="submit"]',
                    "success_indicators": ['.chat-interface', '.conversation-area'],
                    "failure_indicators": ['.error-message', '.login-error']
                },
                "chat_config": {
                    "input_selector": '[data-testid="chat-input"], .chat-input, textarea',
                    "send_selector": '[data-testid="send-button"], .send-button',
                    "response_selector": '.message-content, .response-text',
                    "wait_for_response": 10
                },
                "model_mappings": ["mistral", "mistral-chat", "mistral-ai"],
                "priority": 1,
                "enabled": True
            }
        ]
        
        for provider_config in default_providers:
            try:
                await provider_manager.add_provider(provider_config)
                logger.info(f"Added default provider: {provider_config['name']}")
            except Exception as e:
                logger.warning(f"Failed to add default provider {provider_config['name']}: {str(e)}")
        
    except Exception as e:
        logger.error(f"Failed to add default providers: {str(e)}")


# Shutdown event handler
async def shutdown_webchat_proxy():
    """Shutdown the webchat proxy system"""
    try:
        logger.info("Shutting down webchat proxy system...")
        
        global provider_manager, load_balancer
        
        if provider_manager:
            await provider_manager.stop()
            provider_manager = None
        
        if load_balancer:
            load_balancer = None
        
        logger.info("Webchat proxy system shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during webchat proxy shutdown: {str(e)}")
