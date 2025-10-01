"""
FlareProx Auto-Scaling Integration with Request Volume Monitoring.

This module provides auto-scaling functionality for FlareProx workers based on
request volume and performance metrics.
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, field
import json

# Import FlareProx components
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from flareprox import CloudflareManager, FlareProxError

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for request volume tracking."""
    timestamp: datetime
    endpoint: str
    provider_id: str
    response_time: float
    success: bool
    user_ip: Optional[str] = None


@dataclass
class ScalingMetrics:
    """Metrics for scaling decisions."""
    requests_per_minute: float = 0.0
    requests_per_hour: float = 0.0
    average_response_time: float = 0.0
    error_rate: float = 0.0
    active_workers: int = 0
    total_capacity: int = 0
    utilization_percentage: float = 0.0


@dataclass
class WorkerInstance:
    """Represents a Cloudflare Worker instance."""
    worker_id: str
    worker_name: str
    worker_url: str
    created_at: datetime
    last_used: datetime
    request_count: int = 0
    error_count: int = 0
    is_active: bool = True


class RequestVolumeMonitor:
    """Monitors request volume and provides scaling metrics."""
    
    def __init__(self, window_size_minutes: int = 60):
        self.window_size_minutes = window_size_minutes
        self.request_history: deque = deque(maxlen=10000)  # Keep last 10k requests
        self.metrics_cache: Optional[ScalingMetrics] = None
        self.cache_expiry: Optional[datetime] = None
        self.cache_duration_seconds = 30  # Cache metrics for 30 seconds
    
    def record_request(self, 
                      endpoint: str, 
                      provider_id: str, 
                      response_time: float, 
                      success: bool,
                      user_ip: Optional[str] = None):
        """Record a request for volume monitoring."""
        metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint=endpoint,
            provider_id=provider_id,
            response_time=response_time,
            success=success,
            user_ip=user_ip
        )
        self.request_history.append(metrics)
        
        # Invalidate cache
        self.metrics_cache = None
    
    def get_scaling_metrics(self) -> ScalingMetrics:
        """Get current scaling metrics."""
        now = datetime.now()
        
        # Return cached metrics if still valid
        if (self.metrics_cache and self.cache_expiry and 
            now < self.cache_expiry):
            return self.metrics_cache
        
        # Calculate new metrics
        one_minute_ago = now - timedelta(minutes=1)
        one_hour_ago = now - timedelta(hours=1)
        
        # Filter requests by time windows
        recent_requests = [r for r in self.request_history if r.timestamp >= one_minute_ago]
        hourly_requests = [r for r in self.request_history if r.timestamp >= one_hour_ago]
        
        # Calculate metrics
        requests_per_minute = len(recent_requests)
        requests_per_hour = len(hourly_requests)
        
        # Average response time
        if recent_requests:
            avg_response_time = sum(r.response_time for r in recent_requests) / len(recent_requests)
        else:
            avg_response_time = 0.0
        
        # Error rate
        if recent_requests:
            error_count = sum(1 for r in recent_requests if not r.success)
            error_rate = error_count / len(recent_requests)
        else:
            error_rate = 0.0
        
        # Create metrics object
        metrics = ScalingMetrics(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            average_response_time=avg_response_time,
            error_rate=error_rate
        )
        
        # Cache the metrics
        self.metrics_cache = metrics
        self.cache_expiry = now + timedelta(seconds=self.cache_duration_seconds)
        
        return metrics
    
    def get_provider_metrics(self, provider_id: str) -> Dict[str, Any]:
        """Get metrics for a specific provider."""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        provider_requests = [
            r for r in self.request_history 
            if r.provider_id == provider_id and r.timestamp >= one_hour_ago
        ]
        
        if not provider_requests:
            return {
                "requests_per_hour": 0,
                "average_response_time": 0.0,
                "error_rate": 0.0,
                "last_request": None
            }
        
        return {
            "requests_per_hour": len(provider_requests),
            "average_response_time": sum(r.response_time for r in provider_requests) / len(provider_requests),
            "error_rate": sum(1 for r in provider_requests if not r.success) / len(provider_requests),
            "last_request": max(r.timestamp for r in provider_requests).isoformat()
        }


