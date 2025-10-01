"""
OpenAI-compatible API proxy for chat services.
Provides drop-in replacement for OpenAI API using browser automation.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.data.chat_proxy_models import (
    ChatServiceType,
    ChatAccount,
    ChatProxyRequest,
    ChatProxyResponse,
    DEFAULT_SERVICE_CONFIGS,
)
from backend.util.load_balancer import load_balancer
from backend.blocks.chat_proxy.blocks import (
    ChatProxyLoginBlock,
    ChatProxySendMessageBlock,
    ChatProxyHealthCheckBlock,
)
from backend.data import redis_client as redis
from backend.util.auth import get_user_id

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/v1", tags=["openai-proxy"])

# Import dependency injection
from backend.server.dependencies import ScalingEngineDep


# OpenAI-compatible request/response models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="Model to use (maps to chat service)")
    messages: List[ChatMessage] = Field(..., description="List of messages")
    temperature: Optional[float] = Field(default=1.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens to generate")
    stream: Optional[bool] = Field(default=False, description="Whether to stream responses")
    top_p: Optional[float] = Field(default=1.0, description="Nucleus sampling parameter")
    frequency_penalty: Optional[float] = Field(default=0.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(default=0.0, description="Presence penalty")
    stop: Optional[List[str]] = Field(default=None, description="Stop sequences")


class ChatCompletionChoice(BaseModel):
    index: int = Field(..., description="Choice index")
    message: ChatMessage = Field(..., description="Generated message")
    finish_reason: str = Field(..., description="Reason for finishing")


class ChatCompletionResponse(BaseModel):
    id: str = Field(..., description="Completion ID")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    choices: List[ChatCompletionChoice] = Field(..., description="Generated choices")
    usage: Optional[Dict[str, int]] = Field(default=None, description="Token usage")


class ChatCompletionStreamChoice(BaseModel):
    index: int = Field(..., description="Choice index")
    delta: Dict[str, Any] = Field(..., description="Delta content")
    finish_reason: Optional[str] = Field(default=None, description="Reason for finishing")


class ChatCompletionStreamResponse(BaseModel):
    id: str = Field(..., description="Completion ID")
    object: str = Field(default="chat.completion.chunk", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    choices: List[ChatCompletionStreamChoice] = Field(..., description="Stream choices")


# Legacy model mapping to chat services (for backward compatibility)
LEGACY_MODEL_SERVICE_MAPPING = {
    "gpt-3.5-turbo": ChatServiceType.ZAI,
    "gpt-4": ChatServiceType.ZAI,
    "gpt-4-turbo": ChatServiceType.ZAI,
    "claude-3-sonnet": ChatServiceType.ZAI,
    "claude-3-opus": ChatServiceType.ZAI,
    "qwen-max": ChatServiceType.QWEN,
    "qwen-plus": ChatServiceType.QWEN,
    "qwen-turbo": ChatServiceType.QWEN,
    "deepseek-chat": ChatServiceType.DEEPSEEK,
    "deepseek-coder": ChatServiceType.DEEPSEEK,
    "k2-think": ChatServiceType.K2THINK,
    "grok-beta": ChatServiceType.GROK,
    "grok-2": ChatServiceType.GROK,
}

# Dynamic provider manager (will be set during startup)
dynamic_provider_manager = None

# Default accounts configuration (in production, this would come from database)
DEFAULT_ACCOUNTS = {
    ChatServiceType.ZAI: [
        ChatAccount(
            id="zai_1",
            service_type=ChatServiceType.ZAI,
            email="developer@pixelium.uk",
            password="developer123?",
            browserbase_session_id="zai_session_1"
        )
    ],
    ChatServiceType.QWEN: [
        ChatAccount(
            id="qwen_1",
            service_type=ChatServiceType.QWEN,
            email="developer@pixelium.uk",
            password="developer1?",
            browserbase_session_id="qwen_session_1"
        )
    ],
    ChatServiceType.DEEPSEEK: [
        ChatAccount(
            id="deepseek_1",
            service_type=ChatServiceType.DEEPSEEK,
            email="zeeeepa+1@gmail.com",
            password="developer123??",
            browserbase_session_id="deepseek_session_1"
        )
    ],
    ChatServiceType.K2THINK: [
        ChatAccount(
            id="k2think_1",
            service_type=ChatServiceType.K2THINK,
            email="developer@pixelium.uk",
            password="developer123?",
            browserbase_session_id="k2think_session_1"
        )
    ],
    ChatServiceType.GROK: [
        ChatAccount(
            id="grok_1",
            service_type=ChatServiceType.GROK,
            email="developer@pixelium.uk",
            password="developer123??",
            browserbase_session_id="grok_session_1"
        )
    ],
}


async def get_chat_service_from_model(model: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Map OpenAI model name to provider using dynamic routing with YAML config support.
    
    Returns:
        Tuple of (provider_id, provider_type) where provider_type is 'yaml' or 'legacy'
    """
    # First try YAML configuration providers
    try:
        from backend.util.yaml_config_loader import get_yaml_config_loader
        yaml_loader = await get_yaml_config_loader()
        
        # Check for exact model match in YAML providers
        yaml_provider = yaml_loader.get_provider_by_model(model)
        if yaml_provider:
            provider_id = yaml_loader._generate_provider_id(yaml_provider.name)
            logger.info(f"Routing model '{model}' to YAML provider '{yaml_provider.name}'")
            return provider_id, 'yaml'
        
        # Check for provider name match (e.g., model="z.ai" -> Z.AI provider)
        for provider_id, provider in yaml_loader.providers.items():
            provider_names = [
                provider.name.lower(),
                provider.name.lower().replace(' ', ''),
                provider.name.lower().replace(' ', '-'),
                provider.name.lower().replace(' ', '.'),
            ]
            
            if model.lower() in provider_names:
                logger.info(f"Routing model '{model}' to YAML provider '{provider.name}' by name match")
                return provider_id, 'yaml'
        
        # Check if model should use default YAML provider
        default_provider = yaml_loader.get_default_provider()
        if default_provider and model.lower() in ['gpt-4', 'gpt-3.5-turbo', 'gpt-4-turbo']:
            provider_id = yaml_loader._generate_provider_id(default_provider.name)
            logger.info(f"Routing standard model '{model}' to default YAML provider '{default_provider.name}'")
            return provider_id, 'yaml'
            
    except Exception as e:
        logger.warning(f"Error accessing YAML configuration: {e}")
    
    # Fallback to dynamic provider manager
    if dynamic_provider_manager:
        # Check for exact model mapping
        mapping = dynamic_provider_manager.system_config.get_model_mapping(model)
        if mapping:
            provider = dynamic_provider_manager.providers.get(mapping.provider_id)
            if provider and provider.is_enabled and provider.is_healthy():
                logger.info(f"Routing model '{model}' to dynamic provider '{provider.name}'")
                return mapping.provider_id, 'dynamic'
        
        # Check for provider name match
        for provider_id, provider in dynamic_provider_manager.providers.items():
            if not provider.is_enabled or not provider.is_healthy():
                continue
                
            provider_names = [
                provider.name.lower(),
                provider.name.lower().replace(' ', ''),
                provider.name.lower().replace(' ', '-'),
                provider.name.lower().replace(' ', '.'),
            ]
            
            if model.lower() in provider_names:
                logger.info(f"Routing model '{model}' to dynamic provider '{provider.name}' by name match")
                return provider_id, 'dynamic'
        
        # Check for partial matches in supported models
        for provider_id, provider in dynamic_provider_manager.providers.items():
            if not provider.is_enabled or not provider.is_healthy():
                continue
                
            for supported_model in provider.supported_models:
                if (model.lower() in supported_model.lower() or 
                    supported_model.lower() in model.lower()):
                    logger.info(f"Routing model '{model}' to dynamic provider '{provider.name}' by partial match")
                    return provider_id, 'dynamic'
        
        # Use default provider if configured
        if dynamic_provider_manager.system_config.default_provider_id:
            default_provider = dynamic_provider_manager.providers.get(
                dynamic_provider_manager.system_config.default_provider_id
            )
            if default_provider and default_provider.is_enabled and default_provider.is_healthy():
                logger.info(f"Routing model '{model}' to default dynamic provider '{default_provider.name}'")
                return dynamic_provider_manager.system_config.default_provider_id, 'dynamic'
    
    # Fallback to legacy mapping for backward compatibility
    logger.info(f"No provider found for model '{model}', using legacy routing")
    return None, 'legacy'


