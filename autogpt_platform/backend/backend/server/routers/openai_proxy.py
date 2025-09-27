"""
OpenAI-compatible API proxy for chat services.
Provides drop-in replacement for OpenAI API using browser automation.
"""

import asyncio
import json
import logging
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

# Global reference to scaling engine (will be set during startup)
scaling_engine = None


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


# Model mapping to chat services
MODEL_SERVICE_MAPPING = {
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


async def get_chat_service_from_model(model: str) -> ChatServiceType:
    """Map OpenAI model name to chat service type"""
    service_type = MODEL_SERVICE_MAPPING.get(model)
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
    http_request: Request
) -> ChatCompletionResponse:
    """
    OpenAI-compatible chat completions endpoint.
    Routes requests to appropriate chat services via browser automation.
    """
    try:
        # Get Stagehand API key from environment or request headers
        stagehand_api_key = http_request.headers.get("X-Stagehand-API-Key")
        if not stagehand_api_key:
            # For demo purposes, use a default key
            # In production, this should be properly configured
            stagehand_api_key = "your-stagehand-api-key"
            
        # Map model to service
        service_type = await get_chat_service_from_model(request.model)
        
        logger.info(f"Processing chat completion for {service_type} with model {request.model}")
        
        # Use smart scaling engine if available, otherwise fallback to load balancer
        if scaling_engine:
            # Convert request to dict format for scaling engine
            request_data = {
                "model": request.model,
                "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stream": request.stream
            }
            
            try:
                # Handle request through scaling engine
                response = await scaling_engine.handle_request(service_type, request_data)
                
                # Return the OpenAI-formatted response directly
                return response
                
            except Exception as e:
                logger.error(f"Scaling engine error: {e}")
                # Fallback to traditional method
                pass
        
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
    """List available models (OpenAI-compatible)"""
    models = []
    
    for model_name, service_type in MODEL_SERVICE_MAPPING.items():
        models.append({
            "id": model_name,
            "object": "model",
            "created": int(time.time()),
            "owned_by": f"chat-proxy-{service_type.value}",
            "permission": [],
            "root": model_name,
            "parent": None
        })
        
    return {
        "object": "list",
        "data": models
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
