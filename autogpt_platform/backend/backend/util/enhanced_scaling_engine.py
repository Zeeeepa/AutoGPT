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
import time
import logging
import statistics
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
    
    def __init__(self, browser_manager: BrowserInstanceManager):
        self.browser_manager = browser_manager
        self.provider_metrics: Dict[ChatServiceType, ProviderMetrics] = {}
        self.instance_metrics: Dict[int, InstanceMetrics] = {}
        self.metrics = ScalingMetrics()
        
        # Enhanced scaling configuration
        self.IDLE_TIMEOUT_MINUTES = 15  # Faster scale-down
        self.MIN_INSTANCES = 1  # Always keep base instance
        self.MAX_INSTANCES = None  # Unlimited scaling
        self.PROVIDERS_PER_INSTANCE = 5
        self.SCALING_COOLDOWN_SECONDS = 30  # Faster decisions
        
        # Advanced scaling parameters
        self.SCALE_UP_THRESHOLD = 0.8  # Scale up at 80% capacity
        self.SCALE_DOWN_THRESHOLD = 0.3  # Scale down below 30%
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
