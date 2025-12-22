"""
Simple Provider Addition API - The main user-facing API for adding providers.

This module provides the simple API endpoint that allows users to add chat providers
with just domain, username, and password - exactly as requested by the user.
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import asyncio

from backend.core.ai_provider_engine import AIProviderEngine
from backend.core.provider_interfaces import AIProviderEngineConfig
from backend.util.stagehand_integration import (
    StagehandElementDetector, StagehandAuthenticator, StagehandChatProvider
)
from backend.util.provider_validator import AIProviderValidator
from backend.server.dependencies import ScalingEngineDep


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/providers", tags=["simple-provider-api"])

# Global AI Provider Engine instance
ai_provider_engine: Optional[AIProviderEngine] = None


class AddProviderRequest(BaseModel):
    """Request model for adding a provider with minimal configuration."""
    domain: str = Field(..., description="Domain of the chat service (e.g., 'chat.mistral.ai')")
    username: str = Field(..., description="Username or email for authentication")
    password: str = Field(..., description="Password for authentication")
    
    # Optional fields
    display_name: Optional[str] = Field(None, description="Custom display name for the provider")
    tags: Optional[List[str]] = Field(None, description="Tags for organizing providers")
    ui_hints: Optional[Dict[str, Any]] = Field(None, description="Optional UI hints for better detection")


class AddProviderResponse(BaseModel):
    """Response model for provider addition."""
    success: bool
    provider_id: str
    domain: str
    status: str
    message: str
    discovery_results: Optional[Dict[str, Any]] = None
    test_results: Optional[Dict[str, Any]] = None
    endpoints: Optional[Dict[str, str]] = None


class ProviderInfo(BaseModel):
    """Provider information model."""
    provider_id: str
    domain: str
    display_name: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    tags: List[str] = []
    has_custom_selectors: bool = False


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str = Field(..., description="Message to send to the chat provider")
    provider_id: Optional[str] = Field(None, description="Specific provider to use (optional)")


class ChatResponse(BaseModel):
    """Chat response model."""
    success: bool
    content: str
    provider_id: str
    response_time: Optional[float] = None
    error_message: Optional[str] = None


async def get_ai_provider_engine() -> AIProviderEngine:
    """Get or create the AI provider engine instance."""
    global ai_provider_engine
    
    if ai_provider_engine is None:
        # Create configuration
        config = AIProviderEngineConfig(
            stagehand_api_key=None,  # Will be loaded from environment
            ai_detection_timeout=30,
            ai_confidence_threshold=0.7,
            browser_timeout=60,
            browser_headless=True,
            max_concurrent_sessions=10,
            session_timeout=300,
            auto_scale_enabled=True,
            enable_monitoring=True,
            metrics_collection_interval=60,
            health_check_interval=300
        )
        
        # Create engine
        ai_provider_engine = AIProviderEngine(config)
        
        # Set up components
        element_detector = StagehandElementDetector()
        authenticator = StagehandAuthenticator(element_detector)
        chat_provider = StagehandChatProvider(element_detector)
        validator = AIProviderValidator(element_detector, authenticator, chat_provider)
        
        ai_provider_engine.set_element_detector(element_detector)
        ai_provider_engine.set_authenticator(authenticator)
        ai_provider_engine.set_chat_provider(chat_provider)
        ai_provider_engine.set_validator(validator)
        
        # Start the engine
        await ai_provider_engine.start()
        
        logger.info("AI Provider Engine initialized and started")
    
    return ai_provider_engine


@router.post("/add", response_model=AddProviderResponse)
async def add_provider(
    request: AddProviderRequest,
    background_tasks: BackgroundTasks
) -> AddProviderResponse:
    """
    Add a new chat provider with simple domain/username/password configuration.
    
    This is the main endpoint that implements the user's requirement:
    Just provide domain, username, password and the system automatically
    discovers and configures the chat interface.
    
    Example:
    ```
    POST /api/providers/add
    {
        "domain": "chat.mistral.ai",
        "username": "emailaddress@email.com",
        "password": "Password"
    }
    ```
    """
    logger.info(f"Adding provider for domain: {request.domain}")
    
    try:
        # Get AI provider engine
        engine = await get_ai_provider_engine()
        
        # Add provider using the simple interface
        provider_id, results = await engine.add_provider_simple(
            domain=request.domain,
            username=request.username,
            password=request.password,
            display_name=request.display_name,
            tags=request.tags,
            ui_hints=request.ui_hints
        )
        
        if results["success"]:
            # Create endpoints for the new provider
            endpoints = {
                "chat": f"/api/providers/{provider_id}/chat",
                "status": f"/api/providers/{provider_id}/status",
                "test": f"/api/providers/{provider_id}/test"
            }
            
            return AddProviderResponse(
                success=True,
                provider_id=provider_id,
                domain=request.domain,
                status=results.get("status", "active"),
                message=f"Successfully added provider for {request.domain}",
                discovery_results=results.get("discovery_results"),
                test_results=results.get("test_results"),
                endpoints=endpoints
            )
        else:
            return AddProviderResponse(
                success=False,
                provider_id="",
                domain=request.domain,
                status="error",
                message=f"Failed to add provider: {results.get('error', 'Unknown error')}",
                discovery_results=results.get("discovery_results"),
                test_results=results.get("test_results")
            )
            
    except Exception as e:
        logger.error(f"Error adding provider for {request.domain}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add provider: {str(e)}"
        )


@router.get("/list", response_model=List[ProviderInfo])
async def list_providers() -> List[ProviderInfo]:
    """List all registered providers."""
    try:
        engine = await get_ai_provider_engine()
        providers_data = await engine.list_providers()
        
        return [
            ProviderInfo(
                provider_id=p["provider_id"],
                domain=p["domain"],
                display_name=p["display_name"],
                status=p["status"],
                created_at=p.get("created_at"),
                updated_at=p.get("updated_at"),
                tags=p.get("tags", []),
                has_custom_selectors=p.get("has_custom_selectors", False)
            )
            for p in providers_data
        ]
        
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list providers: {str(e)}"
        )


@router.get("/{provider_id}", response_model=ProviderInfo)
async def get_provider(provider_id: str) -> ProviderInfo:
    """Get detailed information about a specific provider."""
    try:
        engine = await get_ai_provider_engine()
        provider_data = await engine.get_provider_info(provider_id)
        
        if not provider_data:
            raise HTTPException(
                status_code=404,
                detail=f"Provider {provider_id} not found"
            )
        
        return ProviderInfo(
            provider_id=provider_data["provider_id"],
            domain=provider_data["domain"],
            display_name=provider_data["display_name"],
            status=provider_data["status"],
            created_at=provider_data.get("created_at"),
            updated_at=provider_data.get("updated_at"),
            tags=provider_data.get("tags", []),
            has_custom_selectors=provider_data.get("has_custom_selectors", False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider {provider_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get provider: {str(e)}"
        )


@router.post("/{provider_id}/chat", response_model=ChatResponse)
async def chat_with_provider(
    provider_id: str,
    request: ChatRequest
) -> ChatResponse:
    """
    Send a message to a specific provider.
    
    This endpoint allows chatting with any registered provider.
    """
    try:
        engine = await get_ai_provider_engine()
        
        # Send message to the provider
        response = await engine.send_message(provider_id, request.message)
        
        return ChatResponse(
            success=response.success,
            content=response.content,
            provider_id=response.provider_id,
            response_time=response.response_time,
            error_message=response.error_message
        )
        
    except Exception as e:
        logger.error(f"Error chatting with provider {provider_id}: {e}")
        return ChatResponse(
            success=False,
            content="",
            provider_id=provider_id,
            error_message=str(e)
        )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_any_provider(
    request: ChatRequest
) -> ChatResponse:
    """
    Send a message to any available provider.
    
    If provider_id is specified, uses that provider.
    Otherwise, uses the first available active provider.
    """
    try:
        engine = await get_ai_provider_engine()
        
        provider_id = request.provider_id
        
        # If no provider specified, find the first active one
        if not provider_id:
            providers = await engine.list_providers()
            active_providers = [p for p in providers if p["status"] == "active"]
            
            if not active_providers:
                return ChatResponse(
                    success=False,
                    content="",
                    provider_id="",
                    error_message="No active providers available"
                )
            
            provider_id = active_providers[0]["provider_id"]
        
        # Send message to the provider
        response = await engine.send_message(provider_id, request.message)
        
        return ChatResponse(
            success=response.success,
            content=response.content,
            provider_id=response.provider_id,
            response_time=response.response_time,
            error_message=response.error_message
        )
        
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return ChatResponse(
            success=False,
            content="",
            provider_id=request.provider_id or "",
            error_message=str(e)
        )


@router.delete("/{provider_id}")
async def remove_provider(provider_id: str) -> Dict[str, Any]:
    """Remove a provider."""
    try:
        engine = await get_ai_provider_engine()
        success = await engine.remove_provider(provider_id)
        
        if success:
            return {
                "success": True,
                "message": f"Provider {provider_id} removed successfully"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Provider {provider_id} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing provider {provider_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove provider: {str(e)}"
        )


@router.get("/{provider_id}/test")
async def test_provider(provider_id: str) -> Dict[str, Any]:
    """Test a provider's functionality."""
    try:
        engine = await get_ai_provider_engine()
        
        # Send a test message
        test_message = "Hello, this is a test message. Please respond with 'Test successful' if you can see this."
        response = await engine.send_message(provider_id, test_message)
        
        return {
            "success": response.success,
            "provider_id": provider_id,
            "test_message": test_message,
            "response": response.content if response.success else None,
            "response_time": response.response_time,
            "error": response.error_message if not response.success else None
        }
        
    except Exception as e:
        logger.error(f"Error testing provider {provider_id}: {e}")
        return {
            "success": False,
            "provider_id": provider_id,
            "error": str(e)
        }


@router.get("/stats/overview")
async def get_stats() -> Dict[str, Any]:
    """Get system statistics and overview."""
    try:
        engine = await get_ai_provider_engine()
        stats = engine.get_stats()
        
        return {
            "system_status": "operational",
            "ai_provider_engine": "active",
            "providers": stats,
            "features": {
                "ai_element_detection": True,
                "automatic_provider_discovery": True,
                "adaptive_ui_handling": True,
                "cloudflare_scaling": False,  # Will be enabled in Phase 2
                "real_time_monitoring": True
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {
            "system_status": "error",
            "error": str(e)
        }


# Health check endpoint
@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    try:
        engine = await get_ai_provider_engine()
        return {
            "status": "healthy",
            "ai_provider_engine": "active",
            "timestamp": str(asyncio.get_event_loop().time())
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": str(asyncio.get_event_loop().time())
        }
