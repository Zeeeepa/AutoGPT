"""
System Management API Endpoints.

Provides REST API endpoints for managing the enhanced chat proxy system including
configuration management, session monitoring, scaling control, and health checks.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["System Management"])


# Response Models
class SystemHealthResponse(BaseModel):
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    components: Dict[str, Dict[str, Any]] = Field(..., description="Component health status")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    version: str = Field(..., description="System version")


class SystemMetricsResponse(BaseModel):
    timestamp: datetime = Field(..., description="Metrics timestamp")
    requests_per_minute: float = Field(..., description="Current requests per minute")
    requests_per_hour: float = Field(..., description="Current requests per hour")
    average_response_time: float = Field(..., description="Average response time in seconds")
    error_rate: float = Field(..., description="Error rate percentage")
    active_sessions: int = Field(..., description="Number of active sessions")
    active_providers: int = Field(..., description="Number of active providers")
    scaling_workers: int = Field(..., description="Number of scaling workers")


class ConfigReloadResponse(BaseModel):
    success: bool = Field(..., description="Whether reload was successful")
    message: str = Field(..., description="Status message")
    providers_loaded: int = Field(..., description="Number of providers loaded")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")


class SystemStatusResponse(BaseModel):
    system_name: str = Field(..., description="System name")
    version: str = Field(..., description="System version")
    status: str = Field(..., description="System status")
    uptime: str = Field(..., description="System uptime")
    components: Dict[str, str] = Field(..., description="Component statuses")


# Global system start time for uptime calculation
system_start_time = datetime.now()


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health():
    """Get comprehensive system health status."""
    try:
        components = {}
        overall_status = "healthy"
        
        # Check YAML configuration system
        try:
            from backend.util.yaml_config_loader import get_yaml_config_loader
            yaml_loader = await get_yaml_config_loader()
            components["yaml_config"] = {
                "status": "healthy",
                "providers_count": len(yaml_loader.providers),
                "last_reload": yaml_loader.last_reload.isoformat() if yaml_loader.last_reload else None
            }
        except Exception as e:
            components["yaml_config"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            overall_status = "degraded"
        
        # Check session management system
        try:
            from backend.util.session_manager import get_session_manager
            session_manager = await get_session_manager()
            components["session_manager"] = {
                "status": "healthy",
                "active_sessions": len(session_manager.sessions),
                "storage_path": str(session_manager.storage_path)
            }
        except Exception as e:
            components["session_manager"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            overall_status = "degraded"
        
        # Check FlareProx auto-scaling system
        try:
            from backend.util.flareprox_autoscaler import get_flareprox_autoscaler
            autoscaler = get_flareprox_autoscaler()
            if autoscaler:
                components["flareprox_autoscaler"] = {
                    "status": "healthy",
                    "active_workers": len(autoscaler.active_workers),
                    "min_workers": autoscaler.min_workers,
                    "max_workers": autoscaler.max_workers
                }
            else:
                components["flareprox_autoscaler"] = {
                    "status": "disabled",
                    "message": "FlareProx auto-scaling not configured"
                }
        except Exception as e:
            components["flareprox_autoscaler"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            overall_status = "degraded"
        
        # Check provider management system
        try:
            from backend.server.routers.provider_management import scaling_engine
            if scaling_engine:
                components["provider_management"] = {
                    "status": "healthy",
                    "scaling_engine": "active"
                }
            else:
                components["provider_management"] = {
                    "status": "disabled",
                    "message": "Provider management not initialized"
                }
        except Exception as e:
            components["provider_management"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            overall_status = "degraded"
        
        uptime = (datetime.now() - system_start_time).total_seconds()
        
        return SystemHealthResponse(
            status=overall_status,
            timestamp=datetime.now(),
            components=components,
            uptime_seconds=uptime,
            version="1.0.0"
        )
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics():
    """Get current system metrics."""
    try:
        # Initialize default metrics
        metrics = {
            "requests_per_minute": 0.0,
            "requests_per_hour": 0.0,
            "average_response_time": 0.0,
            "error_rate": 0.0,
            "active_sessions": 0,
            "active_providers": 0,
            "scaling_workers": 0
        }
        
        # Get FlareProx metrics
        try:
            from backend.util.flareprox_autoscaler import get_flareprox_autoscaler
            autoscaler = get_flareprox_autoscaler()
            if autoscaler:
                scaling_metrics = autoscaler.volume_monitor.get_scaling_metrics()
                metrics.update({
                    "requests_per_minute": scaling_metrics.requests_per_minute,
                    "requests_per_hour": scaling_metrics.requests_per_hour,
                    "average_response_time": scaling_metrics.average_response_time,
                    "error_rate": scaling_metrics.error_rate * 100,  # Convert to percentage
                    "scaling_workers": len(autoscaler.active_workers)
                })
        except Exception as e:
            logger.warning(f"Could not get FlareProx metrics: {e}")
        
        # Get session metrics
        try:
            from backend.util.session_manager import get_session_manager
            session_manager = await get_session_manager()
            metrics["active_sessions"] = len(session_manager.sessions)
        except Exception as e:
            logger.warning(f"Could not get session metrics: {e}")
        
        # Get provider metrics
        try:
            from backend.util.yaml_config_loader import get_yaml_config_loader
            yaml_loader = await get_yaml_config_loader()
            metrics["active_providers"] = len(yaml_loader.providers)
        except Exception as e:
            logger.warning(f"Could not get provider metrics: {e}")
        
        return SystemMetricsResponse(
            timestamp=datetime.now(),
            **metrics
        )
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Metrics collection failed: {str(e)}")


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """Get basic system status information."""
    try:
        uptime_seconds = (datetime.now() - system_start_time).total_seconds()
        uptime_str = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m {int(uptime_seconds % 60)}s"
        
        # Check component statuses
        components = {}
        
        # YAML Config
        try:
            from backend.util.yaml_config_loader import get_yaml_config_loader
            await get_yaml_config_loader()
            components["yaml_config"] = "healthy"
        except:
            components["yaml_config"] = "unhealthy"
        
        # Session Manager
        try:
            from backend.util.session_manager import get_session_manager
            await get_session_manager()
            components["session_manager"] = "healthy"
        except:
            components["session_manager"] = "unhealthy"
        
        # FlareProx AutoScaler
        try:
            from backend.util.flareprox_autoscaler import get_flareprox_autoscaler
            autoscaler = get_flareprox_autoscaler()
            components["flareprox_autoscaler"] = "healthy" if autoscaler else "disabled"
        except:
            components["flareprox_autoscaler"] = "unhealthy"
        
        return SystemStatusResponse(
            system_name="Enhanced Chat Proxy System",
            version="1.0.0",
            status="operational",
            uptime=uptime_str,
            components=components
        )
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.post("/config/reload", response_model=ConfigReloadResponse)
async def reload_configuration():
    """Reload YAML configuration from disk."""
    try:
        from backend.util.yaml_config_loader import get_yaml_config_loader
        yaml_loader = await get_yaml_config_loader()
        
        # Reload configuration
        await yaml_loader.reload_config()
        
        return ConfigReloadResponse(
            success=True,
            message="Configuration reloaded successfully",
            providers_loaded=len(yaml_loader.providers),
            errors=[]
        )
        
    except Exception as e:
        logger.error(f"Error reloading configuration: {e}")
        return ConfigReloadResponse(
            success=False,
            message=f"Configuration reload failed: {str(e)}",
            providers_loaded=0,
            errors=[str(e)]
        )


@router.get("/config/providers")
async def list_yaml_providers():
    """List all YAML configuration providers."""
    try:
        from backend.util.yaml_config_loader import get_yaml_config_loader
        yaml_loader = await get_yaml_config_loader()
        
        providers = []
        for provider_id, provider in yaml_loader.providers.items():
            providers.append({
                "id": provider_id,
                "name": provider.name,
                "url": provider.url,
                "username": provider.username,
                "models": provider.models,
                "is_default": provider.is_default,
                "timeout": provider.timeout,
                "max_retries": provider.max_retries
            })
        
        return {
            "providers": providers,
            "total_count": len(providers),
            "last_reload": yaml_loader.last_reload.isoformat() if yaml_loader.last_reload else None
        }
        
    except Exception as e:
        logger.error(f"Error listing YAML providers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list providers: {str(e)}")


@router.post("/config/validate")
async def validate_configuration():
    """Validate current YAML configuration."""
    try:
        from backend.util.yaml_config_loader import get_yaml_config_loader
        yaml_loader = await get_yaml_config_loader()
        
        validation_results = []
        
        for provider_id, provider in yaml_loader.providers.items():
            result = {
                "provider_id": provider_id,
                "name": provider.name,
                "valid": True,
                "issues": []
            }
            
            # Basic validation
            if not provider.url:
                result["valid"] = False
                result["issues"].append("Missing URL")
            
            if not provider.username:
                result["valid"] = False
                result["issues"].append("Missing username")
            
            if not provider.models:
                result["valid"] = False
                result["issues"].append("No models configured")
            
            if provider.timeout <= 0:
                result["valid"] = False
                result["issues"].append("Invalid timeout value")
            
            validation_results.append(result)
        
        all_valid = all(result["valid"] for result in validation_results)
        
        return {
            "valid": all_valid,
            "providers": validation_results,
            "summary": {
                "total_providers": len(validation_results),
                "valid_providers": sum(1 for r in validation_results if r["valid"]),
                "invalid_providers": sum(1 for r in validation_results if not r["valid"])
            }
        }
        
    except Exception as e:
        logger.error(f"Error validating configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration validation failed: {str(e)}")


@router.get("/sessions")
async def list_active_sessions():
    """List all active sessions."""
    try:
        from backend.util.session_manager import get_session_manager
        session_manager = await get_session_manager()
        
        sessions = session_manager.list_sessions()
        
        return {
            "sessions": sessions,
            "total_count": len(sessions),
            "valid_sessions": sum(1 for s in sessions if s["is_valid"]),
            "invalid_sessions": sum(1 for s in sessions if not s["is_valid"])
        }
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.delete("/sessions/{provider_id}/{username}")
async def remove_session(provider_id: str, username: str):
    """Remove a specific session."""
    try:
        from backend.util.session_manager import get_session_manager
        session_manager = await get_session_manager()
        
        await session_manager.remove_session(provider_id, username)
        
        return {
            "success": True,
            "message": f"Session for {provider_id}/{username} removed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error removing session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove session: {str(e)}")


@router.delete("/sessions/invalid")
async def cleanup_invalid_sessions():
    """Remove all invalid sessions."""
    try:
        from backend.util.session_manager import get_session_manager
        session_manager = await get_session_manager()
        
        removed_count = 0
        sessions_to_remove = []
        
        for session in session_manager.sessions.values():
            if not session.is_valid:
                sessions_to_remove.append((session.provider_id, session.username))
        
        for provider_id, username in sessions_to_remove:
            await session_manager.remove_session(provider_id, username)
            removed_count += 1
        
        return {
            "success": True,
            "message": f"Removed {removed_count} invalid sessions",
            "removed_count": removed_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up invalid sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup sessions: {str(e)}")


@router.get("/scaling/status")
async def get_scaling_status():
    """Get auto-scaling system status."""
    try:
        from backend.util.flareprox_autoscaler import get_flareprox_autoscaler
        autoscaler = get_flareprox_autoscaler()
        
        if not autoscaler:
            return {
                "enabled": False,
                "message": "FlareProx auto-scaling not configured"
            }
        
        status = autoscaler.get_scaling_status()
        status["enabled"] = True
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting scaling status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scaling status: {str(e)}")


@router.get("/scaling/metrics")
async def get_scaling_metrics():
    """Get detailed scaling metrics."""
    try:
        from backend.util.flareprox_autoscaler import get_flareprox_autoscaler
        autoscaler = get_flareprox_autoscaler()
        
        if not autoscaler:
            return {
                "enabled": False,
                "message": "FlareProx auto-scaling not configured"
            }
        
        metrics = autoscaler.volume_monitor.get_scaling_metrics()
        
        return {
            "enabled": True,
            "timestamp": datetime.now().isoformat(),
            "requests_per_minute": metrics.requests_per_minute,
            "requests_per_hour": metrics.requests_per_hour,
            "average_response_time": metrics.average_response_time,
            "error_rate": metrics.error_rate,
            "active_workers": len(autoscaler.active_workers),
            "utilization_percentage": autoscaler._calculate_utilization()
        }
        
    except Exception as e:
        logger.error(f"Error getting scaling metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scaling metrics: {str(e)}")


@router.post("/scaling/manual-scale")
async def manual_scale_workers(target_workers: int = Field(..., ge=1, le=50)):
    """Manually scale the number of workers."""
    try:
        from backend.util.flareprox_autoscaler import get_flareprox_autoscaler
        autoscaler = get_flareprox_autoscaler()
        
        if not autoscaler:
            raise HTTPException(status_code=503, detail="FlareProx auto-scaling not configured")
        
        current_workers = len(autoscaler.active_workers)
        
        if target_workers > current_workers:
            # Scale up
            for _ in range(target_workers - current_workers):
                await autoscaler._create_worker()
        elif target_workers < current_workers:
            # Scale down
            workers_to_remove = list(autoscaler.active_workers.keys())[:current_workers - target_workers]
            for worker_id in workers_to_remove:
                await autoscaler._remove_worker(worker_id)
        
        return {
            "success": True,
            "message": f"Scaled from {current_workers} to {len(autoscaler.active_workers)} workers",
            "previous_workers": current_workers,
            "current_workers": len(autoscaler.active_workers)
        }
        
    except Exception as e:
        logger.error(f"Error manually scaling workers: {e}")
        raise HTTPException(status_code=500, detail=f"Manual scaling failed: {str(e)}")


@router.post("/maintenance/restart-component")
async def restart_component(component: str, background_tasks: BackgroundTasks):
    """Restart a specific system component."""
    try:
        if component == "yaml_config":
            background_tasks.add_task(_restart_yaml_config)
        elif component == "session_manager":
            background_tasks.add_task(_restart_session_manager)
        elif component == "flareprox_autoscaler":
            background_tasks.add_task(_restart_flareprox_autoscaler)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown component: {component}")
        
        return {
            "success": True,
            "message": f"Component '{component}' restart initiated",
            "component": component
        }
        
    except Exception as e:
        logger.error(f"Error restarting component {component}: {e}")
        raise HTTPException(status_code=500, detail=f"Component restart failed: {str(e)}")


# Background task functions
async def _restart_yaml_config():
    """Restart YAML configuration system."""
    try:
        from backend.util.yaml_config_loader import shutdown_yaml_config, initialize_yaml_config
        await shutdown_yaml_config()
        await asyncio.sleep(1)
        await initialize_yaml_config()
        logger.info("YAML configuration system restarted")
    except Exception as e:
        logger.error(f"Failed to restart YAML configuration: {e}")


async def _restart_session_manager():
    """Restart session management system."""
    try:
        from backend.util.session_manager import shutdown_session_manager, initialize_session_manager
        await shutdown_session_manager()
        await asyncio.sleep(1)
        await initialize_session_manager()
        logger.info("Session management system restarted")
    except Exception as e:
        logger.error(f"Failed to restart session manager: {e}")


async def _restart_flareprox_autoscaler():
    """Restart FlareProx auto-scaling system."""
    try:
        from backend.util.flareprox_autoscaler import shutdown_flareprox_autoscaler, initialize_flareprox_autoscaler
        await shutdown_flareprox_autoscaler()
        await asyncio.sleep(1)
        await initialize_flareprox_autoscaler()
        logger.info("FlareProx auto-scaling system restarted")
    except Exception as e:
        logger.error(f"Failed to restart FlareProx auto-scaling: {e}")
