"""
Circuit Breaker Pattern Implementation for Enhanced Reliability.

Provides automatic failure detection and recovery for external service calls.
Prevents cascade failures and implements intelligent retry strategies.
"""

import asyncio
import time
import logging
from typing import Dict, Optional, Callable, Any, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque


logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: int = 60  # Seconds before trying half-open
    success_threshold: int = 3  # Successes to close from half-open
    timeout: float = 30.0  # Request timeout in seconds
    
    # Advanced configuration
    failure_rate_threshold: float = 0.5  # 50% failure rate
    minimum_requests: int = 10  # Minimum requests before calculating rate
    sliding_window_size: int = 100  # Size of sliding window for metrics
    
    # Exponential backoff
    max_retry_attempts: int = 3
    base_delay: float = 1.0  # Base delay for exponential backoff
    max_delay: float = 60.0  # Maximum delay between retries
    jitter: bool = True  # Add randomness to prevent thundering herd


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeouts: int = 0
    
    # Timing metrics
    avg_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    
    # State transitions
    state_changes: int = 0
    last_state_change: Optional[datetime] = None
    time_in_open_state: float = 0.0
    
    # Recent history for sliding window
    recent_results: deque = field(default_factory=lambda: deque(maxlen=100))
    recent_response_times: deque = field(default_factory=lambda: deque(maxlen=100))


