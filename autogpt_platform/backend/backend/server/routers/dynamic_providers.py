"""
Dynamic Provider Management API Endpoints.

Provides REST API for runtime addition, configuration, and management
of webchat providers with authentication and testing capabilities.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr

from backend.data.dynamic_provider_models import (
    DynamicProvider,
    ProviderStatus,
    AuthenticationMethod,
    ProviderType,
    AuthenticationConfig,
    ProviderTestResult,
    SystemConfiguration
)
from backend.util.dynamic_provider_manager import DynamicProviderManager
from backend.util.auth import get_user_id


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/dynamic-providers", tags=["dynamic-providers"])

# Global provider manager instance (will be set during startup)
provider_manager: Optional[DynamicProviderManager] = None


# Request/Response Models
class AddProviderRequest(BaseModel):
    """Request model for adding a new provider"""
    name: str = Field(..., description="Provider display name", min_length=2, max_length=100)
    base_url: str = Field(..., description="Base URL of the webchat interface")
    chat_url: Optional[str] = Field(default=None, description="Direct chat interface URL")
    provider_type: ProviderType = Field(default=ProviderType.WEBCHAT, description="Provider type")
    
    # Authentication configuration
    auth_method: AuthenticationMethod = Field(..., description="Authentication method")
    email: Optional[str] = Field(default=None, description="Email/username for authentication")
    password: Optional[SecretStr] = Field(default=None, description="Password for authentication")
    
    # Optional login configuration
    login_url: Optional[str] = Field(default=None, description="Custom login page URL")
    email_selector: Optional[str] = Field(default=None, description="Email input CSS selector")
    password_selector: Optional[str] = Field(default=None, description="Password input CSS selector")
    submit_selector: Optional[str] = Field(default=None, description="Submit button CSS selector")
    
    # Chat interface selectors
    chat_input_selector: Optional[str] = Field(default=None, description="Chat input CSS selector")
    send_button_selector: Optional[str] = Field(default=None, description="Send button CSS selector")
    response_selector: Optional[str] = Field(default=None, description="Response area CSS selector")
    
    # Configuration
    timeout_seconds: int = Field(default=30, description="Request timeout", ge=5, le=300)
    max_retries: int = Field(default=3, description="Maximum retry attempts", ge=1, le=10)
    
    # Metadata
    description: Optional[str] = Field(default=None, description="Provider description")
    tags: List[str] = Field(default_factory=list, description="Provider tags")
    supported_models: List[str] = Field(default_factory=list, description="Supported model names")
    
    # Flags
    is_default: bool = Field(default=False, description="Set as default provider")
    auto_authenticate: bool = Field(default=True, description="Automatically authenticate after adding")


class UpdateProviderRequest(BaseModel):
    """Request model for updating a provider"""
    name: Optional[str] = Field(default=None, description="Provider display name")
    base_url: Optional[str] = Field(default=None, description="Base URL")
    chat_url: Optional[str] = Field(default=None, description="Chat interface URL")
    
    # Authentication updates
    email: Optional[str] = Field(default=None, description="New email/username")
    password: Optional[SecretStr] = Field(default=None, description="New password")
    
    # Selector updates
    email_selector: Optional[str] = Field(default=None, description="Email input selector")
    password_selector: Optional[str] = Field(default=None, description="Password input selector")
    submit_selector: Optional[str] = Field(default=None, description="Submit button selector")
    chat_input_selector: Optional[str] = Field(default=None, description="Chat input selector")
    send_button_selector: Optional[str] = Field(default=None, description="Send button selector")
    response_selector: Optional[str] = Field(default=None, description="Response selector")
    
    # Configuration updates
    timeout_seconds: Optional[int] = Field(default=None, description="Request timeout")
    max_retries: Optional[int] = Field(default=None, description="Maximum retries")
    
    # Metadata updates
    description: Optional[str] = Field(default=None, description="Provider description")
    tags: Optional[List[str]] = Field(default=None, description="Provider tags")
    supported_models: Optional[List[str]] = Field(default=None, description="Supported models")
    
    # Status updates
    is_enabled: Optional[bool] = Field(default=None, description="Enable/disable provider")
    is_default: Optional[bool] = Field(default=None, description="Set as default provider")


class ProviderResponse(BaseModel):
    """Response model for provider information"""
    id: str
    name: str
    provider_type: str
    base_url: str
    chat_url: Optional[str]
    status: str
    is_enabled: bool
    is_default: bool
    
    # Authentication info (without sensitive data)
    auth_method: str
    email: Optional[str]
    has_password: bool
    
    # Health and metrics
    is_healthy: bool
    last_authenticated: Optional[datetime]
    last_tested: Optional[datetime]
    total_requests: int
    success_rate: float
    avg_response_time: float
    
    # Configuration
    timeout_seconds: int
    max_retries: int
    supported_models: List[str]
    
    # Metadata
    description: Optional[str]
    tags: List[str]
    created_at: datetime
    updated_at: datetime


class TestProviderRequest(BaseModel):
    """Request model for testing a provider"""
    test_message: str = Field(default="Hello, this is a test message.", description="Test message to send")
    timeout_seconds: int = Field(default=30, description="Test timeout", ge=5, le=120)


class SystemConfigResponse(BaseModel):
    """Response model for system configuration"""
    default_provider_id: Optional[str]
    fallback_provider_id: Optional[str]
    total_providers: int
    active_providers: int
    total_model_mappings: int
    auto_authenticate: bool
    health_check_interval: int
    enable_fuzzy_matching: bool


# API Endpoints
@router.post("/providers", response_model=ProviderResponse)
async def add_provider(
    request: AddProviderRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id)
):
    """Add a new dynamic provider"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    try:
        # Create authentication config
        auth_config = AuthenticationConfig(
            method=request.auth_method,
            email=request.email,
            password=request.password,
            login_url=request.login_url,
            email_selector=request.email_selector,
            password_selector=request.password_selector,
            submit_selector=request.submit_selector
        )
        
        # Prepare provider data
        provider_data = {
            "name": request.name,
            "provider_type": request.provider_type,
            "base_url": request.base_url,
            "chat_url": request.chat_url,
            "auth_config": auth_config,
            "is_default": request.is_default,
            "timeout_seconds": request.timeout_seconds,
            "max_retries": request.max_retries,
            "chat_input_selector": request.chat_input_selector,
            "send_button_selector": request.send_button_selector,
            "response_selector": request.response_selector,
            "description": request.description,
            "tags": request.tags,
            "supported_models": request.supported_models
        }
        
        # Add provider
        provider = await provider_manager.add_provider(provider_data)
        
        # Set as default if requested
        if request.is_default:
            await set_default_provider(provider.id)
        
        # Schedule authentication if requested
        if request.auto_authenticate:
            background_tasks.add_task(authenticate_provider_background, provider.id)
        
        return _provider_to_response(provider)
        
    except Exception as e:
        logger.error(f"Failed to add provider: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/providers", response_model=List[ProviderResponse])
