"""
Smart Scaling Engine with specific overflow-based scaling rules.

Scaling Logic:
- Browser Instance 1: Always running (5 providers)
- Browser Instance 2: Start when all 5 providers busy + overflow requests
- Browser Instance 3: Start when all 10 providers busy + overflow requests
- Auto-shutdown: After 30 minutes of inactivity (except Instance 1)
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from backend.data.chat_proxy_models import ChatServiceType
from backend.util.browser_instance_manager import BrowserInstanceManager, BrowserInstance


logger = logging.getLogger(__name__)


class ScalingEvent(Enum):
    """Types of scaling events."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    OVERFLOW_DETECTED = "overflow_detected"
    IDLE_TIMEOUT = "idle_timeout"


@dataclass
class ProviderStatus:
    """Status of a single provider."""
    service_type: ChatServiceType
    browser_instance_id: int
    is_busy: bool = False
    active_requests: int = 0
    last_request_time: Optional[datetime] = None
    total_requests: int = 0
    error_count: int = 0


@dataclass
class BrowserInstanceStatus:
    """Status of a browser instance."""
    instance_id: int
    is_active: bool = False
    provider_count: int = 0
    active_providers: Set[ChatServiceType] = field(default_factory=set)
    last_activity_time: Optional[datetime] = None
    startup_time: Optional[datetime] = None
    total_requests: int = 0
    idle_minutes: float = 0.0


@dataclass
class ScalingMetrics:
    """Current scaling metrics."""
    total_active_instances: int = 1
    total_active_providers: int = 5
    total_concurrent_requests: int = 0
    pending_requests: int = 0
    last_scaling_event: Optional[ScalingEvent] = None
    last_scaling_time: Optional[datetime] = None


