"""
Enhanced Unlimited Auto-Scaling Engine with Intelligent Load Balancing.

Features:
- Unlimited instance creation based on demand
- Predictive scaling with trend analysis
- Intelligent load balancing across all instances
- Multi-metric scaling decisions
- Advanced resource optimization
"""

import asyncio
import os
import time
import logging
import statistics
import uuid
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict

from backend.data.chat_proxy_models import ChatServiceType
from backend.util.browser_instance_manager import BrowserInstanceManager, BrowserInstance


logger = logging.getLogger(__name__)


class ScalingEvent(Enum):
    """Types of scaling events."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    PREDICTIVE_SCALE_UP = "predictive_scale_up"
    LOAD_BALANCE = "load_balance"
    INSTANCE_FAILURE = "instance_failure"
    CAPACITY_OPTIMIZATION = "capacity_optimization"


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_RESPONSE_TIME = "weighted_response_time"
    RESOURCE_BASED = "resource_based"
    INTELLIGENT = "intelligent"


@dataclass
class ProviderMetrics:
    """Enhanced provider metrics with performance tracking."""
    service_type: ChatServiceType
    browser_instance_id: int
    is_busy: bool = False
    active_requests: int = 0
    total_requests: int = 0
    error_count: int = 0
    last_request_time: Optional[datetime] = None
    
    # Performance metrics
    avg_response_time: float = 0.0
    success_rate: float = 1.0
    throughput: float = 0.0  # requests per minute
    
    # Historical data for trend analysis
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    request_timestamps: deque = field(default_factory=lambda: deque(maxlen=1000))


@dataclass
class InstanceMetrics:
    """Enhanced instance metrics with resource tracking."""
    instance_id: int
    is_active: bool = False
    provider_count: int = 0
    active_providers: Set[ChatServiceType] = field(default_factory=set)
    startup_time: Optional[datetime] = None
    last_activity_time: Optional[datetime] = None
    
    # Resource metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    active_connections: int = 0
    
    # Performance metrics
    total_requests_handled: int = 0
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    
    # Health status
    health_score: float = 1.0
    consecutive_failures: int = 0


@dataclass
class ScalingMetrics:
    """Comprehensive scaling metrics."""
    total_active_instances: int = 1
    total_active_providers: int = 5
    total_concurrent_requests: int = 0
    pending_requests: int = 0
    
    # Capacity metrics
    total_capacity: int = 5
    used_capacity: int = 0
    capacity_utilization: float = 0.0
    
    # Performance metrics
    avg_response_time: float = 0.0
    requests_per_minute: float = 0.0
    error_rate: float = 0.0
    
    # Scaling events
    last_scaling_event: Optional[ScalingEvent] = None
    last_scaling_time: Optional[datetime] = None
    scaling_events_count: int = 0
    
    # Predictive metrics
    predicted_load: float = 0.0
    trend_direction: str = "stable"  # "increasing", "decreasing", "stable"


class EnhancedScalingEngine:
    """
    Enhanced unlimited auto-scaling engine with intelligent load balancing.
    
    Features:
    - Unlimited instance creation based on demand
    - Predictive scaling with trend analysis
    - Multiple load balancing strategies
    - Advanced resource optimization
    - Multi-metric scaling decisions
    """
    
    def __init__(self, browser_manager: BrowserInstanceManager, config: Optional[dict] = None):
        self.browser_manager = browser_manager
        self.provider_metrics: Dict[ChatServiceType, ProviderMetrics] = {}
        self.instance_metrics: Dict[int, InstanceMetrics] = {}
        self.metrics = ScalingMetrics()
        
        # Load configuration from environment or provided config
        config = config or {}
        
        # Enhanced scaling configuration
        self.IDLE_TIMEOUT_MINUTES = int(os.getenv("SCALING_IDLE_TIMEOUT_MINUTES", config.get("idle_timeout_minutes", 15)))
        self.MIN_INSTANCES = int(os.getenv("SCALING_MIN_INSTANCES", config.get("min_instances", 1)))
        self.MAX_INSTANCES = self._parse_max_instances(os.getenv("SCALING_MAX_INSTANCES", config.get("max_instances")))
        self.PROVIDERS_PER_INSTANCE = int(os.getenv("SCALING_PROVIDERS_PER_INSTANCE", config.get("providers_per_instance", 5)))
        self.SCALING_COOLDOWN_SECONDS = int(os.getenv("SCALING_COOLDOWN_SECONDS", config.get("cooldown_seconds", 30)))
        
        # Advanced scaling parameters
        self.SCALE_UP_THRESHOLD = float(os.getenv("SCALING_UP_THRESHOLD", config.get("scale_up_threshold", 0.8)))
        self.SCALE_DOWN_THRESHOLD = float(os.getenv("SCALING_DOWN_THRESHOLD", config.get("scale_down_threshold", 0.3)))
        self.PREDICTIVE_SCALING_WINDOW = 300  # 5 minutes
        self.MAX_CONCURRENT_SCALING_OPERATIONS = 5
        self.INSTANCE_STARTUP_TIMEOUT = 120  # 2 minutes
        
        # Load balancing configuration
        self.load_balancing_strategy = LoadBalancingStrategy.INTELLIGENT
        self.instance_weights: Dict[int, float] = {}
        
        # Request handling
        self.pending_requests: deque = deque()
        self.request_lock = asyncio.Lock()
        self.active_scaling_operations: Set[int] = set()
        
        # Metrics collection
        self.metrics_history: deque = deque(maxlen=1000)
        self.load_predictions: deque = deque(maxlen=100)
        
        # Initialize base instance
        self._initialize_base_instance()
        
        # Background tasks
        self._scaling_task = None
        self._monitoring_task = None
        self._metrics_task = None
        self._prediction_task = None

    def _parse_max_instances(self, value) -> Optional[int]:
        """Parse max instances configuration value."""
        if value is None or str(value).lower() in ['none', 'unlimited', '']:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid max_instances value: {value}, using unlimited")
            return None
        
    def _initialize_base_instance(self):
        """Initialize the base browser instance (always active)."""
        base_providers = {
            ChatServiceType.K2THINK,
            ChatServiceType.QWEN,
            ChatServiceType.DEEPSEEK,
            ChatServiceType.GROK,
            ChatServiceType.ZAI
        }
        
        self.instance_metrics[1] = InstanceMetrics(
            instance_id=1,
            is_active=True,
            provider_count=len(base_providers),
            active_providers=base_providers,
            startup_time=datetime.now(),
            last_activity_time=datetime.now(),
            health_score=1.0
        )
        
        # Initialize provider metrics
        for service_type in base_providers:
            self.provider_metrics[service_type] = ProviderMetrics(
                service_type=service_type,
                browser_instance_id=1
            )
        
        self.instance_weights[1] = 1.0
        logger.info("Base instance initialized with 5 providers")
    
    async def start(self):
        """Start the enhanced scaling engine with all background tasks."""
        logger.info("Starting Enhanced Scaling Engine with unlimited scaling")
        
        # Start background monitoring tasks
        self._scaling_task = asyncio.create_task(self._scaling_monitor())
        self._monitoring_task = asyncio.create_task(self._health_monitor())
        self._metrics_task = asyncio.create_task(self._metrics_collector())
        self._prediction_task = asyncio.create_task(self._predictive_analyzer())
        
        logger.info("All background tasks started successfully")
    
    async def stop(self):
        """Stop the scaling engine and cleanup resources."""
        logger.info("Stopping Enhanced Scaling Engine")
        
        # Cancel background tasks
        for task in [self._scaling_task, self._monitoring_task, 
                    self._metrics_task, self._prediction_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Cleanup non-base instances
        await self._cleanup_idle_instances(force=True)
        logger.info("Enhanced Scaling Engine stopped")
    
    async def handle_request(self, service_type: ChatServiceType, request_data: dict) -> dict:
        """
        Handle incoming request with intelligent load balancing.
        
        Args:
            service_type: The chat service type to route to
            request_data: The request payload
            
        Returns:
            Formatted response from the selected provider
        """
        start_time = time.time()
        
        async with self.request_lock:
            # Find best available provider using intelligent load balancing
            provider = await self._select_optimal_provider(service_type)
            
            if not provider:
                # No available provider - check if we need to scale up
                await self._handle_capacity_shortage(service_type)
                
                # Add to pending queue
                self.pending_requests.append({
                    'service_type': service_type,
                    'request_data': request_data,
                    'timestamp': datetime.now(),
                    'start_time': start_time
                })
                
                # Wait for capacity or timeout
                return await self._wait_for_capacity(service_type, request_data, start_time)
            
            # Process request with selected provider
            return await self._process_request(provider, request_data, start_time)
    
    async def _select_optimal_provider(self, service_type: ChatServiceType) -> Optional[ProviderMetrics]:
        """Select the optimal provider using intelligent load balancing."""
        available_providers = [
            provider for provider in self.provider_metrics.values()
            if (provider.service_type == service_type and 
                not provider.is_busy and
                self.instance_metrics[provider.browser_instance_id].is_active)
        ]
        
        if not available_providers:
            return None
        
        # Apply load balancing strategy
        if self.load_balancing_strategy == LoadBalancingStrategy.INTELLIGENT:
            return self._intelligent_provider_selection(available_providers)
        elif self.load_balancing_strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return min(available_providers, key=lambda p: p.active_requests)
        elif self.load_balancing_strategy == LoadBalancingStrategy.WEIGHTED_RESPONSE_TIME:
            return min(available_providers, key=lambda p: p.avg_response_time)
        else:  # ROUND_ROBIN
            return available_providers[0]  # Simplified round-robin
    
    def _intelligent_provider_selection(self, providers: List[ProviderMetrics]) -> ProviderMetrics:
        """Select provider using intelligent algorithm considering multiple factors."""
        best_provider = None
        best_score = float('-inf')
        
        for provider in providers:
            instance = self.instance_metrics[provider.browser_instance_id]
            
            # Calculate composite score
            score = (
                # Performance factors (40%)
                (1.0 - provider.avg_response_time / 10.0) * 0.2 +  # Response time
                provider.success_rate * 0.2 +  # Success rate
                
                # Load factors (30%)
                (1.0 - provider.active_requests / 10.0) * 0.15 +  # Current load
                (1.0 - instance.cpu_usage) * 0.15 +  # CPU usage
                
                # Health factors (30%)
                instance.health_score * 0.15 +  # Instance health
                (1.0 - provider.error_count / max(provider.total_requests, 1)) * 0.15  # Error rate
            )
            
            if score > best_score:
                best_score = score
                best_provider = provider
        
        return best_provider
    
    async def _handle_capacity_shortage(self, service_type: ChatServiceType):
        """Handle capacity shortage by scaling up if needed."""
        current_utilization = self._calculate_capacity_utilization()
        
        if current_utilization >= self.SCALE_UP_THRESHOLD:
            await self._scale_up_decision()
    
    async def _scale_up_decision(self):
        """Make intelligent scale-up decision."""
        # Check if we're already scaling
        if len(self.active_scaling_operations) >= self.MAX_CONCURRENT_SCALING_OPERATIONS:
            logger.warning("Maximum concurrent scaling operations reached")
            return
        
        # Check cooldown period
        if (self.metrics.last_scaling_time and 
            (datetime.now() - self.metrics.last_scaling_time).total_seconds() < self.SCALING_COOLDOWN_SECONDS):
            return
        
        # Determine next instance ID
        next_instance_id = max(self.instance_metrics.keys()) + 1
        
        # Start scaling operation
        self.active_scaling_operations.add(next_instance_id)
        
        try:
            await self._create_new_instance(next_instance_id)
            logger.info(f"Successfully scaled up to {len(self.instance_metrics)} instances")
            
            # Update metrics
            self.metrics.last_scaling_event = ScalingEvent.SCALE_UP
            self.metrics.last_scaling_time = datetime.now()
            self.metrics.scaling_events_count += 1
            
        except Exception as e:
            logger.error(f"Failed to scale up instance {next_instance_id}: {e}")
        finally:
            self.active_scaling_operations.discard(next_instance_id)
    
    async def _create_new_instance(self, instance_id: int):
        """Create a new browser instance with providers."""
        logger.info(f"Creating new instance {instance_id}")
        
        # Generate unique fingerprint for new instance
        fingerprint = self._generate_dynamic_fingerprint(instance_id)
        
        # Create browser instance
        browser_instance = await self.browser_manager.create_instance(
            instance_id=instance_id,
            fingerprint=fingerprint
        )
        
        if not browser_instance:
            raise Exception(f"Failed to create browser instance {instance_id}")
        
        # Initialize instance metrics
        self.instance_metrics[instance_id] = InstanceMetrics(
            instance_id=instance_id,
            is_active=True,
            provider_count=self.PROVIDERS_PER_INSTANCE,
            active_providers=set(),
            startup_time=datetime.now(),
            last_activity_time=datetime.now(),
            health_score=1.0
        )
        
        # Assign providers to new instance
        await self._assign_providers_to_instance(instance_id)
        
        # Set initial weight
        self.instance_weights[instance_id] = 1.0
        
        # Update total capacity
        self._update_capacity_metrics()
    
    def _generate_dynamic_fingerprint(self, instance_id: int) -> dict:
        """Generate unique browser fingerprint for new instance."""
        fingerprints = [
            {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": (1920, 1080),
                "timezone": "America/New_York",
                "language": "en-US",
                "platform": "Win32"
            },
            {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": (1440, 900),
                "timezone": "America/Los_Angeles",
                "language": "en-US",
                "platform": "MacIntel"
            },
            {
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": (1366, 768),
                "timezone": "Europe/London",
                "language": "en-GB",
                "platform": "Linux x86_64"
            }
        ]
        
        # Cycle through fingerprints and add variations
        base_fingerprint = fingerprints[(instance_id - 1) % len(fingerprints)]
        
        # Add instance-specific variations
        variations = {
            "screen_resolution": [(1920, 1080), (1440, 900), (1366, 768), (1536, 864), (1280, 720)],
            "color_depth": [24, 32],
            "device_memory": [4, 8, 16],
            "hardware_concurrency": [4, 8, 12, 16]
        }
        
        fingerprint = base_fingerprint.copy()
        fingerprint.update({
            "instance_id": instance_id,
            "screen_resolution": variations["screen_resolution"][(instance_id - 1) % len(variations["screen_resolution"])],
            "color_depth": variations["color_depth"][(instance_id - 1) % len(variations["color_depth"])],
            "device_memory": variations["device_memory"][(instance_id - 1) % len(variations["device_memory"])],
            "hardware_concurrency": variations["hardware_concurrency"][(instance_id - 1) % len(variations["hardware_concurrency"])]
        })
        
        return fingerprint

    async def _wait_for_capacity(self, service_type: ChatServiceType, request_data: dict, start_time: float) -> dict:
        """Wait for capacity to become available."""
        max_wait_time = 30  # seconds
        check_interval = 0.5  # seconds
        
        waited_time = 0
        while waited_time < max_wait_time:
            # Check if capacity is now available
            provider = await self._select_optimal_provider(service_type)
            if provider:
                return await self._process_request(provider, request_data, start_time)
            
            # Wait and check again
            await asyncio.sleep(check_interval)
            waited_time += check_interval
        
        # Timeout - return error response
        raise Exception(f"Request timeout: No capacity available for {service_type} after {max_wait_time}s")

    async def _process_request(self, provider: ProviderMetrics, request_data: dict, start_time: float) -> dict:
        """Process request with the selected provider."""
        try:
            # Mark provider as busy
            provider.is_busy = True
            provider.active_requests += 1
            provider.last_request_time = datetime.now()
            
            # Get browser instance
            instance = self.instance_metrics[provider.browser_instance_id]
            browser_instance = await self.browser_manager.get_instance(provider.browser_instance_id)
            
            if not browser_instance:
                raise Exception(f"Browser instance {provider.browser_instance_id} not available")
            
            # Process the request (simplified - would integrate with actual chat service)
            response_data = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request_data.get("model", "unknown"),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"Response from {provider.service_type.value} via instance {provider.browser_instance_id}"
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                }
            }
            
            # Update metrics
            response_time = time.time() - start_time
            provider.response_times.append(response_time)
            provider.total_requests += 1
            
            # Calculate new average response time
            if provider.response_times:
                provider.avg_response_time = statistics.mean(provider.response_times)
            
            # Update success rate
            provider.success_rate = (provider.total_requests - provider.error_count) / provider.total_requests
            
            return response_data
            
        except Exception as e:
            # Update error metrics
            provider.error_count += 1
            if provider.total_requests > 0:
                provider.success_rate = (provider.total_requests - provider.error_count) / provider.total_requests
            
            logger.error(f"Request processing failed for {provider.service_type}: {e}")
            raise
            
        finally:
            # Mark provider as not busy
            provider.is_busy = False
            provider.active_requests = max(0, provider.active_requests - 1)

    async def _scaling_monitor(self):
        """Background task to monitor scaling needs."""
        while True:
            try:
                await asyncio.sleep(self.SCALING_COOLDOWN_SECONDS)
                
                # Calculate current utilization
                utilization = self._calculate_capacity_utilization()
                
                # Check if we need to scale up
                if utilization >= self.SCALE_UP_THRESHOLD:
                    await self._scale_up_decision()
                
                # Check if we can scale down
                elif utilization <= self.SCALE_DOWN_THRESHOLD:
                    await self._scale_down_decision()
                
                # Update metrics
                self.metrics.capacity_utilization = utilization
                self.metrics.total_active_instances = len([i for i in self.instance_metrics.values() if i.is_active])
                self.metrics.total_active_providers = len([p for p in self.provider_metrics.values() if not p.is_busy])
                
            except Exception as e:
                logger.error(f"Scaling monitor error: {e}")

    async def _health_monitor(self):
        """Background task to monitor instance and provider health."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check instance health
                for instance_id, instance in self.instance_metrics.items():
                    if not instance.is_active:
                        continue
                    
                    # Check if instance is responsive
                    try:
                        browser_instance = await self.browser_manager.get_instance(instance_id)
                        if not browser_instance:
                            instance.consecutive_failures += 1
                            instance.health_score = max(0.1, instance.health_score - 0.1)
                        else:
                            instance.consecutive_failures = 0
                            instance.health_score = min(1.0, instance.health_score + 0.1)
                    except Exception as e:
                        logger.warning(f"Health check failed for instance {instance_id}: {e}")
                        instance.consecutive_failures += 1
                        instance.health_score = max(0.1, instance.health_score - 0.2)
                
                # Check provider health
                for provider in self.provider_metrics.values():
                    instance = self.instance_metrics.get(provider.browser_instance_id)
                    if instance and instance.consecutive_failures >= 3:
                        provider.error_count += 1
                
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    async def _metrics_collector(self):
        """Background task to collect and update metrics."""
        while True:
            try:
                await asyncio.sleep(30)  # Collect every 30 seconds
                
                # Collect current metrics
                current_metrics = ScalingMetrics()
                current_metrics.total_active_instances = len([i for i in self.instance_metrics.values() if i.is_active])
                current_metrics.total_active_providers = len(self.provider_metrics)
                current_metrics.total_concurrent_requests = sum(p.active_requests for p in self.provider_metrics.values())
                
                # Calculate capacity metrics
                current_metrics.total_capacity = current_metrics.total_active_instances * self.PROVIDERS_PER_INSTANCE
                current_metrics.used_capacity = len([p for p in self.provider_metrics.values() if p.is_busy])
                current_metrics.capacity_utilization = (
                    current_metrics.used_capacity / current_metrics.total_capacity 
                    if current_metrics.total_capacity > 0 else 0
                )
                
                # Calculate performance metrics
                if self.provider_metrics:
                    response_times = [p.avg_response_time for p in self.provider_metrics.values() if p.avg_response_time > 0]
                    current_metrics.avg_response_time = statistics.mean(response_times) if response_times else 0
                    
                    total_requests = sum(p.total_requests for p in self.provider_metrics.values())
                    total_errors = sum(p.error_count for p in self.provider_metrics.values())
                    current_metrics.error_rate = (total_errors / total_requests) if total_requests > 0 else 0
                
                # Store metrics
                self.metrics = current_metrics
                self.metrics_history.append(current_metrics)
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")

    async def _predictive_analyzer(self):
        """Background task for predictive scaling analysis."""
        while True:
            try:
                await asyncio.sleep(self.PREDICTIVE_SCALING_WINDOW)  # Analyze every 5 minutes
                
                if len(self.metrics_history) < 3:
                    await asyncio.sleep(60)
                    continue
                
                # Analyze trends
                recent_metrics = list(self.metrics_history)[-10:]  # Last 10 data points
                utilizations = [m.capacity_utilization for m in recent_metrics]
                
                if len(utilizations) >= 3:
                    # Simple trend analysis
                    recent_avg = statistics.mean(utilizations[-3:])
                    older_avg = statistics.mean(utilizations[-6:-3]) if len(utilizations) >= 6 else recent_avg
                    
                    if recent_avg > older_avg + 0.1:
                        self.metrics.trend_direction = "increasing"
                        # Predictive scale up if trend is strongly increasing
                        if recent_avg > 0.6 and self.metrics.trend_direction == "increasing":
                            await self._predictive_scale_up()
                    elif recent_avg < older_avg - 0.1:
                        self.metrics.trend_direction = "decreasing"
                    else:
                        self.metrics.trend_direction = "stable"
                
                # Predict future load
                if len(utilizations) >= 5:
                    # Simple linear prediction
                    x = list(range(len(utilizations)))
                    y = utilizations
                    
                    # Calculate simple linear regression slope
                    n = len(x)
                    slope = (n * sum(x[i] * y[i] for i in range(n)) - sum(x) * sum(y)) / (n * sum(x[i]**2 for i in range(n)) - sum(x)**2)
                    
                    # Predict next value
                    self.metrics.predicted_load = max(0, min(1, utilizations[-1] + slope))
                
            except Exception as e:
                logger.error(f"Predictive analyzer error: {e}")

    async def _assign_providers_to_instance(self, instance_id: int):
        """Assign providers to a new instance."""
        try:
            # Assign all service types to the new instance
            service_types = [
                ChatServiceType.K2THINK,
                ChatServiceType.QWEN,
                ChatServiceType.DEEPSEEK,
                ChatServiceType.GROK,
                ChatServiceType.ZAI
            ]
            
            for service_type in service_types:
                provider_id = f"{service_type.value}_{instance_id}"
                
                self.provider_metrics[service_type] = ProviderMetrics(
                    service_type=service_type,
                    browser_instance_id=instance_id
                )
                
                # Update instance metrics
                self.instance_metrics[instance_id].active_providers.add(service_type)
            
            self.instance_metrics[instance_id].provider_count = len(service_types)
            logger.info(f"Assigned {len(service_types)} providers to instance {instance_id}")
            
        except Exception as e:
            logger.error(f"Failed to assign providers to instance {instance_id}: {e}")
            raise

    def _update_capacity_metrics(self):
        """Update capacity-related metrics."""
        try:
            active_instances = len([i for i in self.instance_metrics.values() if i.is_active])
            total_providers = len(self.provider_metrics)
            busy_providers = len([p for p in self.provider_metrics.values() if p.is_busy])
            
            self.metrics.total_active_instances = active_instances
            self.metrics.total_active_providers = total_providers
            self.metrics.total_capacity = active_instances * self.PROVIDERS_PER_INSTANCE
            self.metrics.used_capacity = busy_providers
            self.metrics.capacity_utilization = (
                busy_providers / (active_instances * self.PROVIDERS_PER_INSTANCE)
                if active_instances > 0 else 0
            )
            
        except Exception as e:
            logger.error(f"Failed to update capacity metrics: {e}")

    def _calculate_capacity_utilization(self) -> float:
        """Calculate current capacity utilization."""
        try:
            active_instances = len([i for i in self.instance_metrics.values() if i.is_active])
            if active_instances == 0:
                return 0.0
            
            total_capacity = active_instances * self.PROVIDERS_PER_INSTANCE
            busy_providers = len([p for p in self.provider_metrics.values() if p.is_busy])
            
            return busy_providers / total_capacity
            
        except Exception as e:
            logger.error(f"Failed to calculate capacity utilization: {e}")
            return 0.0

    async def _scale_down_decision(self):
        """Make intelligent scale-down decision."""
        try:
            # Don't scale down below minimum instances
            active_instances = [i for i in self.instance_metrics.values() if i.is_active]
            if len(active_instances) <= self.MIN_INSTANCES:
                return
            
            # Find least utilized instance (excluding base instance)
            candidates = [i for i in active_instances if i.instance_id != 1]  # Don't remove base instance
            if not candidates:
                return
            
            # Sort by utilization (least busy first)
            candidates.sort(key=lambda i: len([p for p in self.provider_metrics.values() 
                                            if p.browser_instance_id == i.instance_id and p.is_busy]))
            
            # Check if least utilized instance has been idle long enough
            least_utilized = candidates[0]
            if (least_utilized.last_activity_time and 
                (datetime.now() - least_utilized.last_activity_time).total_seconds() > self.IDLE_TIMEOUT_MINUTES * 60):
                
                await self._remove_instance(least_utilized.instance_id)
                
        except Exception as e:
            logger.error(f"Scale down decision failed: {e}")

    async def _predictive_scale_up(self):
        """Perform predictive scale up based on trends."""
        try:
            logger.info("Performing predictive scale up based on increasing load trend")
            await self._scale_up_decision()
            
            # Update metrics
            self.metrics.last_scaling_event = ScalingEvent.PREDICTIVE_SCALE_UP
            self.metrics.last_scaling_time = datetime.now()
            self.metrics.scaling_events_count += 1
            
        except Exception as e:
            logger.error(f"Predictive scale up failed: {e}")

    async def _remove_instance(self, instance_id: int):
        """Remove a browser instance and its providers."""
        try:
            logger.info(f"Removing instance {instance_id}")
            
            # Remove providers associated with this instance
            providers_to_remove = [
                service_type for service_type, provider in self.provider_metrics.items()
                if provider.browser_instance_id == instance_id
            ]
            
            for service_type in providers_to_remove:
                del self.provider_metrics[service_type]
            
            # Mark instance as inactive
            if instance_id in self.instance_metrics:
                self.instance_metrics[instance_id].is_active = False
            
            # Remove from browser manager
            await self.browser_manager.remove_instance(instance_id)
            
            # Update capacity metrics
            self._update_capacity_metrics()
            
            # Update scaling metrics
            self.metrics.last_scaling_event = ScalingEvent.SCALE_DOWN
            self.metrics.last_scaling_time = datetime.now()
            self.metrics.scaling_events_count += 1
            
            logger.info(f"Successfully removed instance {instance_id}")
            
        except Exception as e:
            logger.error(f"Failed to remove instance {instance_id}: {e}")

    async def _cleanup_idle_instances(self, force: bool = False):
        """Cleanup idle instances during shutdown."""
        try:
            instances_to_remove = []
            
            for instance_id, instance in self.instance_metrics.items():
                if instance_id == 1:  # Never remove base instance
                    continue
                    
                if force or (instance.last_activity_time and 
                           (datetime.now() - instance.last_activity_time).total_seconds() > self.IDLE_TIMEOUT_MINUTES * 60):
                    instances_to_remove.append(instance_id)
            
            for instance_id in instances_to_remove:
                await self._remove_instance(instance_id)
                
        except Exception as e:
            logger.error(f"Cleanup idle instances failed: {e}")

    def get_status(self) -> dict:
        """Get current scaling engine status."""
        return {
            "metrics": {
                "total_active_instances": self.metrics.total_active_instances,
                "total_active_providers": self.metrics.total_active_providers,
                "total_concurrent_requests": self.metrics.total_concurrent_requests,
                "capacity_utilization": self.metrics.capacity_utilization,
                "avg_response_time": self.metrics.avg_response_time,
                "error_rate": self.metrics.error_rate,
                "trend_direction": self.metrics.trend_direction,
                "predicted_load": self.metrics.predicted_load
            },
            "instances": {
                str(instance_id): {
                    "is_active": instance.is_active,
                    "provider_count": instance.provider_count,
                    "health_score": instance.health_score,
                    "consecutive_failures": instance.consecutive_failures
                }
                for instance_id, instance in self.instance_metrics.items()
            },
            "providers": {
                service_type.value: {
                    "browser_instance_id": provider.browser_instance_id,
                    "is_busy": provider.is_busy,
                    "active_requests": provider.active_requests,
                    "total_requests": provider.total_requests,
                    "error_count": provider.error_count,
                    "avg_response_time": provider.avg_response_time,
                    "success_rate": provider.success_rate
                }
                for service_type, provider in self.provider_metrics.items()
            }
        }