class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors."""
    pass


class CircuitOpenError(CircuitBreakerError):
    """Raised when circuit is open and blocking requests."""
    pass


class CircuitTimeoutError(CircuitBreakerError):
    """Raised when request times out."""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation with advanced failure detection and recovery.
    
    Features:
    - Automatic failure detection and recovery
    - Exponential backoff with jitter
    - Sliding window metrics
    - Configurable thresholds and timeouts
    - Comprehensive monitoring and logging
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        
        # State management
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state_change_time = datetime.now()
        
        # Concurrency control
        self.lock = asyncio.Lock()
        
        logger.info(f"Circuit breaker '{name}' initialized in CLOSED state")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitOpenError: When circuit is open
            CircuitTimeoutError: When request times out
            CircuitBreakerError: Other circuit breaker errors
        """
        async with self.lock:
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                if not self._should_attempt_reset():
                    self.metrics.total_requests += 1
                    raise CircuitOpenError(f"Circuit breaker '{self.name}' is OPEN")
                else:
                    # Transition to half-open for testing
                    await self._transition_to_half_open()
        
        # Execute the function with timeout and retry logic
        return await self._execute_with_protection(func, *args, **kwargs)
    
    async def _execute_with_protection(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with timeout and error handling."""
        start_time = time.time()
        last_exception = None
        
        for attempt in range(self.config.max_retry_attempts + 1):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    self._execute_function(func, *args, **kwargs),
                    timeout=self.config.timeout
                )
                
                # Record success
                response_time = time.time() - start_time
                await self._record_success(response_time)
                
                return result
                
            except asyncio.TimeoutError:
                last_exception = CircuitTimeoutError(
                    f"Request to '{self.name}' timed out after {self.config.timeout}s"
                )
                await self._record_timeout()
                
            except Exception as e:
                last_exception = e
                await self._record_failure(e)
            
            # Apply exponential backoff for retries
            if attempt < self.config.max_retry_attempts:
                delay = self._calculate_backoff_delay(attempt)
                logger.warning(
                    f"Circuit breaker '{self.name}' attempt {attempt + 1} failed, "
                    f"retrying in {delay:.2f}s: {last_exception}"
                )
                await asyncio.sleep(delay)
        
        # All retries exhausted
        raise last_exception
    
    async def _execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Execute the actual function (sync or async)."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            # Run sync function in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)
    
    async def _record_success(self, response_time: float):
        """Record successful request."""
        async with self.lock:
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            self.metrics.recent_results.append(True)
            self.metrics.recent_response_times.append(response_time)
            
            # Update response time metrics
            self._update_response_time_metrics(response_time)
            
            # Handle state transitions
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    await self._transition_to_closed()
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
    
    async def _record_failure(self, exception: Exception):
        """Record failed request."""
        async with self.lock:
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.recent_results.append(False)
            
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            logger.warning(f"Circuit breaker '{self.name}' recorded failure: {exception}")
            
            # Check if we should open the circuit
            if self._should_open_circuit():
                await self._transition_to_open()
    
    async def _record_timeout(self):
        """Record timeout as failure."""
        async with self.lock:
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.timeouts += 1
            self.metrics.recent_results.append(False)
            
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            logger.warning(f"Circuit breaker '{self.name}' recorded timeout")
            
            if self._should_open_circuit():
                await self._transition_to_open()
    
    def _should_open_circuit(self) -> bool:
        """Determine if circuit should be opened."""
        # Check failure count threshold
        if self.failure_count >= self.config.failure_threshold:
            return True
        
        # Check failure rate if we have enough requests
        if len(self.metrics.recent_results) >= self.config.minimum_requests:
            failure_rate = self._calculate_failure_rate()
            if failure_rate >= self.config.failure_rate_threshold:
                return True
        
        return False
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset from open state."""
        if self.state != CircuitState.OPEN:
            return False
        
        time_since_open = (datetime.now() - self.state_change_time).total_seconds()
        return time_since_open >= self.config.recovery_timeout
    
    async def _transition_to_open(self):
        """Transition circuit to OPEN state."""
        if self.state != CircuitState.OPEN:
            logger.warning(f"Circuit breaker '{self.name}' transitioning to OPEN state")
            self.state = CircuitState.OPEN
            self.state_change_time = datetime.now()
            self.metrics.state_changes += 1
            self.metrics.last_state_change = self.state_change_time
    
    async def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state."""
        logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN state")
        self.state = CircuitState.HALF_OPEN
        self.state_change_time = datetime.now()
        self.success_count = 0
        self.metrics.state_changes += 1
        self.metrics.last_state_change = self.state_change_time
    
    async def _transition_to_closed(self):
        """Transition circuit to CLOSED state."""
        logger.info(f"Circuit breaker '{self.name}' transitioning to CLOSED state")
        
        # Calculate time spent in open state
        if self.state == CircuitState.OPEN:
            time_open = (datetime.now() - self.state_change_time).total_seconds()
            self.metrics.time_in_open_state += time_open
        
        self.state = CircuitState.CLOSED
        self.state_change_time = datetime.now()
        self.failure_count = 0
        self.success_count = 0
        self.metrics.state_changes += 1
        self.metrics.last_state_change = self.state_change_time
    
    def _calculate_failure_rate(self) -> float:
        """Calculate current failure rate from sliding window."""
        if not self.metrics.recent_results:
            return 0.0
        
        failures = sum(1 for result in self.metrics.recent_results if not result)
        return failures / len(self.metrics.recent_results)
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = min(
            self.config.base_delay * (2 ** attempt),
            self.config.max_delay
        )
        
        if self.config.jitter:
            # Add random jitter (±25%)
            import random
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    def _update_response_time_metrics(self, response_time: float):
        """Update response time statistics."""
        # Update running average
        total_responses = len(self.metrics.recent_response_times)
        if total_responses == 1:
            self.metrics.avg_response_time = response_time
        else:
            # Exponential moving average
            alpha = 0.1  # Smoothing factor
            self.metrics.avg_response_time = (
                alpha * response_time + 
                (1 - alpha) * self.metrics.avg_response_time
            )
        
        # Update min/max
        self.metrics.min_response_time = min(self.metrics.min_response_time, response_time)
        self.metrics.max_response_time = max(self.metrics.max_response_time, response_time)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current circuit breaker metrics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_rate": self._calculate_failure_rate(),
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "timeouts": self.metrics.timeouts,
            "avg_response_time": self.metrics.avg_response_time,
            "min_response_time": self.metrics.min_response_time if self.metrics.min_response_time != float('inf') else 0,
            "max_response_time": self.metrics.max_response_time,
            "state_changes": self.metrics.state_changes,
            "last_state_change": self.metrics.last_state_change.isoformat() if self.metrics.last_state_change else None,
            "time_in_open_state": self.metrics.time_in_open_state
        }
    
    async def reset(self):
        """Manually reset circuit breaker to closed state."""
        async with self.lock:
            logger.info(f"Manually resetting circuit breaker '{self.name}'")
            await self._transition_to_closed()
            
            # Clear metrics
            self.metrics = CircuitBreakerMetrics()
    
    def is_closed(self) -> bool:
        """Check if circuit is in closed state."""
        return self.state == CircuitState.CLOSED
    
    def is_open(self) -> bool:
        """Check if circuit is in open state."""
        return self.state == CircuitState.OPEN
    
    def is_half_open(self) -> bool:
        """Check if circuit is in half-open state."""
        return self.state == CircuitState.HALF_OPEN


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.default_config = CircuitBreakerConfig()
    
    def get_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create circuit breaker by name."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(
                name=name,
                config=config or self.default_config
            )
        
        return self.circuit_breakers[name]
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers."""
        return {
            name: cb.get_metrics()
            for name, cb in self.circuit_breakers.items()
        }
    
    async def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            await cb.reset()
    
    def get_unhealthy_circuits(self) -> List[str]:
        """Get list of circuit breakers that are not in closed state."""
        return [
            name for name, cb in self.circuit_breakers.items()
            if not cb.is_closed()
        ]


# Global circuit breaker manager instance
circuit_breaker_manager = CircuitBreakerManager()