async def get_legacy_chat_service_from_model(model: str) -> ChatServiceType:
    """Legacy model mapping for backward compatibility"""
    service_type = LEGACY_MODEL_SERVICE_MAPPING.get(model)
    if not service_type:
        # Default to Z.AI for unknown models
        service_type = ChatServiceType.ZAI
    return service_type


async def get_account_for_service(service_type: ChatServiceType) -> Optional[ChatAccount]:
    """Get an available account for the service using load balancer"""
    accounts = DEFAULT_ACCOUNTS.get(service_type, [])
    if not accounts:
        return None
        
    # Use load balancer to select account
    selected_account = await load_balancer.get_next_account(
        service_type=service_type,
        accounts=accounts
    )
    
    return selected_account


async def ensure_account_logged_in(account: ChatAccount, stagehand_api_key: str) -> bool:
    """Ensure account is logged in, login if necessary"""
    try:
        # First check if already logged in
        health_block = ChatProxyHealthCheckBlock()
        health_input = health_block.Input(
            stagehand_credentials={"api_key": stagehand_api_key},
            browserbase_project_id=account.browserbase_session_id,
            service_type=account.service_type
        )
        
        health_results = {}
        async for key, value in health_block.run(health_input):
            health_results[key] = value
            
        if health_results.get("healthy", False):
            logger.info(f"Account {account.id} is already logged in")
            return True
            
        # Need to login
        logger.info(f"Logging in account {account.id} for {account.service_type}")
        login_block = ChatProxyLoginBlock()
        login_input = login_block.Input(
            stagehand_credentials={"api_key": stagehand_api_key},
            browserbase_project_id=account.browserbase_session_id,
            service_type=account.service_type,
            email=account.email,
            password=account.password.get_secret_value()
        )
        
        login_results = {}
        async for key, value in login_block.run(login_input):
            login_results[key] = value
            
        success = login_results.get("success", False)
        if success:
            logger.info(f"Successfully logged in account {account.id}")
        else:
            logger.error(f"Failed to login account {account.id}: {login_results.get('error_message', 'Unknown error')}")
            
        return success
        
    except Exception as e:
        logger.error(f"Error ensuring account {account.id} is logged in: {e}")
        return False