async def list_providers(
    status: Optional[str] = None,
    enabled_only: bool = False,
    user_id: str = Depends(get_user_id)
):
    """List all dynamic providers"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    try:
        providers = list(provider_manager.providers.values())
        
        # Apply filters
        if status:
            providers = [p for p in providers if p.status == status]
        
        if enabled_only:
            providers = [p for p in providers if p.is_enabled]
        
        return [_provider_to_response(provider) for provider in providers]
        
    except Exception as e:
        logger.error(f"Failed to list providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get a specific provider by ID"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    provider = provider_manager.providers.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    return _provider_to_response(provider)


@router.put("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: str,
    request: UpdateProviderRequest,
    user_id: str = Depends(get_user_id)
):
    """Update a provider configuration"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    provider = provider_manager.providers.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    try:
        # Update basic fields
        if request.name is not None:
            provider.name = request.name
        if request.base_url is not None:
            provider.base_url = request.base_url
        if request.chat_url is not None:
            provider.chat_url = request.chat_url
        
        # Update authentication
        if request.email is not None:
            provider.auth_config.email = request.email
        if request.password is not None:
            provider.auth_config.password = request.password
        
        # Update selectors
        if request.email_selector is not None:
            provider.auth_config.email_selector = request.email_selector
        if request.password_selector is not None:
            provider.auth_config.password_selector = request.password_selector
        if request.submit_selector is not None:
            provider.auth_config.submit_selector = request.submit_selector
        if request.chat_input_selector is not None:
            provider.chat_input_selector = request.chat_input_selector
        if request.send_button_selector is not None:
            provider.send_button_selector = request.send_button_selector
        if request.response_selector is not None:
            provider.response_selector = request.response_selector
        
        # Update configuration
        if request.timeout_seconds is not None:
            provider.timeout_seconds = request.timeout_seconds
        if request.max_retries is not None:
            provider.max_retries = request.max_retries
        
        # Update metadata
        if request.description is not None:
            provider.description = request.description
        if request.tags is not None:
            provider.tags = request.tags
        if request.supported_models is not None:
            provider.supported_models = request.supported_models
        
        # Update status
        if request.is_enabled is not None:
            provider.is_enabled = request.is_enabled
        if request.is_default is not None:
            provider.is_default = request.is_default
            if request.is_default:
                await set_default_provider(provider_id)
        
        # Update timestamp
        provider.updated_at = datetime.now()
        
        return _provider_to_response(provider)
        
    except Exception as e:
        logger.error(f"Failed to update provider {provider_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    user_id: str = Depends(get_user_id)
):
    """Delete a provider"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    success = await provider_manager.remove_provider(provider_id)
    if not success:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    return {"message": "Provider deleted successfully"}


@router.post("/providers/{provider_id}/authenticate")
async def authenticate_provider(
    provider_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id)
):
    """Authenticate a provider"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    provider = provider_manager.providers.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Schedule authentication in background
    background_tasks.add_task(authenticate_provider_background, provider_id)
    
    return {"message": "Authentication started", "provider_id": provider_id}


