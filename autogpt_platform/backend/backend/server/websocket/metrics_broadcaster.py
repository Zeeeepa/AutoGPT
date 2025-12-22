"""
Metrics Broadcaster for WebSocket Monitoring.

Automatically collects and broadcasts system metrics, health status, and events
to connected WebSocket clients at regular intervals.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MetricsBroadcaster:
    """Automatically broadcasts system metrics and events."""
    
    def __init__(self, broadcast_interval: int = 5):
        self.broadcast_interval = broadcast_interval  # seconds
        self.is_running = False
        
        # Background tasks
        self._metrics_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None
        self._events_task: Optional[asyncio.Task] = None
        
        # Last known values for change detection
        self._last_metrics: Dict[str, Any] = {}
        self._last_health: Dict[str, Any] = {}
        self._last_session_count = 0
        self._last_worker_count = 0
    
    async def start(self):
        """Start the metrics broadcaster."""
        if self.is_running:
            return
        
        logger.info("Starting metrics broadcaster")
        self.is_running = True
        
        # Start background tasks
        self._metrics_task = asyncio.create_task(self._metrics_broadcast_loop())
        self._health_task = asyncio.create_task(self._health_broadcast_loop())
        self._events_task = asyncio.create_task(self._events_monitor_loop())
        
        logger.info(f"Metrics broadcaster started with {self.broadcast_interval}s interval")
    
    async def stop(self):
        """Stop the metrics broadcaster."""
        if not self.is_running:
            return
        
        logger.info("Stopping metrics broadcaster")
        self.is_running = False
        
        # Cancel background tasks
        for task in [self._metrics_task, self._health_task, self._events_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info("Metrics broadcaster stopped")
    
    async def _metrics_broadcast_loop(self):
        """Broadcast metrics at regular intervals."""
        while self.is_running:
            try:
                await asyncio.sleep(self.broadcast_interval)
                
                # Collect current metrics
                metrics = await self._collect_system_metrics()
                
                # Check if metrics have changed significantly
                if self._metrics_changed(metrics):
                    # Broadcast metrics update
                    from backend.server.websocket.monitoring import broadcast_metrics_update
                    await broadcast_metrics_update(metrics)
                    self._last_metrics = metrics.copy()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics broadcast loop: {e}")
                await asyncio.sleep(self.broadcast_interval)
    
    async def _health_broadcast_loop(self):
        """Broadcast health status at regular intervals."""
        while self.is_running:
            try:
                await asyncio.sleep(self.broadcast_interval * 2)  # Less frequent than metrics
                
                # Collect current health status
                health = await self._collect_system_health()
                
                # Check if health status has changed
                if self._health_changed(health):
                    # Broadcast health update
                    from backend.server.websocket.monitoring import broadcast_health_update
                    await broadcast_health_update(health)
                    self._last_health = health.copy()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health broadcast loop: {e}")
                await asyncio.sleep(self.broadcast_interval * 2)
    
    async def _events_monitor_loop(self):
        """Monitor for significant system events and broadcast them."""
        while self.is_running:
            try:
                await asyncio.sleep(self.broadcast_interval)
                
                # Check for session changes
                await self._check_session_changes()
                
                # Check for scaling events
                await self._check_scaling_changes()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in events monitor loop: {e}")
                await asyncio.sleep(self.broadcast_interval)
    
    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics."""
        metrics = {
            "requests_per_minute": 0.0,
            "requests_per_hour": 0.0,
            "average_response_time": 0.0,
            "error_rate": 0.0,
            "active_sessions": 0,
            "active_providers": 0,
            "scaling_workers": 0,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Get FlareProx metrics
            from backend.util.flareprox_autoscaler import get_flareprox_autoscaler
            autoscaler = get_flareprox_autoscaler()
            if autoscaler:
                scaling_metrics = autoscaler.volume_monitor.get_scaling_metrics()
                metrics.update({
                    "requests_per_minute": scaling_metrics.requests_per_minute,
                    "requests_per_hour": scaling_metrics.requests_per_hour,
                    "average_response_time": scaling_metrics.average_response_time,
                    "error_rate": scaling_metrics.error_rate * 100,
                    "scaling_workers": len(autoscaler.active_workers)
                })
        except Exception as e:
            logger.debug(f"Could not get FlareProx metrics: {e}")
        
        try:
            # Get session metrics
            from backend.util.session_manager import get_session_manager
            session_manager = await get_session_manager()
            metrics["active_sessions"] = len(session_manager.sessions)
        except Exception as e:
            logger.debug(f"Could not get session metrics: {e}")
        
        try:
            # Get provider metrics
            from backend.util.yaml_config_loader import get_yaml_config_loader
            yaml_loader = await get_yaml_config_loader()
            metrics["active_providers"] = len(yaml_loader.providers)
        except Exception as e:
            logger.debug(f"Could not get provider metrics: {e}")
        
        return metrics
    
    async def _collect_system_health(self) -> Dict[str, Any]:
        """Collect current system health status."""
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        overall_status = "healthy"
        
        try:
            # Check YAML configuration system
            from backend.util.yaml_config_loader import get_yaml_config_loader
            yaml_loader = await get_yaml_config_loader()
            health["components"]["yaml_config"] = {
                "status": "healthy",
                "providers_count": len(yaml_loader.providers)
            }
        except Exception as e:
            health["components"]["yaml_config"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            overall_status = "degraded"
        
        try:
            # Check session management system
            from backend.util.session_manager import get_session_manager
            session_manager = await get_session_manager()
            health["components"]["session_manager"] = {
                "status": "healthy",
                "active_sessions": len(session_manager.sessions)
            }
        except Exception as e:
            health["components"]["session_manager"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            overall_status = "degraded"
        
        try:
            # Check FlareProx auto-scaling system
            from backend.util.flareprox_autoscaler import get_flareprox_autoscaler
            autoscaler = get_flareprox_autoscaler()
            if autoscaler:
                health["components"]["flareprox_autoscaler"] = {
                    "status": "healthy",
                    "active_workers": len(autoscaler.active_workers)
                }
            else:
                health["components"]["flareprox_autoscaler"] = {
                    "status": "disabled",
                    "message": "FlareProx auto-scaling not configured"
                }
        except Exception as e:
            health["components"]["flareprox_autoscaler"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            overall_status = "degraded"
        
        health["status"] = overall_status
        return health
    
    async def _check_session_changes(self):
        """Check for session-related changes and broadcast events."""
        try:
            from backend.util.session_manager import get_session_manager
            session_manager = await get_session_manager()
            current_session_count = len(session_manager.sessions)
            
            if current_session_count != self._last_session_count:
                # Session count changed
                event_data = {
                    "event": "session_count_changed",
                    "previous_count": self._last_session_count,
                    "current_count": current_session_count,
                    "change": current_session_count - self._last_session_count
                }
                
                from backend.server.websocket.monitoring import broadcast_session_update
                await broadcast_session_update(event_data)
                
                self._last_session_count = current_session_count
                logger.info(f"Session count changed: {self._last_session_count} -> {current_session_count}")
        
        except Exception as e:
            logger.debug(f"Error checking session changes: {e}")
    
    async def _check_scaling_changes(self):
        """Check for scaling-related changes and broadcast events."""
        try:
            from backend.util.flareprox_autoscaler import get_flareprox_autoscaler
            autoscaler = get_flareprox_autoscaler()
            
            if autoscaler:
                current_worker_count = len(autoscaler.active_workers)
                
                if current_worker_count != self._last_worker_count:
                    # Worker count changed
                    event_data = {
                        "event": "worker_count_changed",
                        "previous_count": self._last_worker_count,
                        "current_count": current_worker_count,
                        "change": current_worker_count - self._last_worker_count,
                        "scaling_direction": "up" if current_worker_count > self._last_worker_count else "down"
                    }
                    
                    from backend.server.websocket.monitoring import broadcast_scaling_event
                    await broadcast_scaling_event(event_data)
                    
                    self._last_worker_count = current_worker_count
                    logger.info(f"Worker count changed: {self._last_worker_count} -> {current_worker_count}")
        
        except Exception as e:
            logger.debug(f"Error checking scaling changes: {e}")
    
    def _metrics_changed(self, new_metrics: Dict[str, Any]) -> bool:
        """Check if metrics have changed significantly."""
        if not self._last_metrics:
            return True
        
        # Check for significant changes in key metrics
        significant_changes = [
            "requests_per_minute",
            "average_response_time",
            "error_rate",
            "active_sessions",
            "active_providers",
            "scaling_workers"
        ]
        
        for key in significant_changes:
            old_value = self._last_metrics.get(key, 0)
            new_value = new_metrics.get(key, 0)
            
            # Check for any change in counts
            if key in ["active_sessions", "active_providers", "scaling_workers"]:
                if old_value != new_value:
                    return True
            
            # Check for significant percentage changes in rates
            elif key in ["requests_per_minute", "average_response_time", "error_rate"]:
                if old_value == 0 and new_value > 0:
                    return True
                elif old_value > 0:
                    change_percent = abs((new_value - old_value) / old_value)
                    if change_percent > 0.1:  # 10% change threshold
                        return True
        
        return False
    
    def _health_changed(self, new_health: Dict[str, Any]) -> bool:
        """Check if health status has changed."""
        if not self._last_health:
            return True
        
        # Check overall status change
        if self._last_health.get("status") != new_health.get("status"):
            return True
        
        # Check component status changes
        old_components = self._last_health.get("components", {})
        new_components = new_health.get("components", {})
        
        for component_name, component_status in new_components.items():
            old_status = old_components.get(component_name, {}).get("status")
            new_status = component_status.get("status")
            
            if old_status != new_status:
                return True
        
        return False


# Global broadcaster instance
metrics_broadcaster: Optional[MetricsBroadcaster] = None


async def initialize_metrics_broadcaster(broadcast_interval: int = 5) -> MetricsBroadcaster:
    """Initialize the metrics broadcaster."""
    global metrics_broadcaster
    
    if metrics_broadcaster is None:
        metrics_broadcaster = MetricsBroadcaster(broadcast_interval)
        await metrics_broadcaster.start()
        logger.info("Metrics broadcaster initialized")
    
    return metrics_broadcaster


async def shutdown_metrics_broadcaster():
    """Shutdown the metrics broadcaster."""
    global metrics_broadcaster
    
    if metrics_broadcaster:
        await metrics_broadcaster.stop()
        metrics_broadcaster = None
        logger.info("Metrics broadcaster shutdown")


def get_metrics_broadcaster() -> Optional[MetricsBroadcaster]:
    """Get the global metrics broadcaster."""
    return metrics_broadcaster