async def send_message_to_service(
    account: ChatAccount,
    message: str,
    stagehand_api_key: str
) -> ChatProxyResponse:
    """Send message to chat service and get response"""
    start_time = time.time()
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    
    try:
        # Ensure account is logged in
        if not await ensure_account_logged_in(account, stagehand_api_key):
            raise HTTPException(
                status_code=503,
                detail=f"Failed to login to {account.service_type}"
            )
            
        # Send message
        send_block = ChatProxySendMessageBlock()
        send_input = send_block.Input(
            stagehand_credentials={"api_key": stagehand_api_key},
            browserbase_project_id=account.browserbase_session_id,
            service_type=account.service_type,
            message=message
        )
        
        send_results = {}
        async for key, value in send_block.run(send_input):
            send_results[key] = value
            
        response_time = time.time() - start_time
        success = send_results.get("success", False)
        
        # Update load balancer health
        await load_balancer.update_account_health(
            account_id=account.id,
            success=success,
            response_time=response_time,
            error_message=send_results.get("error_message") if not success else None
        )
        
        if success:
            return ChatProxyResponse(
                request_id=request_id,
                service_type=account.service_type,
                account_id=account.id,
                content=send_results.get("response", ""),
                response_time=response_time,
                success=True
            )
        else:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to get response from {account.service_type}: {send_results.get('error_message', 'Unknown error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        response_time = time.time() - start_time
        
        # Update load balancer health
        await load_balancer.update_account_health(
            account_id=account.id,
            success=False,
            response_time=response_time,
            error_message=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    http_request: Request,
    scaling_engine = ScalingEngineDep
) -> ChatCompletionResponse:
    """
    OpenAI-compatible chat completions endpoint.
    Routes requests to appropriate chat services via browser automation.
    """
    try:
        # Get Stagehand API key from environment or request headers
        stagehand_api_key = http_request.headers.get("X-Stagehand-API-Key")
        if not stagehand_api_key:
            # Try to get from environment
            stagehand_api_key = os.getenv("STAGEHAND_API_KEY")
            
        if not stagehand_api_key:
            raise HTTPException(
                status_code=401,
                detail="Stagehand API key is required. Provide it via 'X-Stagehand-API-Key' header or STAGEHAND_API_KEY environment variable."
            )
            
        # Map model to provider using new routing system
        provider_id, provider_type = await get_chat_service_from_model(request.model)
        
        logger.info(f"Processing chat completion for model '{request.model}' -> provider '{provider_id}' (type: {provider_type})")
        
        # Handle YAML provider routing
        if provider_type == 'yaml' and provider_id:
            try:
                from backend.util.yaml_config_loader import get_yaml_config_loader
                yaml_loader = await get_yaml_config_loader()
                provider_config = yaml_loader.providers.get(provider_id)
                
                if provider_config:
                    # Use AI Provider Engine for YAML providers
                    from backend.server.routers.simple_provider_api import get_ai_provider_engine
                    engine = await get_ai_provider_engine()
                    
                    # Extract user message
                    user_message = ""
                    for msg in reversed(request.messages):
                        if msg.role == "user":
                            user_message = msg.content
                            break
                    
                    if not user_message:
                        raise HTTPException(status_code=400, detail="No user message found")
                    
                    # Send message through AI provider engine
                    response = await engine.send_message(provider_id, user_message)
                    
                    if response.success:
                        # Format as OpenAI response
                        completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
                        created_timestamp = int(time.time())
                        
                        return ChatCompletionResponse(
                            id=completion_id,
                            created=created_timestamp,
                            model=request.model,
                            choices=[
                                ChatCompletionChoice(
                                    index=0,
                                    message=ChatMessage(role="assistant", content=response.content),
                                    finish_reason="stop"
                                )
                            ]
                        )
                    else:
                        raise HTTPException(status_code=500, detail=f"Provider error: {response.error_message}")
                        
            except Exception as e:
                logger.error(f"YAML provider error: {e}")
                # Fall through to legacy handling
        
        # Handle dynamic provider routing
        elif provider_type == 'dynamic' and provider_id and scaling_engine:
            try:
                # Convert request to dict format for scaling engine
                request_data = {
                    "model": request.model,
                    "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stream": request.stream
                }
                
                # Handle request through scaling engine
                response = await scaling_engine.handle_request(provider_id, request_data)
                return response
                
            except Exception as e:
                logger.error(f"Dynamic provider error: {e}")
                # Fall through to legacy handling
        
        # Legacy routing fallback
        service_type = await get_legacy_chat_service_from_model(request.model)
        logger.info(f"Using legacy routing: {service_type}")
        
        # Use smart scaling engine for legacy services
        if scaling_engine:
            try:
                request_data = {
                    "model": request.model,
                    "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stream": request.stream
                }
                
                response = await scaling_engine.handle_request(service_type, request_data)
                return response
                
            except Exception as e:
                logger.error(f"Legacy scaling engine error: {e}")
                # Continue to traditional fallback
        
        # Fallback to traditional load balancer method
        # Get account for service
        account = await get_account_for_service(service_type)
        if not account:
            raise HTTPException(
                status_code=503,
                detail=f"No available accounts for service {service_type}"
            )
            
        # Extract user message (last message in conversation)
        user_message = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                user_message = msg.content
                break
                
        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="No user message found in request"
            )
        
        # Handle streaming vs non-streaming
        if request.stream:
            return StreamingResponse(
                stream_chat_completion(account, user_message, request, stagehand_api_key),
                media_type="text/plain"
            )
        else:
            # Send message and get response
            proxy_response = await send_message_to_service(
                account=account,
                message=user_message,
                stagehand_api_key=stagehand_api_key
            )
            
            # Format as OpenAI response
            completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
            created_timestamp = int(time.time())
            
            return ChatCompletionResponse(
                id=completion_id,
                created=created_timestamp,
                model=request.model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(
                            role="assistant",
                            content=proxy_response.content
                        ),
                        finish_reason="stop"
                    )
                ],
                usage={
                    "prompt_tokens": len(user_message.split()),
                    "completion_tokens": len(proxy_response.content.split()),
                    "total_tokens": len(user_message.split()) + len(proxy_response.content.split())
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat completions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


async def stream_chat_completion(
    account: ChatAccount,
    message: str,
    request: ChatCompletionRequest,
    stagehand_api_key: str
) -> AsyncGenerator[str, None]:
    """Stream chat completion response"""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    created_timestamp = int(time.time())
    
    try:
        # For now, we'll simulate streaming by getting the full response
        # and then streaming it word by word
        # In a real implementation, you'd want to implement true streaming
        proxy_response = await send_message_to_service(
            account=account,
            message=message,
            stagehand_api_key=stagehand_api_key
        )
        
        # Stream the response word by word
        words = proxy_response.content.split()
        
        for i, word in enumerate(words):
            chunk = ChatCompletionStreamResponse(
                id=completion_id,
                created=created_timestamp,
                model=request.model,
                choices=[
                    ChatCompletionStreamChoice(
                        index=0,
                        delta={"content": word + " " if i < len(words) - 1 else word},
                        finish_reason=None
                    )
                ]
            )
            
            yield f"data: {chunk.model_dump_json()}\n\n"
            await asyncio.sleep(0.1)  # Small delay for streaming effect
            
        # Send final chunk
        final_chunk = ChatCompletionStreamResponse(
            id=completion_id,
            created=created_timestamp,
            model=request.model,
            choices=[
                ChatCompletionStreamChoice(
                    index=0,
                    delta={},
                    finish_reason="stop"
                )
            ]
        )
        
        yield f"data: {final_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        error_chunk = {
            "error": {
                "message": str(e),
                "type": "internal_error",
                "code": "internal_error"
            }
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"


@router.get("/models")
async def list_models():
    """List available models (OpenAI-compatible) including YAML providers"""
    models = []
    
    # Add models from YAML configuration
    try:
        from backend.util.yaml_config_loader import get_yaml_config_loader
        yaml_loader = await get_yaml_config_loader()
        
        for provider_id, provider in yaml_loader.providers.items():
            for model_name in provider.models:
                models.append({
                    "id": model_name,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": f"yaml-provider-{provider.name.lower().replace(' ', '-')}",
                    "permission": [],
                    "root": model_name,
                    "parent": None
                })
                
        logger.info(f"Added {len([m for p in yaml_loader.providers.values() for m in p.models])} models from YAML providers")
        
    except Exception as e:
        logger.warning(f"Could not load YAML models: {e}")
    
    # Add models from dynamic providers
    if dynamic_provider_manager:
        try:
            for provider_id, provider in dynamic_provider_manager.providers.items():
                if provider.is_enabled and provider.is_healthy():
                    for model_name in provider.supported_models:
                        models.append({
                            "id": model_name,
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": f"dynamic-provider-{provider.name.lower().replace(' ', '-')}",
                            "permission": [],
                            "root": model_name,
                            "parent": None
                        })
        except Exception as e:
            logger.warning(f"Could not load dynamic provider models: {e}")
    
    # Add legacy models for backward compatibility
    for model_name, service_type in LEGACY_MODEL_SERVICE_MAPPING.items():
        models.append({
            "id": model_name,
            "object": "model",
            "created": int(time.time()),
            "owned_by": f"legacy-{service_type.value}",
            "permission": [],
            "root": model_name,
            "parent": None
        })
        
    # Remove duplicates based on model ID
    unique_models = {}
    for model in models:
        if model["id"] not in unique_models:
            unique_models[model["id"]] = model
    
    return {
        "object": "list",
        "data": list(unique_models.values())
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": list(ChatServiceType),
        "models": list(MODEL_SERVICE_MAPPING.keys())
    }


@router.get("/stats")
async def get_stats():
    """Get proxy statistics"""
    stats = {}
    
    for service_type in ChatServiceType:
        service_stats = await load_balancer.get_service_stats(service_type)
        stats[service_type.value] = service_stats
        
    return {
        "timestamp": datetime.now().isoformat(),
        "services": stats
    }
