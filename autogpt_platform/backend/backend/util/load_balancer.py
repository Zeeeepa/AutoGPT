"""
Load balancer for chat proxy accounts.
Implements multiple strategies for distributing requests across available accounts.
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from backend.data.chat_proxy_models import (
    ChatAccount,
    ChatServiceType,
    AccountStatus,
    LoadBalancingStrategy,
    LoadBalancerState,
)
from backend.data import redis_client as redis

logger = logging.getLogger(__name__)


@dataclass
class AccountHealth:
    """Health information for an account"""
    account_id: str
    status: AccountStatus
    last_success: Optional[datetime]
    error_count: int
    response_time: float
    usage_count: int


class ChatProxyLoadBalancer:
    """
    Load balancer for chat proxy accounts with multiple strategies.
    Handles account selection, health monitoring, and usage tracking.
    """
    
    def __init__(self):
        self._states: Dict[ChatServiceType, LoadBalancerState] = {}
        self._account_health: Dict[str, AccountHealth] = {}
        self._lock = asyncio.Lock()
        
    async def get_next_account(
        self,
        service_type: ChatServiceType,
        accounts: List[ChatAccount],
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    ) -> Optional[ChatAccount]:
        """
        Get the next account to use based on the load balancing strategy.
        
        Args:
            service_type: The chat service type
            accounts: List of available accounts for the service
            strategy: Load balancing strategy to use
            
        Returns:
            Selected account or None if no healthy accounts available
        """
        async with self._lock:
            if not accounts:
                logger.warning(f"No accounts available for {service_type}")
                return None
                
            # Filter healthy accounts
            healthy_accounts = [
                acc for acc in accounts 
                if acc.status == AccountStatus.ACTIVE and self._is_account_healthy(acc.id)
            ]
            
            if not healthy_accounts:
                logger.warning(f"No healthy accounts available for {service_type}")
                # Try to use any available account as fallback
                healthy_accounts = [acc for acc in accounts if acc.status != AccountStatus.ERROR]
                if not healthy_accounts:
                    return None
                    
            # Get or create load balancer state
            state = self._get_or_create_state(service_type, strategy)
            
            # Select account based on strategy
            if strategy == LoadBalancingStrategy.ROUND_ROBIN:
                selected = self._round_robin_select(healthy_accounts, state)
            elif strategy == LoadBalancingStrategy.LEAST_USED:
                selected = self._least_used_select(healthy_accounts, state)
            elif strategy == LoadBalancingStrategy.HEALTH_BASED:
                selected = self._health_based_select(healthy_accounts, state)
            elif strategy == LoadBalancingStrategy.WEIGHTED:
                selected = self._weighted_select(healthy_accounts, state)
            else:
                selected = self._round_robin_select(healthy_accounts, state)
                
            if selected:
                # Update usage tracking
                state.account_usage[selected.id] = state.account_usage.get(selected.id, 0) + 1
                state.last_updated = datetime.now()
                
                # Store state in Redis for persistence
                await self._store_state(service_type, state)
                
                logger.info(f"Selected account {selected.id} for {service_type} using {strategy}")
                
            return selected
            
    def _round_robin_select(self, accounts: List[ChatAccount], state: LoadBalancerState) -> ChatAccount:
        """Round robin selection"""
        if state.current_index >= len(accounts):
            state.current_index = 0
            
        selected = accounts[state.current_index]
        state.current_index = (state.current_index + 1) % len(accounts)
        return selected
        
    def _least_used_select(self, accounts: List[ChatAccount], state: LoadBalancerState) -> ChatAccount:
        """Select account with least usage"""
        return min(accounts, key=lambda acc: state.account_usage.get(acc.id, 0))
        
    def _health_based_select(self, accounts: List[ChatAccount], state: LoadBalancerState) -> ChatAccount:
        """Select account based on health score"""
        def health_score(account: ChatAccount) -> float:
            health = self._account_health.get(account.id)
            if not health:
                return 0.5  # Default score for unknown health
                
            # Calculate score based on error rate and response time
            error_rate = health.error_count / max(health.usage_count, 1)
            response_score = max(0, 1 - (health.response_time / 10.0))  # Normalize to 10s max
            health_score = (1 - error_rate) * 0.7 + response_score * 0.3
            
            return health_score
            
        return max(accounts, key=health_score)
        
    def _weighted_select(self, accounts: List[ChatAccount], state: LoadBalancerState) -> ChatAccount:
        """Weighted random selection based on account weights"""
        weights = [acc.weight for acc in accounts]
        total_weight = sum(weights)
        
        if total_weight == 0:
            return random.choice(accounts)
            
        # Weighted random selection
        r = random.uniform(0, total_weight)
        cumulative = 0
        
        for i, weight in enumerate(weights):
            cumulative += weight
            if r <= cumulative:
                return accounts[i]
                
        return accounts[-1]  # Fallback
        
    def _is_account_healthy(self, account_id: str) -> bool:
        """Check if an account is considered healthy"""
        health = self._account_health.get(account_id)
        if not health:
            return True  # Assume healthy if no data
            
        # Consider unhealthy if too many recent errors
        if health.error_count >= 3:
            return False
            
        # Consider unhealthy if last success was too long ago
        if health.last_success:
            time_since_success = datetime.now() - health.last_success
            if time_since_success > timedelta(hours=1):
                return False
                
        return True
        
    def _get_or_create_state(
        self, 
        service_type: ChatServiceType, 
        strategy: LoadBalancingStrategy
    ) -> LoadBalancerState:
        """Get or create load balancer state for a service"""
        if service_type not in self._states:
            self._states[service_type] = LoadBalancerState(
                service_type=service_type,
                strategy=strategy
            )
        return self._states[service_type]
        
    async def _store_state(self, service_type: ChatServiceType, state: LoadBalancerState):
        """Store load balancer state in Redis"""
        try:
            key = f"chat_proxy:lb_state:{service_type.value}"
            data = state.model_dump_json()
            await redis.set(key, data, ex=3600)  # Expire after 1 hour
        except Exception as e:
            logger.error(f"Failed to store load balancer state: {e}")
            
    async def _load_state(self, service_type: ChatServiceType) -> Optional[LoadBalancerState]:
        """Load load balancer state from Redis"""
        try:
            key = f"chat_proxy:lb_state:{service_type.value}"
            data = await redis.get(key)
            if data:
                return LoadBalancerState.model_validate_json(data)
        except Exception as e:
            logger.error(f"Failed to load load balancer state: {e}")
        return None
        
    async def update_account_health(
        self,
        account_id: str,
        success: bool,
        response_time: float = 0.0,
        error_message: Optional[str] = None
    ):
        """Update health information for an account"""
        async with self._lock:
            health = self._account_health.get(account_id)
            if not health:
                health = AccountHealth(
                    account_id=account_id,
                    status=AccountStatus.ACTIVE,
                    last_success=None,
                    error_count=0,
                    response_time=0.0,
                    usage_count=0
                )
                self._account_health[account_id] = health
                
            health.usage_count += 1
            
            if success:
                health.last_success = datetime.now()
                health.error_count = max(0, health.error_count - 1)  # Reduce error count on success
                health.status = AccountStatus.ACTIVE
            else:
                health.error_count += 1
                if health.error_count >= 3:
                    health.status = AccountStatus.ERROR
                    logger.warning(f"Account {account_id} marked as ERROR due to {health.error_count} consecutive errors")
                    
            # Update response time with exponential moving average
            if response_time > 0:
                if health.response_time == 0:
                    health.response_time = response_time
                else:
                    health.response_time = health.response_time * 0.8 + response_time * 0.2
                    
            # Store health data in Redis
            await self._store_account_health(account_id, health)
            
    async def _store_account_health(self, account_id: str, health: AccountHealth):
        """Store account health in Redis"""
        try:
            key = f"chat_proxy:account_health:{account_id}"
            data = {
                "account_id": health.account_id,
                "status": health.status.value,
                "last_success": health.last_success.isoformat() if health.last_success else None,
                "error_count": health.error_count,
                "response_time": health.response_time,
                "usage_count": health.usage_count,
            }
            await redis.set(key, json.dumps(data), ex=86400)  # Expire after 24 hours
        except Exception as e:
            logger.error(f"Failed to store account health: {e}")
            
    async def get_service_stats(self, service_type: ChatServiceType) -> Dict:
        """Get statistics for a service"""
        state = self._states.get(service_type)
        if not state:
            return {"error": "No state found for service"}
            
        total_usage = sum(state.account_usage.values())
        healthy_count = len(state.healthy_accounts)
        unhealthy_count = len(state.unhealthy_accounts)
        
        return {
            "service_type": service_type.value,
            "strategy": state.strategy.value,
            "total_requests": total_usage,
            "healthy_accounts": healthy_count,
            "unhealthy_accounts": unhealthy_count,
            "account_usage": state.account_usage,
            "last_updated": state.last_updated.isoformat()
        }
        
    async def reset_account_health(self, account_id: str):
        """Reset health status for an account"""
        async with self._lock:
            if account_id in self._account_health:
                health = self._account_health[account_id]
                health.error_count = 0
                health.status = AccountStatus.ACTIVE
                health.last_success = datetime.now()
                
                await self._store_account_health(account_id, health)
                logger.info(f"Reset health for account {account_id}")


# Global load balancer instance
load_balancer = ChatProxyLoadBalancer()
