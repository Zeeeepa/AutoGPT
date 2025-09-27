"""
Provider Management API endpoints for the chat proxy system.
Handles provider configuration, scaling rules, and browser instance management.
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import asyncio
import json

from backend.util.smart_scaling_engine import SmartScalingEngine
from backend.util.browser_instance_manager import BrowserInstanceManager
from backend.data.chat_proxy_models import ChatServiceType


logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances (will be initialized on startup)
scaling_engine: Optional[SmartScalingEngine] = None
browser_manager: Optional[BrowserInstanceManager] = None
websocket_connections: List[WebSocket] = []


class ProviderConfig(BaseModel):
    """Provider configuration model."""
    service_type: str
    enabled: bool
    endpoint_url: Optional[str] = None
    custom_settings: Optional[Dict] = None


class ScalingRuleConfig(BaseModel):
    """Scaling rule configuration model."""
    auto_scale_enabled: bool = True
    idle_timeout_minutes: int = 30
    max_instances: int = 3
    providers_per_instance: int = 5
    scaling_cooldown_seconds: int = 60


class BrowserInstanceConfig(BaseModel):
    """Browser instance configuration model."""
    instance_id: int
    enabled: bool
    fingerprint_config: Optional[Dict] = None


# Startup and shutdown events
async def initialize_provider_management():
    """Initialize the provider management system."""
    global scaling_engine, browser_manager
    
    try:
        # Initialize browser manager
        browser_manager = BrowserInstanceManager()
        
        # Initialize scaling engine
        scaling_engine = SmartScalingEngine(browser_manager)
        
        # Start the scaling engine
        await scaling_engine.start()
        
        # Start Instance 1 (always active)
        await browser_manager.start_instance(1)
        
        logger.info("Provider management system initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize provider management: {e}")
        raise


async def shutdown_provider_management():
    """Shutdown the provider management system."""
    global scaling_engine, browser_manager
    
    try:
        if scaling_engine:
            await scaling_engine.stop()
        
        if browser_manager:
            # Stop all instances
            for instance_id in range(1, 4):
                await browser_manager.stop_instance(instance_id)
        
        logger.info("Provider management system shutdown successfully")
        
    except Exception as e:
        logger.error(f"Error during provider management shutdown: {e}")


# Provider Management Endpoints

@router.get("/providers")
async def list_providers():
    """List all available providers and their status."""
    if not scaling_engine:
        raise HTTPException(status_code=503, detail="Scaling engine not initialized")
    
    try:
        status = scaling_engine.get_status()
        
        # Format provider information
        providers = []
        for service_type in ChatServiceType:
            provider_info = {
                "service_type": service_type.value,
                "enabled": service_type in scaling_engine.provider_status,
                "status": "active" if service_type in scaling_engine.provider_status else "inactive",
                "browser_instance_id": None,
                "is_busy": False,
                "active_requests": 0,
                "total_requests": 0,
                "error_count": 0
            }
            
            if service_type in scaling_engine.provider_status:
                provider = scaling_engine.provider_status[service_type]
                provider_info.update({
                    "browser_instance_id": provider.browser_instance_id,
                    "is_busy": provider.is_busy,
                    "active_requests": provider.active_requests,
                    "total_requests": provider.total_requests,
                    "error_count": provider.error_count,
                    "last_request_time": provider.last_request_time.isoformat() if provider.last_request_time else None
                })
            
            providers.append(provider_info)
        
        return {
            "providers": providers,
            "total_providers": len(providers),
            "active_providers": len([p for p in providers if p["enabled"]]),
            "metrics": status["metrics"]
        }
        
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/providers/{service_type}/enable")
async def enable_provider(service_type: str):
    """Enable a specific provider."""
    if not scaling_engine:
        raise HTTPException(status_code=503, detail="Scaling engine not initialized")
    
    try:
        # Validate service type
        try:
            service_enum = ChatServiceType(service_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid service type: {service_type}")
        
        # For now, providers are enabled by default when instances start
        # In the future, this could be more dynamic
        
        return {
            "success": True,
            "message": f"Provider {service_type} enabled",
            "service_type": service_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling provider {service_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/providers/{service_type}/disable")
async def disable_provider(service_type: str):
    """Disable a specific provider."""
    if not scaling_engine:
        raise HTTPException(status_code=503, detail="Scaling engine not initialized")
    
    try:
        # Validate service type
        try:
            service_enum = ChatServiceType(service_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid service type: {service_type}")
        
        # For now, providers are disabled when instances stop
        # In the future, this could be more granular
        
        return {
            "success": True,
            "message": f"Provider {service_type} disabled",
            "service_type": service_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling provider {service_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Browser Instance Management Endpoints

@router.get("/instances")
async def list_browser_instances():
    """List all browser instances and their status."""
    if not browser_manager:
        raise HTTPException(status_code=503, detail="Browser manager not initialized")
    
    try:
        instances_status = browser_manager.get_all_instances_status()
        
        # Add health check information
        for instance_id_str, instance_info in instances_status.items():
            if instance_info:
                instance_id = int(instance_id_str)
                health = await browser_manager.health_check_instance(instance_id)
                instance_info["health"] = health
        
        return {
            "instances": instances_status,
            "total_instances": len(instances_status),
            "active_instances": len([i for i in instances_status.values() if i and i["is_active"]])
        }
        
    except Exception as e:
        logger.error(f"Error listing browser instances: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances/{instance_id}/start")
async def start_browser_instance(instance_id: int):
    """Start a specific browser instance."""
    if not browser_manager:
        raise HTTPException(status_code=503, detail="Browser manager not initialized")
    
    if instance_id < 1 or instance_id > 3:
        raise HTTPException(status_code=400, detail="Instance ID must be 1, 2, or 3")
    
    try:
        success = await browser_manager.start_instance(instance_id)
        
        if success:
            # Notify WebSocket clients
            await broadcast_instance_update(instance_id, "started")
            
            return {
                "success": True,
                "message": f"Browser Instance {instance_id} started successfully",
                "instance_id": instance_id
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to start Browser Instance {instance_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting Browser Instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances/{instance_id}/stop")
async def stop_browser_instance(instance_id: int):
    """Stop a specific browser instance."""
    if not browser_manager:
        raise HTTPException(status_code=503, detail="Browser manager not initialized")
    
    if instance_id == 1:
        raise HTTPException(status_code=400, detail="Cannot stop Instance 1 (always active)")
    
    if instance_id < 1 or instance_id > 3:
        raise HTTPException(status_code=400, detail="Instance ID must be 1, 2, or 3")
    
    try:
        success = await browser_manager.stop_instance(instance_id)
        
        if success:
            # Notify WebSocket clients
            await broadcast_instance_update(instance_id, "stopped")
            
            return {
                "success": True,
                "message": f"Browser Instance {instance_id} stopped successfully",
                "instance_id": instance_id
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to stop Browser Instance {instance_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping Browser Instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances/{instance_id}/health")
async def check_instance_health(instance_id: int):
    """Check health of a specific browser instance."""
    if not browser_manager:
        raise HTTPException(status_code=503, detail="Browser manager not initialized")
    
    if instance_id < 1 or instance_id > 3:
        raise HTTPException(status_code=400, detail="Instance ID must be 1, 2, or 3")
    
    try:
        health = await browser_manager.health_check_instance(instance_id)
        return health
        
    except Exception as e:
        logger.error(f"Error checking health for Instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Scaling Management Endpoints

@router.get("/scaling/status")
async def get_scaling_status():
    """Get current scaling engine status."""
    if not scaling_engine:
        raise HTTPException(status_code=503, detail="Scaling engine not initialized")
    
    try:
        return scaling_engine.get_status()
        
    except Exception as e:
        logger.error(f"Error getting scaling status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scaling/rules")
async def get_scaling_rules():
    """Get current scaling rules configuration."""
    if not scaling_engine:
        raise HTTPException(status_code=503, detail="Scaling engine not initialized")
    
    return {
        "idle_timeout_minutes": scaling_engine.IDLE_TIMEOUT_MINUTES,
        "max_instances": scaling_engine.MAX_INSTANCES,
        "providers_per_instance": scaling_engine.PROVIDERS_PER_INSTANCE,
        "scaling_cooldown_seconds": scaling_engine.SCALING_COOLDOWN_SECONDS
    }


@router.post("/scaling/rules")
async def update_scaling_rules(rules: ScalingRuleConfig):
    """Update scaling rules configuration."""
    if not scaling_engine:
        raise HTTPException(status_code=503, detail="Scaling engine not initialized")
    
    try:
        # Update scaling engine configuration
        scaling_engine.IDLE_TIMEOUT_MINUTES = rules.idle_timeout_minutes
        scaling_engine.MAX_INSTANCES = rules.max_instances
        scaling_engine.PROVIDERS_PER_INSTANCE = rules.providers_per_instance
        scaling_engine.SCALING_COOLDOWN_SECONDS = rules.scaling_cooldown_seconds
        
        return {
            "success": True,
            "message": "Scaling rules updated successfully",
            "rules": rules.dict()
        }
        
    except Exception as e:
        logger.error(f"Error updating scaling rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# System Status Endpoints

@router.get("/status")
async def get_system_status():
    """Get overall system status."""
    try:
        status = {
            "system_healthy": True,
            "scaling_engine_active": scaling_engine is not None,
            "browser_manager_active": browser_manager is not None,
            "websocket_connections": len(websocket_connections)
        }
        
        if scaling_engine:
            scaling_status = scaling_engine.get_status()
            status.update({
                "total_active_instances": scaling_status["metrics"]["total_active_instances"],
                "total_active_providers": scaling_status["metrics"]["total_active_providers"],
                "total_concurrent_requests": scaling_status["metrics"]["total_concurrent_requests"],
                "pending_requests": scaling_status["metrics"]["pending_requests"]
            })
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket for Real-time Updates

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    websocket_connections.append(websocket)
    
    try:
        # Send initial status
        if scaling_engine:
            initial_status = scaling_engine.get_status()
            await websocket.send_text(json.dumps({
                "type": "initial_status",
                "data": initial_status
            }))
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages (ping/pong, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
    
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)


async def broadcast_status_update():
    """Broadcast status updates to all connected WebSocket clients."""
    if not scaling_engine or not websocket_connections:
        return
    
    try:
        status = scaling_engine.get_status()
        message = json.dumps({
            "type": "status_update",
            "data": status
        })
        
        # Send to all connected clients
        disconnected = []
        for websocket in websocket_connections:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            websocket_connections.remove(websocket)
    
    except Exception as e:
        logger.error(f"Error broadcasting status update: {e}")


async def broadcast_instance_update(instance_id: int, action: str):
    """Broadcast browser instance updates to WebSocket clients."""
    if not websocket_connections:
        return
    
    try:
        message = json.dumps({
            "type": "instance_update",
            "data": {
                "instance_id": instance_id,
                "action": action,
                "timestamp": asyncio.get_event_loop().time()
            }
        })
        
        # Send to all connected clients
        disconnected = []
        for websocket in websocket_connections:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            websocket_connections.remove(websocket)
    
    except Exception as e:
        logger.error(f"Error broadcasting instance update: {e}")


# Background task for periodic status updates
async def start_status_broadcaster():
    """Start background task for periodic status updates."""
    while True:
        try:
            await broadcast_status_update()
            await asyncio.sleep(10)  # Broadcast every 10 seconds
        except Exception as e:
            logger.error(f"Error in status broadcaster: {e}")
            await asyncio.sleep(10)