class FlareProxAutoScaler:
    """Auto-scaling manager for FlareProx workers based on request volume."""
    
    def __init__(self, 
                 cloudflare_api_token: str,
                 cloudflare_account_id: str,
                 cloudflare_zone_id: Optional[str] = None):
        self.cloudflare_manager = CloudflareManager(
            api_token=cloudflare_api_token,
            account_id=cloudflare_account_id,
            zone_id=cloudflare_zone_id
        )
        
        # Scaling configuration
        self.min_workers = 1
        self.max_workers = 50  # Reasonable limit
        self.scale_up_threshold_rpm = 100  # Scale up if > 100 requests/minute
        self.scale_down_threshold_rpm = 20  # Scale down if < 20 requests/minute
        self.scale_up_response_time_threshold = 5.0  # Scale up if avg response time > 5s
        self.scale_down_idle_minutes = 10  # Scale down workers idle for 10+ minutes
        
        # Worker management
        self.active_workers: Dict[str, WorkerInstance] = {}
        self.worker_rotation_index = 0
        
        # Monitoring
        self.volume_monitor = RequestVolumeMonitor()
        self.last_scaling_action = datetime.now()
        self.scaling_cooldown_minutes = 2  # Wait 2 minutes between scaling actions
        
        # Background tasks
        self._scaling_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the auto-scaler."""
        logger.info("Starting FlareProx auto-scaler")
        
        # Ensure we have at least minimum workers
        await self._ensure_minimum_workers()
        
        # Start background tasks
        self._scaling_task = asyncio.create_task(self._scaling_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"FlareProx auto-scaler started with {len(self.active_workers)} workers")
    
    async def stop(self):
        """Stop the auto-scaler."""
        logger.info("Stopping FlareProx auto-scaler")
        
        # Cancel background tasks
        if self._scaling_task:
            self._scaling_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        logger.info("FlareProx auto-scaler stopped")
    
    def record_request(self, 
                      endpoint: str, 
                      provider_id: str, 
                      response_time: float, 
                      success: bool,
                      user_ip: Optional[str] = None):
        """Record a request for volume monitoring."""
        self.volume_monitor.record_request(endpoint, provider_id, response_time, success, user_ip)
        
        # Update worker usage if we can identify which worker handled it
        if self.active_workers:
            latest_worker = max(self.active_workers.values(), key=lambda w: w.last_used)
            latest_worker.request_count += 1
            latest_worker.last_used = datetime.now()
            if not success:
                latest_worker.error_count += 1
    
    def get_next_worker_url(self) -> Optional[str]:
        """Get the next worker URL for load balancing."""
        if not self.active_workers:
            return None
        
        # Simple round-robin load balancing
        worker_list = list(self.active_workers.values())
        if not worker_list:
            return None
        
        worker = worker_list[self.worker_rotation_index % len(worker_list)]
        self.worker_rotation_index += 1
        
        # Update last used time
        worker.last_used = datetime.now()
        
        return worker.worker_url
    
    def get_scaling_status(self) -> Dict[str, Any]:
        """Get current scaling status and metrics."""
        metrics = self.volume_monitor.get_scaling_metrics()
        
        return {
            "active_workers": len(self.active_workers),
            "min_workers": self.min_workers,
            "max_workers": self.max_workers,
            "metrics": {
                "requests_per_minute": metrics.requests_per_minute,
                "requests_per_hour": metrics.requests_per_hour,
                "average_response_time": metrics.average_response_time,
                "error_rate": metrics.error_rate,
                "utilization_percentage": self._calculate_utilization()
            },
            "workers": [
                {
                    "worker_id": worker.worker_id,
                    "worker_name": worker.worker_name,
                    "worker_url": worker.worker_url,
                    "created_at": worker.created_at.isoformat(),
                    "last_used": worker.last_used.isoformat(),
                    "request_count": worker.request_count,
                    "error_count": worker.error_count,
                    "is_active": worker.is_active
                }
                for worker in self.active_workers.values()
            ],
            "scaling_thresholds": {
                "scale_up_rpm": self.scale_up_threshold_rpm,
                "scale_down_rpm": self.scale_down_threshold_rpm,
                "scale_up_response_time": self.scale_up_response_time_threshold,
                "scale_down_idle_minutes": self.scale_down_idle_minutes
            }
        }
    
    async def _scaling_loop(self):
        """Main scaling loop that runs in the background."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._evaluate_scaling()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scaling loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _cleanup_loop(self):
        """Cleanup loop for removing idle workers."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self._cleanup_idle_workers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _evaluate_scaling(self):
        """Evaluate whether scaling is needed."""
        now = datetime.now()
        
        # Check cooldown period
        if (now - self.last_scaling_action).total_seconds() < self.scaling_cooldown_minutes * 60:
            return
        
        metrics = self.volume_monitor.get_scaling_metrics()
        current_workers = len(self.active_workers)
        
        # Determine if we need to scale up
        should_scale_up = (
            (metrics.requests_per_minute > self.scale_up_threshold_rpm) or
            (metrics.average_response_time > self.scale_up_response_time_threshold and 
             metrics.requests_per_minute > 10)  # Only scale up for response time if we have traffic
        )
        
        # Determine if we can scale down
        should_scale_down = (
            metrics.requests_per_minute < self.scale_down_threshold_rpm and
            current_workers > self.min_workers
        )
        
        if should_scale_up and current_workers < self.max_workers:
            await self._scale_up()
        elif should_scale_down:
            await self._scale_down()
    
    async def _scale_up(self):
        """Scale up by adding a new worker."""
        try:
            logger.info("Scaling up: Adding new FlareProx worker")
            
            # Create new worker
            worker_data = await self._create_worker()
            if worker_data:
                self.last_scaling_action = datetime.now()
                logger.info(f"Successfully scaled up to {len(self.active_workers)} workers")
            
        except Exception as e:
            logger.error(f"Failed to scale up: {e}")
    
    async def _scale_down(self):
        """Scale down by removing the least used worker."""
        try:
            if len(self.active_workers) <= self.min_workers:
                return
            
            # Find the least used worker
            least_used_worker = min(
                self.active_workers.values(),
                key=lambda w: w.last_used
            )
            
            # Check if it's been idle long enough
            idle_time = datetime.now() - least_used_worker.last_used
            if idle_time.total_seconds() < self.scale_down_idle_minutes * 60:
                return
            
            logger.info(f"Scaling down: Removing worker {least_used_worker.worker_name}")
            
            # Remove the worker
            await self._remove_worker(least_used_worker.worker_id)
            self.last_scaling_action = datetime.now()
            
            logger.info(f"Successfully scaled down to {len(self.active_workers)} workers")
            
        except Exception as e:
            logger.error(f"Failed to scale down: {e}")
    
    async def _ensure_minimum_workers(self):
        """Ensure we have at least the minimum number of workers."""
        current_count = len(self.active_workers)
        needed = self.min_workers - current_count
        
        if needed > 0:
            logger.info(f"Creating {needed} workers to meet minimum requirement")
            for _ in range(needed):
                try:
                    await self._create_worker()
                except Exception as e:
                    logger.error(f"Failed to create minimum worker: {e}")
    
    async def _create_worker(self) -> Optional[WorkerInstance]:
        """Create a new Cloudflare Worker."""
        try:
            # Generate unique worker name
            timestamp = int(time.time())
            worker_name = f"flareprox-autoscale-{timestamp}"
            
            # Create worker using CloudflareManager
            worker_url = await asyncio.get_event_loop().run_in_executor(
                None, 
                self.cloudflare_manager.create_worker,
                worker_name
            )
            
            if not worker_url:
                raise FlareProxError("Failed to create worker - no URL returned")
            
            # Create worker instance
            worker = WorkerInstance(
                worker_id=worker_name,
                worker_name=worker_name,
                worker_url=worker_url,
                created_at=datetime.now(),
                last_used=datetime.now()
            )
            
            self.active_workers[worker_name] = worker
            logger.info(f"Created new worker: {worker_name} at {worker_url}")
            
            return worker
            
        except Exception as e:
            logger.error(f"Failed to create worker: {e}")
            return None
    
    async def _remove_worker(self, worker_id: str):
        """Remove a Cloudflare Worker."""
        try:
            if worker_id not in self.active_workers:
                return
            
            worker = self.active_workers[worker_id]
            
            # Delete worker using CloudflareManager
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.cloudflare_manager.delete_worker,
                worker.worker_name
            )
            
            # Remove from active workers
            del self.active_workers[worker_id]
            logger.info(f"Removed worker: {worker.worker_name}")
            
        except Exception as e:
            logger.error(f"Failed to remove worker {worker_id}: {e}")
    
    async def _cleanup_idle_workers(self):
        """Remove workers that have been idle for too long."""
        now = datetime.now()
        idle_threshold = timedelta(minutes=self.scale_down_idle_minutes * 2)  # Double the threshold for cleanup
        
        workers_to_remove = []
        for worker_id, worker in self.active_workers.items():
            if (now - worker.last_used) > idle_threshold and len(self.active_workers) > self.min_workers:
                workers_to_remove.append(worker_id)
        
        for worker_id in workers_to_remove:
            await self._remove_worker(worker_id)
    
    def _calculate_utilization(self) -> float:
        """Calculate current utilization percentage."""
        if not self.active_workers:
            return 0.0
        
        metrics = self.volume_monitor.get_scaling_metrics()
        
        # Estimate capacity (rough calculation)
        estimated_capacity_per_worker = 50  # requests per minute per worker
        total_capacity = len(self.active_workers) * estimated_capacity_per_worker
        
        if total_capacity == 0:
            return 0.0
        
        return min(100.0, (metrics.requests_per_minute / total_capacity) * 100)


# Global instance
flareprox_autoscaler: Optional[FlareProxAutoScaler] = None


async def initialize_flareprox_autoscaler() -> bool:
    """Initialize FlareProx auto-scaling system."""
    global flareprox_autoscaler
    
    try:
        # Get Cloudflare credentials from environment
        api_token = os.getenv("CLOUDFLARE_API_TOKEN")
        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        zone_id = os.getenv("CLOUDFLARE_ZONE_ID")  # Optional
        
        if not api_token or not account_id:
            logger.warning("Cloudflare credentials not found - FlareProx auto-scaling disabled")
            return False
        
        # Create and start auto-scaler
        flareprox_autoscaler = FlareProxAutoScaler(
            cloudflare_api_token=api_token,
            cloudflare_account_id=account_id,
            cloudflare_zone_id=zone_id
        )
        
        await flareprox_autoscaler.start()
        logger.info("FlareProx auto-scaling system initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize FlareProx auto-scaling: {e}")
        return False


async def shutdown_flareprox_autoscaler():
    """Shutdown FlareProx auto-scaling system."""
    global flareprox_autoscaler
    if flareprox_autoscaler:
        await flareprox_autoscaler.stop()
        flareprox_autoscaler = None


def get_flareprox_autoscaler() -> Optional[FlareProxAutoScaler]:
    """Get the global FlareProx auto-scaler instance."""
    return flareprox_autoscaler


def record_request_metrics(endpoint: str, 
                          provider_id: str, 
                          response_time: float, 
                          success: bool,
                          user_ip: Optional[str] = None):
    """Record request metrics for auto-scaling decisions."""
    if flareprox_autoscaler:
        flareprox_autoscaler.record_request(endpoint, provider_id, response_time, success, user_ip)


def get_next_proxy_url() -> Optional[str]:
    """Get the next proxy URL for load balancing."""
    if flareprox_autoscaler:
        return flareprox_autoscaler.get_next_worker_url()
    return None
