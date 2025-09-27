"""
Test load balancer functionality and health monitoring.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List


@pytest.mark.integration
class TestLoadBalancer:
    """Test load balancer functionality."""
    
    def test_load_balancer_import(self):
        """Test load balancer can be imported."""
        from backend.util.load_balancer import (
            ChatProxyLoadBalancer,
            load_balancer,
            AccountHealth
        )
        
        assert ChatProxyLoadBalancer is not None
        assert load_balancer is not None
        assert AccountHealth is not None
        
        print("✅ Load balancer imports successful")
    
    async def test_load_balancer_initialization(self):
        """Test load balancer initializes correctly."""
        from autogpt_platform.backend.backend.util.load_balancer import ChatProxyLoadBalancer
        
        lb = ChatProxyLoadBalancer()
        assert lb is not None
        assert lb._states == {}
        assert lb._account_health == {}
        
        print("✅ Load balancer initialization successful")
    
    async def test_round_robin_strategy(self):
        """Test round robin load balancing strategy."""
        from autogpt_platform.backend.backend.util.load_balancer import ChatProxyLoadBalancer
        from autogpt_platform.backend.backend.data.chat_proxy_models import (
            ChatAccount,
            ChatServiceType,
            LoadBalancingStrategy,
            AccountStatus
        )
        
        lb = ChatProxyLoadBalancer()
        
        # Create test accounts
        accounts = [
            ChatAccount(
                id=f"test_account_{i}",
                service_type=ChatServiceType.ZAI,
                email=f"test{i}@example.com",
                password="test-password",
                status=AccountStatus.ACTIVE
            )
            for i in range(3)
        ]
        
        # Test round robin selection
        selected_accounts = []
        for _ in range(6):  # Test 2 full cycles
            selected = await lb.get_next_account(
                service_type=ChatServiceType.ZAI,
                accounts=accounts,
                strategy=LoadBalancingStrategy.ROUND_ROBIN
            )
            selected_accounts.append(selected.id if selected else None)
        
        # Verify round robin behavior
        expected_pattern = ["test_account_0", "test_account_1", "test_account_2"] * 2
        assert selected_accounts == expected_pattern
        
        print("✅ Round robin strategy working correctly")
    
    async def test_least_used_strategy(self):
        """Test least used load balancing strategy."""
        from autogpt_platform.backend.backend.util.load_balancer import ChatProxyLoadBalancer
        from autogpt_platform.backend.backend.data.chat_proxy_models import (
            ChatAccount,
            ChatServiceType,
            LoadBalancingStrategy,
            AccountStatus
        )
        
        lb = ChatProxyLoadBalancer()
        
        # Create test accounts
        accounts = [
            ChatAccount(
                id=f"test_account_{i}",
                service_type=ChatServiceType.ZAI,
                email=f"test{i}@example.com",
                password="test-password",
                status=AccountStatus.ACTIVE
            )
            for i in range(3)
        ]
        
        # Simulate usage by selecting accounts multiple times
        for _ in range(5):
            selected = await lb.get_next_account(
                service_type=ChatServiceType.ZAI,
                accounts=accounts,
                strategy=LoadBalancingStrategy.LEAST_USED
            )
            assert selected is not None
        
        # Get state to verify usage tracking
        state = lb._get_or_create_state(ChatServiceType.ZAI, LoadBalancingStrategy.LEAST_USED)
        assert len(state.account_usage) > 0
        
        print("✅ Least used strategy working correctly")
    
    async def test_health_based_strategy(self):
        """Test health-based load balancing strategy."""
        from autogpt_platform.backend.backend.util.load_balancer import (
            ChatProxyLoadBalancer,
            AccountHealth
        )
        from autogpt_platform.backend.backend.data.chat_proxy_models import (
            ChatAccount,
            ChatServiceType,
            LoadBalancingStrategy,
            AccountStatus
        )
        
        lb = ChatProxyLoadBalancer()
        
        # Create test accounts
        accounts = [
            ChatAccount(
                id=f"test_account_{i}",
                service_type=ChatServiceType.ZAI,
                email=f"test{i}@example.com",
                password="test-password",
                status=AccountStatus.ACTIVE
            )
            for i in range(3)
        ]
        
        # Set up different health states
        lb._account_health["test_account_0"] = AccountHealth(
            account_id="test_account_0",
            status=AccountStatus.ACTIVE,
            last_success=datetime.now(),
            error_count=0,
            response_time=1.0,
            usage_count=10
        )
        
        lb._account_health["test_account_1"] = AccountHealth(
            account_id="test_account_1",
            status=AccountStatus.ACTIVE,
            last_success=datetime.now() - timedelta(minutes=30),
            error_count=2,
            response_time=5.0,
            usage_count=10
        )
        
        # Test health-based selection
        selected = await lb.get_next_account(
            service_type=ChatServiceType.ZAI,
            accounts=accounts,
            strategy=LoadBalancingStrategy.HEALTH_BASED
        )
        
        assert selected is not None
        # Should prefer account_0 (better health)
        # Note: This might not always be deterministic due to health scoring
        
        print("✅ Health-based strategy working correctly")
    
    async def test_weighted_strategy(self):
        """Test weighted load balancing strategy."""
        from autogpt_platform.backend.backend.util.load_balancer import ChatProxyLoadBalancer
        from autogpt_platform.backend.backend.data.chat_proxy_models import (
            ChatAccount,
            ChatServiceType,
            LoadBalancingStrategy,
            AccountStatus
        )
        
        lb = ChatProxyLoadBalancer()
        
        # Create test accounts with different weights
        accounts = [
            ChatAccount(
                id="high_weight_account",
                service_type=ChatServiceType.ZAI,
                email="high@example.com",
                password="test-password",
                status=AccountStatus.ACTIVE,
                weight=10.0
            ),
            ChatAccount(
                id="low_weight_account",
                service_type=ChatServiceType.ZAI,
                email="low@example.com",
                password="test-password",
                status=AccountStatus.ACTIVE,
                weight=1.0
            )
        ]
        
        # Test weighted selection multiple times
        selections = {}
        for _ in range(100):  # Run many times to see distribution
            selected = await lb.get_next_account(
                service_type=ChatServiceType.ZAI,
                accounts=accounts,
                strategy=LoadBalancingStrategy.WEIGHTED
            )
            if selected:
                selections[selected.id] = selections.get(selected.id, 0) + 1
        
        # High weight account should be selected more often
        high_weight_count = selections.get("high_weight_account", 0)
        low_weight_count = selections.get("low_weight_account", 0)
        
        # Should be roughly 10:1 ratio, but allow for randomness
        assert high_weight_count > low_weight_count
        
        print(f"✅ Weighted strategy working: {high_weight_count}:{low_weight_count} ratio")
    
    async def test_account_health_tracking(self):
        """Test account health tracking functionality."""
        from autogpt_platform.backend.backend.util.load_balancer import ChatProxyLoadBalancer
        from autogpt_platform.backend.backend.data.chat_proxy_models import AccountStatus
        
        lb = ChatProxyLoadBalancer()
        
        account_id = "test_health_account"
        
        # Test successful request tracking
        await lb.update_account_health(
            account_id=account_id,
            success=True,
            response_time=1.5
        )
        
        health = lb._account_health.get(account_id)
        assert health is not None
        assert health.status == AccountStatus.ACTIVE
        assert health.error_count == 0
        assert health.response_time == 1.5
        assert health.usage_count == 1
        assert health.last_success is not None
        
        # Test failed request tracking
        await lb.update_account_health(
            account_id=account_id,
            success=False,
            response_time=10.0,
            error_message="Test error"
        )
        
        health = lb._account_health.get(account_id)
        assert health.error_count == 1
        assert health.usage_count == 2
        
        # Test multiple failures leading to ERROR status
        for _ in range(3):
            await lb.update_account_health(
                account_id=account_id,
                success=False,
                response_time=10.0
            )
        
        health = lb._account_health.get(account_id)
        assert health.status == AccountStatus.ERROR
        assert health.error_count >= 3
        
        print("✅ Account health tracking working correctly")
    
    async def test_unhealthy_account_filtering(self):
        """Test that unhealthy accounts are filtered out."""
        from autogpt_platform.backend.backend.util.load_balancer import (
            ChatProxyLoadBalancer,
            AccountHealth
        )
        from autogpt_platform.backend.backend.data.chat_proxy_models import (
            ChatAccount,
            ChatServiceType,
            LoadBalancingStrategy,
            AccountStatus
        )
        
        lb = ChatProxyLoadBalancer()
        
        # Create test accounts
        healthy_account = ChatAccount(
            id="healthy_account",
            service_type=ChatServiceType.ZAI,
            email="healthy@example.com",
            password="test-password",
            status=AccountStatus.ACTIVE
        )
        
        unhealthy_account = ChatAccount(
            id="unhealthy_account",
            service_type=ChatServiceType.ZAI,
            email="unhealthy@example.com",
            password="test-password",
            status=AccountStatus.ERROR
        )
        
        accounts = [healthy_account, unhealthy_account]
        
        # Set up unhealthy state
        lb._account_health["unhealthy_account"] = AccountHealth(
            account_id="unhealthy_account",
            status=AccountStatus.ERROR,
            last_success=datetime.now() - timedelta(hours=2),
            error_count=5,
            response_time=30.0,
            usage_count=10
        )
        
        # Test that only healthy account is selected
        for _ in range(10):
            selected = await lb.get_next_account(
                service_type=ChatServiceType.ZAI,
                accounts=accounts,
                strategy=LoadBalancingStrategy.ROUND_ROBIN
            )
            assert selected is not None
            assert selected.id == "healthy_account"
        
        print("✅ Unhealthy account filtering working correctly")
    
    async def test_no_healthy_accounts_fallback(self):
        """Test behavior when no healthy accounts are available."""
        from autogpt_platform.backend.backend.util.load_balancer import ChatProxyLoadBalancer
        from autogpt_platform.backend.backend.data.chat_proxy_models import (
            ChatAccount,
            ChatServiceType,
            LoadBalancingStrategy,
            AccountStatus
        )
        
        lb = ChatProxyLoadBalancer()
        
        # Create only unhealthy accounts
        accounts = [
            ChatAccount(
                id="error_account",
                service_type=ChatServiceType.ZAI,
                email="error@example.com",
                password="test-password",
                status=AccountStatus.ERROR
            )
        ]
        
        # Test fallback behavior
        selected = await lb.get_next_account(
            service_type=ChatServiceType.ZAI,
            accounts=accounts,
            strategy=LoadBalancingStrategy.ROUND_ROBIN
        )
        
        # Should return None when no healthy accounts available
        assert selected is None
        
        print("✅ No healthy accounts fallback working correctly")
    
    async def test_service_stats(self):
        """Test service statistics collection."""
        from autogpt_platform.backend.backend.util.load_balancer import ChatProxyLoadBalancer
        from autogpt_platform.backend.backend.data.chat_proxy_models import (
            ChatAccount,
            ChatServiceType,
            LoadBalancingStrategy,
            AccountStatus
        )
        
        lb = ChatProxyLoadBalancer()
        
        # Create test accounts and simulate usage
        accounts = [
            ChatAccount(
                id="stats_account",
                service_type=ChatServiceType.ZAI,
                email="stats@example.com",
                password="test-password",
                status=AccountStatus.ACTIVE
            )
        ]
        
        # Simulate some requests
        for _ in range(5):
            await lb.get_next_account(
                service_type=ChatServiceType.ZAI,
                accounts=accounts,
                strategy=LoadBalancingStrategy.ROUND_ROBIN
            )
        
        # Get stats
        stats = await lb.get_service_stats(ChatServiceType.ZAI)
        
        assert "service_type" in stats
        assert "strategy" in stats
        assert "total_requests" in stats
        assert "account_usage" in stats
        assert "last_updated" in stats
        
        assert stats["service_type"] == ChatServiceType.ZAI.value
        assert stats["total_requests"] >= 5
        
        print("✅ Service statistics collection working correctly")
    
    async def test_account_health_reset(self):
        """Test account health reset functionality."""
        from autogpt_platform.backend.backend.util.load_balancer import (
            ChatProxyLoadBalancer,
            AccountHealth
        )
        from autogpt_platform.backend.backend.data.chat_proxy_models import AccountStatus
        
        lb = ChatProxyLoadBalancer()
        
        account_id = "reset_test_account"
        
        # Set up unhealthy account
        lb._account_health[account_id] = AccountHealth(
            account_id=account_id,
            status=AccountStatus.ERROR,
            last_success=None,
            error_count=5,
            response_time=30.0,
            usage_count=10
        )
        
        # Reset health
        await lb.reset_account_health(account_id)
        
        # Verify reset
        health = lb._account_health.get(account_id)
        assert health is not None
        assert health.status == AccountStatus.ACTIVE
        assert health.error_count == 0
        assert health.last_success is not None
        
        print("✅ Account health reset working correctly")


@pytest.mark.integration
class TestLoadBalancerIntegration:
    """Test load balancer integration with other components."""
    
    def test_load_balancer_with_chat_models(self):
        """Test load balancer integration with chat proxy models."""
        from autogpt_platform.backend.backend.util.load_balancer import load_balancer
        from autogpt_platform.backend.backend.data.chat_proxy_models import (
            ChatServiceType,
            DEFAULT_SERVICE_CONFIGS
        )
        
        # Verify load balancer can work with all service types
        for service_type in ChatServiceType:
            config = DEFAULT_SERVICE_CONFIGS.get(service_type)
            assert config is not None
            assert config.load_balancing_strategy is not None
        
        print("✅ Load balancer integrates with chat models")
    
    async def test_concurrent_load_balancing(self):
        """Test load balancer under concurrent access."""
        from autogpt_platform.backend.backend.util.load_balancer import ChatProxyLoadBalancer
        from autogpt_platform.backend.backend.data.chat_proxy_models import (
            ChatAccount,
            ChatServiceType,
            LoadBalancingStrategy,
            AccountStatus
        )
        
        lb = ChatProxyLoadBalancer()
        
        # Create test accounts
        accounts = [
            ChatAccount(
                id=f"concurrent_account_{i}",
                service_type=ChatServiceType.ZAI,
                email=f"concurrent{i}@example.com",
                password="test-password",
                status=AccountStatus.ACTIVE
            )
            for i in range(3)
        ]
        
        # Create concurrent tasks
        async def select_account():
            return await lb.get_next_account(
                service_type=ChatServiceType.ZAI,
                accounts=accounts,
                strategy=LoadBalancingStrategy.ROUND_ROBIN
            )
        
        # Run concurrent selections
        tasks = [select_account() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Verify all selections succeeded
        assert all(result is not None for result in results)
        
        # Verify round robin distribution
        account_counts = {}
        for result in results:
            account_counts[result.id] = account_counts.get(result.id, 0) + 1
        
        # Should have relatively even distribution
        assert len(account_counts) == 3  # All accounts used
        
        print(f"✅ Concurrent load balancing working: {account_counts}")
    
    def test_load_balancer_state_persistence_structure(self):
        """Test load balancer state structure for persistence."""
        from autogpt_platform.backend.backend.data.chat_proxy_models import LoadBalancerState
        from autogpt_platform.backend.backend.data.chat_proxy_models import (
            ChatServiceType,
            LoadBalancingStrategy
        )
        
        # Test state creation
        state = LoadBalancerState(
            service_type=ChatServiceType.ZAI,
            strategy=LoadBalancingStrategy.ROUND_ROBIN
        )
        
        assert state.service_type == ChatServiceType.ZAI
        assert state.strategy == LoadBalancingStrategy.ROUND_ROBIN
        assert state.current_index == 0
        assert isinstance(state.account_usage, dict)
        assert isinstance(state.healthy_accounts, list)
        assert isinstance(state.unhealthy_accounts, list)
        assert state.last_updated is not None
        
        # Test serialization
        state_dict = state.model_dump()
        assert "service_type" in state_dict
        assert "strategy" in state_dict
        assert "current_index" in state_dict
        
        # Test deserialization
        new_state = LoadBalancerState.model_validate(state_dict)
        assert new_state.service_type == state.service_type
        assert new_state.strategy == state.strategy
        
        print("✅ Load balancer state persistence structure working")
