"""
Intelligent Load Balancer with Multiple Strategies and Health Monitoring.

Provides advanced load balancing algorithms with real-time health monitoring,
performance-based routing, and automatic failover capabilities.
"""

import asyncio
import time
import logging
import random
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
import statistics

from backend.data.chat_proxy_models import ChatServiceType


logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    """Available load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_LEAST_CONNECTIONS = "weighted_least_connections"
    RESPONSE_TIME = "response_time"
    WEIGHTED_RESPONSE_TIME = "weighted_response_time"
    RESOURCE_BASED = "resource_based"
    HEALTH_BASED = "health_based"
    INTELLIGENT = "intelligent"
    ADAPTIVE = "adaptive"


@dataclass
class ServerMetrics:
    """Comprehensive server metrics for load balancing decisions."""
    server_id: str
    is_healthy: bool = True
    is_available: bool = True
    
    # Connection metrics
    active_connections: int = 0
    total_connections: int = 0
    max_connections: int = 100
    
    # Performance metrics
    avg_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    success_rate: float = 1.0
    error_rate: float = 0.0
    
    # Resource metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_usage: float = 0.0
    
    # Health metrics
    health_score: float = 1.0
    consecutive_failures: int = 0
    last_health_check: Optional[datetime] = None
    
    # Historical data
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    request_timestamps: deque = field(default_factory=lambda: deque(maxlen=1000))
    error_timestamps: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # Load balancing weights
    static_weight: float = 1.0
    dynamic_weight: float = 1.0
    effective_weight: float = 1.0
    
    # Capacity and limits
    capacity_score: float = 1.0
    throughput: float = 0.0  # requests per second
    
    def update_response_time(self, response_time: float):
        """Update response time metrics."""
        self.response_times.append(response_time)
        
        if len(self.response_times) == 1:
            self.avg_response_time = response_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.avg_response_time = (
                alpha * response_time + 
                (1 - alpha) * self.avg_response_time
            )
        
        self.min_response_time = min(self.min_response_time, response_time)
        self.max_response_time = max(self.max_response_time, response_time)
    
    def calculate_load_score(self) -> float:
        """Calculate current load score (0.0 = no load, 1.0 = full load)."""
        connection_load = self.active_connections / max(self.max_connections, 1)
        cpu_load = self.cpu_usage
        memory_load = self.memory_usage
        
        # Weighted average of different load factors
        return (
            connection_load * 0.4 +
            cpu_load * 0.3 +
            memory_load * 0.3
        )


@dataclass
class LoadBalancerConfig:
    """Configuration for load balancer behavior."""
    strategy: LoadBalancingStrategy = LoadBalancingStrategy.INTELLIGENT
    health_check_interval: int = 30  # seconds
    health_check_timeout: float = 5.0  # seconds
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds
    
    # Failure detection
    failure_threshold: int = 3  # consecutive failures before marking unhealthy
    recovery_threshold: int = 2  # consecutive successes before marking healthy
    
    # Performance thresholds
    max_response_time: float = 10.0  # seconds
    max_error_rate: float = 0.1  # 10%
    min_success_rate: float = 0.9  # 90%
    
    # Adaptive behavior
    enable_adaptive_weights: bool = True
    weight_adjustment_factor: float = 0.1
    performance_window: int = 300  # seconds for performance calculations


class IntelligentLoadBalancer:
    """
    Advanced load balancer with multiple strategies and intelligent routing.
    
    Features:
    - Multiple load balancing algorithms
    - Real-time health monitoring
    - Performance-based routing
    - Automatic failover and recovery
    - Adaptive weight adjustment
    - Circuit breaker integration
    """
    
    def __init__(self, config: Optional[LoadBalancerConfig] = None):
        self.config = config or LoadBalancerConfig()
        self.servers: Dict[str, ServerMetrics] = {}
        self.strategy = self.config.strategy
        
        # Round-robin state
        self.round_robin_index = 0
        
        # Health monitoring
        self.health_check_task: Optional[asyncio.Task] = None
        self.health_check_callbacks: Dict[str, Callable] = {}
        
        # Performance tracking
        self.global_metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'requests_per_second': 0.0
        }
        
        # Adaptive learning
        self.performance_history: deque = deque(maxlen=1000)
        self.strategy_performance: Dict[LoadBalancingStrategy, float] = {}
        
        logger.info(f"Intelligent Load Balancer initialized with strategy: {self.strategy.value}")
    
    async def start(self):
        """Start the load balancer and health monitoring."""
        logger.info("Starting Intelligent Load Balancer")
        
        # Start health check monitoring
        self.health_check_task = asyncio.create_task(self._health_check_monitor())
        
        logger.info("Load balancer started successfully")
    
    async def stop(self):
        """Stop the load balancer and cleanup resources."""
        logger.info("Stopping Intelligent Load Balancer")
        
        if self.health_check_task and not self.health_check_task.done():
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Load balancer stopped")
    
    def add_server(self, server_id: str, weight: float = 1.0, 
                   health_check_callback: Optional[Callable] = None):
        """Add a server to the load balancer pool."""
        self.servers[server_id] = ServerMetrics(
            server_id=server_id,
            static_weight=weight,
            dynamic_weight=weight,
            effective_weight=weight
        )
        
        if health_check_callback:
            self.health_check_callbacks[server_id] = health_check_callback
        
        logger.info(f"Added server '{server_id}' with weight {weight}")
    
    def remove_server(self, server_id: str):
        """Remove a server from the load balancer pool."""
        if server_id in self.servers:
            del self.servers[server_id]
            self.health_check_callbacks.pop(server_id, None)
            logger.info(f"Removed server '{server_id}'")
    
    async def select_server(self, request_context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Select the best server based on the current strategy.
        
        Args:
            request_context: Optional context for request-specific routing
            
        Returns:
            Server ID of selected server, or None if no healthy servers
        """
        healthy_servers = self._get_healthy_servers()
        
        if not healthy_servers:
            logger.warning("No healthy servers available")
            return None
        
        # Apply load balancing strategy
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin_select(healthy_servers)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_select(healthy_servers)
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._least_connections_select(healthy_servers)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_LEAST_CONNECTIONS:
            return self._weighted_least_connections_select(healthy_servers)
        elif self.strategy == LoadBalancingStrategy.RESPONSE_TIME:
            return self._response_time_select(healthy_servers)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_RESPONSE_TIME:
            return self._weighted_response_time_select(healthy_servers)
        elif self.strategy == LoadBalancingStrategy.RESOURCE_BASED:
            return self._resource_based_select(healthy_servers)
        elif self.strategy == LoadBalancingStrategy.HEALTH_BASED:
            return self._health_based_select(healthy_servers)
        elif self.strategy == LoadBalancingStrategy.INTELLIGENT:
            return self._intelligent_select(healthy_servers, request_context)
        elif self.strategy == LoadBalancingStrategy.ADAPTIVE:
            return await self._adaptive_select(healthy_servers, request_context)
        else:
            # Default to round-robin
            return self._round_robin_select(healthy_servers)
    
    def _get_healthy_servers(self) -> List[str]:
        """Get list of healthy and available servers."""
        return [
            server_id for server_id, metrics in self.servers.items()
            if metrics.is_healthy and metrics.is_available
        ]
    
    def _round_robin_select(self, servers: List[str]) -> str:
        """Simple round-robin selection."""
        if not servers:
            return None
        
        server = servers[self.round_robin_index % len(servers)]
        self.round_robin_index += 1
        return server
    
    def _weighted_round_robin_select(self, servers: List[str]) -> str:
        """Weighted round-robin selection."""
        if not servers:
            return None
        
        # Create weighted list
        weighted_servers = []
        for server_id in servers:
            weight = int(self.servers[server_id].effective_weight * 10)
            weighted_servers.extend([server_id] * max(1, weight))
        
        if not weighted_servers:
            return servers[0]
        
        server = weighted_servers[self.round_robin_index % len(weighted_servers)]
        self.round_robin_index += 1
        return server
    
    def _least_connections_select(self, servers: List[str]) -> str:
        """Select server with least active connections."""
        return min(servers, key=lambda s: self.servers[s].active_connections)
    
    def _weighted_least_connections_select(self, servers: List[str]) -> str:
        """Select server with best connections-to-weight ratio."""
        def connection_ratio(server_id: str) -> float:
            metrics = self.servers[server_id]
            return metrics.active_connections / max(metrics.effective_weight, 0.1)
        
        return min(servers, key=connection_ratio)
    
    def _response_time_select(self, servers: List[str]) -> str:
        """Select server with best response time."""
        return min(servers, key=lambda s: self.servers[s].avg_response_time)
    
    def _weighted_response_time_select(self, servers: List[str]) -> str:
        """Select server with best weighted response time."""
        def weighted_response_time(server_id: str) -> float:
            metrics = self.servers[server_id]
            return metrics.avg_response_time / max(metrics.effective_weight, 0.1)
        
        return min(servers, key=weighted_response_time)
    
    def _resource_based_select(self, servers: List[str]) -> str:
        """Select server based on resource utilization."""
        def resource_score(server_id: str) -> float:
            metrics = self.servers[server_id]
            return metrics.calculate_load_score()
        
        return min(servers, key=resource_score)
    
    def _health_based_select(self, servers: List[str]) -> str:
        """Select server based on health score."""
        return max(servers, key=lambda s: self.servers[s].health_score)
    
    def _intelligent_select(self, servers: List[str], 
                          request_context: Optional[Dict[str, Any]] = None) -> str:
        """Intelligent selection using multiple factors."""
        best_server = None
        best_score = float('-inf')
        
        for server_id in servers:
            metrics = self.servers[server_id]
            
            # Calculate composite score
            score = self._calculate_server_score(metrics, request_context)
            
            if score > best_score:
                best_score = score
                best_server = server_id
        
        return best_server
    
    def _calculate_server_score(self, metrics: ServerMetrics, 
                              request_context: Optional[Dict[str, Any]] = None) -> float:
        """Calculate composite score for intelligent selection."""
        # Performance factors (40%)
        performance_score = (
            (1.0 - min(metrics.avg_response_time / 10.0, 1.0)) * 0.15 +  # Response time
            metrics.success_rate * 0.15 +  # Success rate
            (1.0 - metrics.error_rate) * 0.10  # Error rate
        )
        
        # Load factors (30%)
        load_score = (
            (1.0 - metrics.calculate_load_score()) * 0.15 +  # Overall load
            (1.0 - metrics.active_connections / max(metrics.max_connections, 1)) * 0.15  # Connection load
        )
        
        # Health factors (20%)
        health_score = (
            metrics.health_score * 0.10 +  # Health score
            (1.0 - metrics.consecutive_failures / 10.0) * 0.10  # Failure history
        )
        
        # Weight factor (10%)
        weight_score = metrics.effective_weight / 10.0 * 0.10
        
        total_score = performance_score + load_score + health_score + weight_score
        
        # Apply request-specific adjustments
        if request_context:
            total_score *= self._apply_context_adjustments(metrics, request_context)
        
        return total_score
    
    def _apply_context_adjustments(self, metrics: ServerMetrics, 
                                 context: Dict[str, Any]) -> float:
        """Apply request-specific adjustments to server score."""
        adjustment = 1.0
        
        # Priority-based adjustment
        if 'priority' in context:
            priority = context['priority']
            if priority == 'high' and metrics.health_score > 0.9:
                adjustment *= 1.2  # Prefer healthy servers for high priority
            elif priority == 'low' and metrics.calculate_load_score() < 0.5:
                adjustment *= 1.1  # Prefer less loaded servers for low priority
        
        # Service type specific adjustments
        if 'service_type' in context:
            service_type = context['service_type']
            # Could implement service-specific routing logic here
        
        return adjustment
    
    async def _adaptive_select(self, servers: List[str], 
                             request_context: Optional[Dict[str, Any]] = None) -> str:
        """Adaptive selection that learns from performance."""
        # Try different strategies and learn from results
        if len(self.performance_history) < 100:
            # Not enough data, use intelligent selection
            return self._intelligent_select(servers, request_context)
        
        # Select strategy based on recent performance
        best_strategy = max(
            self.strategy_performance.items(),
            key=lambda x: x[1],
            default=(LoadBalancingStrategy.INTELLIGENT, 0.0)
        )[0]
        
        # Temporarily switch strategy
        original_strategy = self.strategy
        self.strategy = best_strategy
        
        try:
            server = await self.select_server(request_context)
        finally:
            self.strategy = original_strategy
        
        return server
    
    async def record_request_result(self, server_id: str, success: bool, 
                                  response_time: float, error: Optional[Exception] = None):
        """Record the result of a request for metrics and learning."""
        if server_id not in self.servers:
            return
        
        metrics = self.servers[server_id]
        
        # Update connection count
        metrics.active_connections = max(0, metrics.active_connections - 1)
        metrics.total_connections += 1
        
        # Update performance metrics
        if success:
            metrics.update_response_time(response_time)
            metrics.consecutive_failures = 0
            
            # Update success rate
            total_requests = len(metrics.request_timestamps)
            if total_requests > 0:
                successes = total_requests - len(metrics.error_timestamps)
                metrics.success_rate = successes / total_requests
                metrics.error_rate = 1.0 - metrics.success_rate
        else:
            metrics.consecutive_failures += 1
            metrics.error_timestamps.append(datetime.now())
            
            # Update error rate
            total_requests = len(metrics.request_timestamps)
            if total_requests > 0:
                metrics.error_rate = len(metrics.error_timestamps) / total_requests
                metrics.success_rate = 1.0 - metrics.error_rate
        
        # Update timestamps
        metrics.request_timestamps.append(datetime.now())
        
        # Update health score
        await self._update_health_score(server_id)
        
        # Update adaptive weights if enabled
        if self.config.enable_adaptive_weights:
            self._update_adaptive_weights(server_id, success, response_time)
        
        # Record for global metrics
        self.global_metrics['total_requests'] += 1
        if success:
            self.global_metrics['successful_requests'] += 1
        else:
            self.global_metrics['failed_requests'] += 1
        
        # Update global average response time
        if success:
            alpha = 0.1
            self.global_metrics['avg_response_time'] = (
                alpha * response_time + 
                (1 - alpha) * self.global_metrics['avg_response_time']
            )
    
    async def _update_health_score(self, server_id: str):
        """Update server health score based on recent performance."""
        metrics = self.servers[server_id]
        
        # Base health score on success rate and response time
        health_score = (
            metrics.success_rate * 0.6 +  # Success rate weight
            (1.0 - min(metrics.avg_response_time / self.config.max_response_time, 1.0)) * 0.3 +  # Response time weight
            (1.0 - metrics.consecutive_failures / self.config.failure_threshold) * 0.1  # Failure weight
        )
        
        metrics.health_score = max(0.0, min(1.0, health_score))
        
        # Mark as unhealthy if too many consecutive failures
        if metrics.consecutive_failures >= self.config.failure_threshold:
            metrics.is_healthy = False
            logger.warning(f"Server '{server_id}' marked as unhealthy")
        elif metrics.consecutive_failures == 0 and not metrics.is_healthy:
            # Potential recovery - need consecutive successes
            if metrics.success_rate >= self.config.min_success_rate:
                metrics.is_healthy = True
                logger.info(f"Server '{server_id}' recovered and marked as healthy")
    
    def _update_adaptive_weights(self, server_id: str, success: bool, response_time: float):
        """Update server weights based on performance."""
        metrics = self.servers[server_id]
        
        if success and response_time < self.config.max_response_time:
            # Good performance - increase weight
            adjustment = 1.0 + self.config.weight_adjustment_factor
        else:
            # Poor performance - decrease weight
            adjustment = 1.0 - self.config.weight_adjustment_factor
        
        metrics.dynamic_weight *= adjustment
        metrics.dynamic_weight = max(0.1, min(5.0, metrics.dynamic_weight))  # Clamp weights
        
        # Calculate effective weight
        metrics.effective_weight = (
            metrics.static_weight * 0.5 + 
            metrics.dynamic_weight * 0.5
        )
    
    async def _health_check_monitor(self):
        """Background task for health checking servers."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check monitor: {e}")
    
    async def _perform_health_checks(self):
        """Perform health checks on all servers."""
        tasks = []
        
        for server_id in self.servers.keys():
            if server_id in self.health_check_callbacks:
                task = asyncio.create_task(
                    self._check_server_health(server_id)
                )
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_server_health(self, server_id: str):
        """Check health of a specific server."""
        try:
            callback = self.health_check_callbacks[server_id]
            
            # Execute health check with timeout
            is_healthy = await asyncio.wait_for(
                callback(),
                timeout=self.config.health_check_timeout
            )
            
            metrics = self.servers[server_id]
            metrics.last_health_check = datetime.now()
            
            if is_healthy and not metrics.is_healthy:
                # Server recovered
                metrics.is_healthy = True
                metrics.consecutive_failures = 0
                logger.info(f"Server '{server_id}' health check passed - marked as healthy")
            elif not is_healthy and metrics.is_healthy:
                # Server failed
                metrics.consecutive_failures += 1
                if metrics.consecutive_failures >= self.config.failure_threshold:
                    metrics.is_healthy = False
                    logger.warning(f"Server '{server_id}' health check failed - marked as unhealthy")
        
        except Exception as e:
            logger.error(f"Health check failed for server '{server_id}': {e}")
            metrics = self.servers[server_id]
            metrics.consecutive_failures += 1
            if metrics.consecutive_failures >= self.config.failure_threshold:
                metrics.is_healthy = False
    
    def get_server_metrics(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific server."""
        if server_id not in self.servers:
            return None
        
        metrics = self.servers[server_id]
        return {
            'server_id': server_id,
            'is_healthy': metrics.is_healthy,
            'is_available': metrics.is_available,
            'active_connections': metrics.active_connections,
            'total_connections': metrics.total_connections,
            'avg_response_time': metrics.avg_response_time,
            'success_rate': metrics.success_rate,
            'error_rate': metrics.error_rate,
            'health_score': metrics.health_score,
            'load_score': metrics.calculate_load_score(),
            'static_weight': metrics.static_weight,
            'dynamic_weight': metrics.dynamic_weight,
            'effective_weight': metrics.effective_weight,
            'consecutive_failures': metrics.consecutive_failures,
            'last_health_check': metrics.last_health_check.isoformat() if metrics.last_health_check else None
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all servers and global stats."""
        return {
            'global_metrics': self.global_metrics,
            'strategy': self.strategy.value,
            'servers': {
                server_id: self.get_server_metrics(server_id)
                for server_id in self.servers.keys()
            },
            'healthy_servers': len(self._get_healthy_servers()),
            'total_servers': len(self.servers)
        }