@router.post("/providers/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider(
    provider_id: str,
    request: TestProviderRequest,
    user_id: str = Depends(get_user_id)
):
    """Test a provider with a sample query"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    provider = provider_manager.providers.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    try:
        # Perform test query
        result = await provider_manager.test_provider(
            provider_id=provider_id,
            test_message=request.test_message,
            timeout_seconds=request.timeout_seconds
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to test provider {provider_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/providers/{provider_id}/enable")
async def enable_provider(
    provider_id: str,
    user_id: str = Depends(get_user_id)
):
    """Enable a provider"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    provider = provider_manager.providers.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    provider.is_enabled = True
    provider.updated_at = datetime.now()
    
    return {"message": "Provider enabled", "provider_id": provider_id}


@router.post("/providers/{provider_id}/disable")
async def disable_provider(
    provider_id: str,
    user_id: str = Depends(get_user_id)
):
    """Disable a provider"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    provider = provider_manager.providers.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    provider.is_enabled = False
    provider.updated_at = datetime.now()
    
    return {"message": "Provider disabled", "provider_id": provider_id}


@router.get("/system/config", response_model=SystemConfigResponse)
async def get_system_config(user_id: str = Depends(get_user_id)):
    """Get system configuration"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    config = provider_manager.system_config
    
    active_providers = len([p for p in provider_manager.providers.values() if p.is_enabled])
    
    return SystemConfigResponse(
        default_provider_id=config.default_provider_id,
        fallback_provider_id=config.fallback_provider_id,
        total_providers=len(provider_manager.providers),
        active_providers=active_providers,
        total_model_mappings=len(config.model_mappings),
        auto_authenticate=config.auto_authenticate,
        health_check_interval=config.health_check_interval,
        enable_fuzzy_matching=config.enable_fuzzy_matching
    )


@router.put("/system/default-provider/{provider_id}")
async def set_default_provider(
    provider_id: str,
    user_id: str = Depends(get_user_id)
):
    """Set the default provider"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    provider = provider_manager.providers.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Clear existing default
    for p in provider_manager.providers.values():
        p.is_default = False
    
    # Set new default
    provider.is_default = True
    provider_manager.system_config.default_provider_id = provider_id
    
    return {"message": "Default provider set", "provider_id": provider_id}


@router.get("/models/mappings")
async def get_model_mappings(user_id: str = Depends(get_user_id)):
    """Get all model-to-provider mappings"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    mappings = []
    for mapping in provider_manager.system_config.model_mappings:
        provider = provider_manager.providers.get(mapping.provider_id)
        mappings.append({
            "model_name": mapping.model_name,
            "provider_id": mapping.provider_id,
            "provider_name": provider.name if provider else "Unknown",
            "priority": mapping.priority,
            "is_exact_match": mapping.is_exact_match,
            "created_at": mapping.created_at
        })
    
    return {"mappings": mappings}


@router.post("/models/mappings")
async def add_model_mapping(
    model_name: str,
    provider_id: str,
    priority: int = 1,
    is_exact_match: bool = True,
    user_id: str = Depends(get_user_id)
):
    """Add a new model mapping"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    provider = provider_manager.providers.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    provider_manager.system_config.add_model_mapping(
        model_name=model_name,
        provider_id=provider_id,
        priority=priority,
        is_exact_match=is_exact_match
    )
    
    return {"message": "Model mapping added", "model_name": model_name, "provider_id": provider_id}


@router.delete("/models/mappings")
async def remove_model_mapping(
    model_name: str,
    provider_id: str,
    user_id: str = Depends(get_user_id)
):
    """Remove a model mapping"""
    if not provider_manager:
        raise HTTPException(status_code=503, detail="Provider manager not initialized")
    
    provider_manager.system_config.remove_model_mapping(model_name, provider_id)
    
    return {"message": "Model mapping removed", "model_name": model_name, "provider_id": provider_id}


# Helper Functions
def _provider_to_response(provider: DynamicProvider) -> ProviderResponse:
    """Convert provider model to response model"""
    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type.value,
        base_url=provider.base_url,
        chat_url=provider.chat_url,
        status=provider.status.value,
        is_enabled=provider.is_enabled,
        is_default=provider.is_default,
        auth_method=provider.auth_config.method.value,
        email=provider.auth_config.email,
        has_password=provider.auth_config.password is not None,
        is_healthy=provider.is_healthy(),
        last_authenticated=provider.last_authenticated,
        last_tested=provider.last_tested,
        total_requests=provider.metrics.total_requests,
        success_rate=provider.metrics.calculate_success_rate(),
        avg_response_time=provider.metrics.avg_response_time,
        timeout_seconds=provider.timeout_seconds,
        max_retries=provider.max_retries,
        supported_models=provider.supported_models,
        description=provider.description,
        tags=provider.tags,
        created_at=provider.created_at,
        updated_at=provider.updated_at
    )


async def authenticate_provider_background(provider_id: str):
    """Background task for provider authentication"""
    try:
        if provider_manager:
            await provider_manager.authenticate_provider(provider_id)
    except Exception as e:
        logger.error(f"Background authentication failed for provider {provider_id}: {e}")


# Startup function to set provider manager
def set_provider_manager(manager: DynamicProviderManager):
    """Set the global provider manager instance"""
    global provider_manager
    provider_manager = manager