class SmartScalingEngine:
    """
    Intelligent scaling engine that manages browser instances based on overflow.
    
    Rules:
    1. Instance 1: Always running with 5 providers
    2. Instance 2: Start when all 5 providers busy + overflow
    3. Instance 3: Start when all 10 providers busy + overflow
    4. Auto-shutdown: After 30 minutes of inactivity (except Instance 1)
    """
    
    def __init__(self, browser_manager: BrowserInstanceManager):
        self.browser_manager = browser_manager
        self.provider_status: Dict[ChatServiceType, ProviderStatus] = {}
        self.instance_status: Dict[int, BrowserInstanceStatus] = {}
        self.metrics = ScalingMetrics()
        
        # Scaling configuration
        self.IDLE_TIMEOUT_MINUTES = 30
        self.MAX_INSTANCES = 3
        self.PROVIDERS_PER_INSTANCE = 5
        self.SCALING_COOLDOWN_SECONDS = 60  # Prevent rapid scaling
        
        # Request queue for overflow handling
        self.pending_requests: List[dict] = []
        self.request_lock = asyncio.Lock()
        
        # Initialize Instance 1 (always active)
        self._initialize_instance_1()
        
        # Start background tasks
        self._scaling_task = None
        self._monitoring_task = None
        
    def _initialize_instance_1(self):
        """Initialize the first browser instance (always active)."""
        self.instance_status[1] = BrowserInstanceStatus(
            instance_id=1,
            is_active=True,
            provider_count=5,
            active_providers={
                ChatServiceType.K2THINK,
                ChatServiceType.QWEN,
                ChatServiceType.DEEPSEEK,
                ChatServiceType.GROK,
                ChatServiceType.ZAI
            },
            startup_time=datetime.now(),
            last_activity_time=datetime.now()
        )
        
        # Initialize provider status for Instance 1
        for service_type in self.instance_status[1].active_providers:
            self.provider_status[service_type] = ProviderStatus(
                service_type=service_type,
                browser_instance_id=1
            )
    
    async def start(self):
        """Start the scaling engine and background tasks."""
        logger.info("Starting Smart Scaling Engine...")
        
        # Start background monitoring
        self._scaling_task = asyncio.create_task(self._scaling_monitor())
        self._monitoring_task = asyncio.create_task(self._metrics_monitor())
        
        logger.info("Smart Scaling Engine started successfully")
    
    async def stop(self):
        """Stop the scaling engine and cleanup."""
        logger.info("Stopping Smart Scaling Engine...")
        
        if self._scaling_task:
            self._scaling_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()
        
        # Shutdown non-essential instances
        await self._shutdown_instance(2)
        await self._shutdown_instance(3)
        
        logger.info("Smart Scaling Engine stopped")
    
    async def handle_request(self, service_type: ChatServiceType, request_data: dict) -> dict:
        """
        Handle incoming request with smart scaling logic.
        
        Args:
            service_type: The requested service type
            request_data: Request payload
            
        Returns:
            Response from the provider
        """
        async with self.request_lock:
            # Check if requested provider is available
            if service_type in self.provider_status:
                provider = self.provider_status[service_type]
                
                # If provider is not busy, handle request immediately
                if not provider.is_busy:
                    return await self._execute_request(service_type, request_data)
            
            # All providers of this type are busy, check for overflow scaling
            await self._check_overflow_scaling()
            
            # Queue the request if no immediate capacity
            self.pending_requests.append({
                'service_type': service_type,
                'request_data': request_data,
                'timestamp': datetime.now()
            })
            
            # Wait for capacity or timeout
            return await self._wait_for_capacity(service_type, request_data)
    
    async def _execute_request(self, service_type: ChatServiceType, request_data: dict) -> dict:
        """Execute a request on the specified provider."""
        provider = self.provider_status[service_type]
        instance_id = provider.browser_instance_id
        
        # Mark provider as busy
        provider.is_busy = True
        provider.active_requests += 1
        provider.last_request_time = datetime.now()
        provider.total_requests += 1
        
        # Update instance activity
        if instance_id in self.instance_status:
            self.instance_status[instance_id].last_activity_time = datetime.now()
            self.instance_status[instance_id].total_requests += 1
        
        try:
            # Execute the actual request through browser manager
            response = await self.browser_manager.execute_request(
                instance_id, service_type, request_data
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Request failed for {service_type}: {e}")
            provider.error_count += 1
            raise
            
        finally:
            # Mark provider as available
            provider.is_busy = False
            provider.active_requests = max(0, provider.active_requests - 1)
    
    async def _check_overflow_scaling(self):
        """Check if overflow scaling is needed."""
        active_instances = [i for i in self.instance_status.values() if i.is_active]
        total_active_providers = sum(len(i.active_providers) for i in active_instances)
        busy_providers = sum(1 for p in self.provider_status.values() if p.is_busy)
        
        # Check if all active providers are busy
        if busy_providers >= total_active_providers:
            if len(active_instances) == 1 and 2 not in self.instance_status:
                # Scale to Instance 2
                await self._scale_up_instance(2)
            elif len(active_instances) == 2 and 3 not in self.instance_status:
                # Scale to Instance 3
                await self._scale_up_instance(3)
            else:
                logger.warning("All instances at maximum capacity")
    
    async def _scale_up_instance(self, instance_id: int):
        """Scale up a new browser instance."""
        if instance_id > self.MAX_INSTANCES:
            logger.warning(f"Cannot scale beyond {self.MAX_INSTANCES} instances")
            return
        
        # Check scaling cooldown
        if (self.metrics.last_scaling_time and 
            datetime.now() - self.metrics.last_scaling_time < timedelta(seconds=self.SCALING_COOLDOWN_SECONDS)):
            logger.info("Scaling cooldown active, skipping scale-up")
            return
        
        logger.info(f"Scaling up Browser Instance {instance_id}")
        
        try:
            # Start the browser instance
            await self.browser_manager.start_instance(instance_id)
            
            # Create instance status
            self.instance_status[instance_id] = BrowserInstanceStatus(
                instance_id=instance_id,
                is_active=True,
                provider_count=5,
                active_providers=self._get_providers_for_instance(instance_id),
                startup_time=datetime.now(),
                last_activity_time=datetime.now()
            )
            
            # Initialize provider status for new instance
            for service_type in self.instance_status[instance_id].active_providers:
                self.provider_status[service_type] = ProviderStatus(
                    service_type=service_type,
                    browser_instance_id=instance_id
                )
            
            # Update metrics
            self.metrics.total_active_instances += 1
            self.metrics.total_active_providers += 5
            self.metrics.last_scaling_event = ScalingEvent.SCALE_UP
            self.metrics.last_scaling_time = datetime.now()
            
            logger.info(f"Browser Instance {instance_id} scaled up successfully")
            
        except Exception as e:
            logger.error(f"Failed to scale up Instance {instance_id}: {e}")
    
    async def _shutdown_instance(self, instance_id: int):
        """Shutdown a browser instance."""
        if instance_id == 1:
            logger.warning("Cannot shutdown Instance 1 (always active)")
            return
        
        if instance_id not in self.instance_status:
            return
        
        logger.info(f"Shutting down Browser Instance {instance_id}")
        
        try:
            # Stop the browser instance
            await self.browser_manager.stop_instance(instance_id)
            
            # Remove provider status for this instance
            providers_to_remove = [
                service_type for service_type, provider in self.provider_status.items()
                if provider.browser_instance_id == instance_id
            ]
            
            for service_type in providers_to_remove:
                del self.provider_status[service_type]
            
            # Remove instance status
            del self.instance_status[instance_id]
            
            # Update metrics
            self.metrics.total_active_instances -= 1
            self.metrics.total_active_providers -= 5
            self.metrics.last_scaling_event = ScalingEvent.SCALE_DOWN
            self.metrics.last_scaling_time = datetime.now()
            
            logger.info(f"Browser Instance {instance_id} shutdown successfully")
            
        except Exception as e:
            logger.error(f"Failed to shutdown Instance {instance_id}: {e}")
    
    def _get_providers_for_instance(self, instance_id: int) -> Set[ChatServiceType]:
        """Get the set of providers for a specific instance."""
        # For now, use the same 5 providers for all instances
        # In the future, this could be configurable
        return {
            ChatServiceType.K2THINK,
            ChatServiceType.QWEN,
            ChatServiceType.DEEPSEEK,
            ChatServiceType.GROK,
            ChatServiceType.ZAI
        }
    
    async def _wait_for_capacity(self, service_type: ChatServiceType, request_data: dict) -> dict:
        """Wait for capacity to become available."""
        max_wait_time = 30  # seconds
        check_interval = 0.5  # seconds
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            # Check if capacity is now available
            if service_type in self.provider_status:
                provider = self.provider_status[service_type]
                if not provider.is_busy:
                    return await self._execute_request(service_type, request_data)
            
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
        
        raise TimeoutError(f"No capacity available for {service_type} within {max_wait_time}s")
    
    async def _scaling_monitor(self):
        """Background task to monitor scaling conditions."""
        while True:
            try:
                await self._check_idle_instances()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scaling monitor: {e}")
                await asyncio.sleep(60)
    
    async def _check_idle_instances(self):
        """Check for idle instances that should be shutdown."""
        current_time = datetime.now()
        
        for instance_id, instance in list(self.instance_status.items()):
            if instance_id == 1:  # Never shutdown Instance 1
                continue
            
            if not instance.is_active:
                continue
            
            # Calculate idle time
            if instance.last_activity_time:
                idle_time = current_time - instance.last_activity_time
                instance.idle_minutes = idle_time.total_seconds() / 60
                
                # Check if instance should be shutdown
                if instance.idle_minutes >= self.IDLE_TIMEOUT_MINUTES:
                    logger.info(f"Instance {instance_id} idle for {instance.idle_minutes:.1f} minutes, shutting down")
                    await self._shutdown_instance(instance_id)
    
    async def _metrics_monitor(self):
        """Background task to update metrics."""
        while True:
            try:
                self._update_metrics()
                await asyncio.sleep(10)  # Update every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics monitor: {e}")
                await asyncio.sleep(10)
    
    def _update_metrics(self):
        """Update current scaling metrics."""
        active_instances = [i for i in self.instance_status.values() if i.is_active]
        
        self.metrics.total_active_instances = len(active_instances)
        self.metrics.total_active_providers = sum(len(i.active_providers) for i in active_instances)
        self.metrics.total_concurrent_requests = sum(p.active_requests for p in self.provider_status.values())
        self.metrics.pending_requests = len(self.pending_requests)
    
    def get_status(self) -> dict:
        """Get current scaling engine status."""
        return {
            'metrics': {
                'total_active_instances': self.metrics.total_active_instances,
                'total_active_providers': self.metrics.total_active_providers,
                'total_concurrent_requests': self.metrics.total_concurrent_requests,
                'pending_requests': self.metrics.pending_requests,
                'last_scaling_event': self.metrics.last_scaling_event.value if self.metrics.last_scaling_event else None,
                'last_scaling_time': self.metrics.last_scaling_time.isoformat() if self.metrics.last_scaling_time else None
            },
            'instances': {
                str(instance_id): {
                    'is_active': instance.is_active,
                    'provider_count': instance.provider_count,
                    'active_providers': [p.value for p in instance.active_providers],
                    'last_activity_time': instance.last_activity_time.isoformat() if instance.last_activity_time else None,
                    'idle_minutes': instance.idle_minutes,
                    'total_requests': instance.total_requests
                }
                for instance_id, instance in self.instance_status.items()
            },
            'providers': {
                provider.service_type.value: {
                    'browser_instance_id': provider.browser_instance_id,
                    'is_busy': provider.is_busy,
                    'active_requests': provider.active_requests,
                    'total_requests': provider.total_requests,
                    'error_count': provider.error_count,
                    'last_request_time': provider.last_request_time.isoformat() if provider.last_request_time else None
                }
                for provider in self.provider_status.values()
            }
        }
