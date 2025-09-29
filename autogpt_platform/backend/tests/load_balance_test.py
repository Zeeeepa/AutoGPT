"""
Comprehensive Load Balance Test Suite for Dynamic Provider Management.

Tests all aspects of the load balancing and routing system including:
- Dynamic model routing with priority-based selection
- Provider management endpoints
- Load distribution across multiple providers
- Circuit breaker and failover functionality
- Performance benchmarking and stress testing
"""

import asyncio
import json
import logging
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

# Import the application and components
from backend.server.app import app
from backend.data.dynamic_provider_models import (
    DynamicProvider,
    ProviderStatus,
    AuthenticationMethod,
    ProviderType,
    AuthenticationConfig,
    ProviderMetrics,
    SystemConfiguration
)
from backend.util.dynamic_provider_manager import DynamicProviderManager
from backend.util.intelligent_load_balancer import IntelligentLoadBalancer


# Test configuration
TEST_CONFIG = {
    "base_url": "http://localhost:8000",
    "timeout": 30,
    "max_concurrent_requests": 50,
    "test_duration_seconds": 60,
    "provider_count": 5,
    "models_to_test": [
        "z.ai", "k2", "qwen", "deepseek", "grok",  # Exact matches
        "custom-chat", "unknown-model", "gpt-4.1",  # Fallback tests
        "chatgpt", "claude", "gemini"  # Partial matches
    ]
}

# Test client
client = TestClient(app)

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LoadBalanceTestSuite:
    """Comprehensive test suite for load balancing functionality"""
    
    def __init__(self):
        self.test_results = {
            "routing_tests": [],
            "load_balance_tests": [],
            "performance_tests": [],
            "failover_tests": [],
            "provider_management_tests": []
        }
        self.test_providers = []
        self.start_time = None
        
    async def setup_test_environment(self):
        """Set up test environment with mock providers"""
        logger.info("Setting up test environment...")
        
        # Create test providers
        for i in range(TEST_CONFIG["provider_count"]):
            provider_data = {
                "name": f"Test Provider {i+1}",
                "base_url": f"https://testprovider{i+1}.com",
                "auth_method": "email_password",
                "email": f"test{i+1}@example.com",
                "password": "test_password",
                "supported_models": [f"test-model-{i+1}", f"provider-{i+1}"],
                "is_enabled": True,
                "auto_authenticate": False
            }
            
            response = client.post(
                "/api/dynamic-providers/providers",
                json=provider_data
            )
            
            if response.status_code == 201:
                provider = response.json()
                self.test_providers.append(provider)
                logger.info(f"Created test provider: {provider['name']}")
            else:
                logger.error(f"Failed to create test provider {i+1}: {response.text}")
    
    async def cleanup_test_environment(self):
        """Clean up test environment"""
        logger.info("Cleaning up test environment...")
        
        for provider in self.test_providers:
            response = client.delete(f"/api/dynamic-providers/providers/{provider['id']}")
            if response.status_code == 200:
                logger.info(f"Deleted test provider: {provider['name']}")
            else:
                logger.warning(f"Failed to delete provider {provider['id']}: {response.text}")
    
    def test_model_routing_logic(self):
        """Test the dynamic model routing system"""
        logger.info("Testing model routing logic...")
        
        routing_tests = [
            # Exact match tests
            {"model": "z.ai", "expected_type": "exact_match", "description": "Z.AI exact match"},
            {"model": "k2", "expected_type": "exact_match", "description": "K2Think exact match"},
            {"model": "qwen", "expected_type": "exact_match", "description": "Qwen exact match"},
            
            # Provider name matching tests
            {"model": "test-provider-1", "expected_type": "name_match", "description": "Provider name match"},
            
            # Default fallback tests
            {"model": "unknown-model", "expected_type": "default_fallback", "description": "Unknown model fallback"},
            {"model": "gpt-4.1", "expected_type": "default_fallback", "description": "GPT-4.1 fallback"},
            
            # Partial matching tests
            {"model": "custom-chat", "expected_type": "partial_match", "description": "Partial model match"},
        ]
        
        results = []
        for test_case in routing_tests:
            try:
                # Test chat completions endpoint
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": test_case["model"],
                        "messages": [{"role": "user", "content": "Test routing"}],
                        "max_tokens": 10
                    },
                    timeout=TEST_CONFIG["timeout"]
                )
                
                result = {
                    "model": test_case["model"],
                    "description": test_case["description"],
                    "expected_type": test_case["expected_type"],
                    "status_code": response.status_code,
                    "success": response.status_code in [200, 202],
                    "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0,
                    "error": None if response.status_code in [200, 202] else response.text
                }
                
                results.append(result)
                logger.info(f"Routing test '{test_case['description']}': {'PASS' if result['success'] else 'FAIL'}")
                
            except Exception as e:
                result = {
                    "model": test_case["model"],
                    "description": test_case["description"],
                    "expected_type": test_case["expected_type"],
                    "status_code": 0,
                    "success": False,
                    "response_time": 0,
                    "error": str(e)
                }
                results.append(result)
                logger.error(f"Routing test '{test_case['description']}' failed: {e}")
        
        self.test_results["routing_tests"] = results
        return results
    
    def test_provider_management_endpoints(self):
        """Test all provider management REST endpoints"""
        logger.info("Testing provider management endpoints...")
        
        endpoint_tests = [
            # List providers
            {
                "method": "GET",
                "endpoint": "/api/dynamic-providers/providers",
                "description": "List all providers"
            },
            
            # Get system config
            {
                "method": "GET", 
                "endpoint": "/api/dynamic-providers/system/config",
                "description": "Get system configuration"
            },
            
            # Get model mappings
            {
                "method": "GET",
                "endpoint": "/api/dynamic-providers/models/mappings", 
                "description": "Get model mappings"
            },
            
            # Health check
            {
                "method": "GET",
                "endpoint": "/v1/health",
                "description": "Health check endpoint"
            },
            
            # Get models
            {
                "method": "GET",
                "endpoint": "/v1/models",
                "description": "Get available models"
            },
            
            # Get stats
            {
                "method": "GET",
                "endpoint": "/v1/stats",
                "description": "Get system statistics"
            }
        ]
        
        results = []
        for test_case in endpoint_tests:
            try:
                if test_case["method"] == "GET":
                    response = client.get(test_case["endpoint"])
                elif test_case["method"] == "POST":
                    response = client.post(test_case["endpoint"], json=test_case.get("data", {}))
                elif test_case["method"] == "PUT":
                    response = client.put(test_case["endpoint"], json=test_case.get("data", {}))
                elif test_case["method"] == "DELETE":
                    response = client.delete(test_case["endpoint"])
                
                result = {
                    "endpoint": test_case["endpoint"],
                    "method": test_case["method"],
                    "description": test_case["description"],
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                    "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0,
                    "response_size": len(response.content) if response.content else 0
                }
                
                results.append(result)
                logger.info(f"Endpoint test '{test_case['description']}': {'PASS' if result['success'] else 'FAIL'}")
                
            except Exception as e:
                result = {
                    "endpoint": test_case["endpoint"],
                    "method": test_case["method"],
                    "description": test_case["description"],
                    "status_code": 0,
                    "success": False,
                    "response_time": 0,
                    "response_size": 0,
                    "error": str(e)
                }
                results.append(result)
                logger.error(f"Endpoint test '{test_case['description']}' failed: {e}")
        
        self.test_results["provider_management_tests"] = results
        return results
    
    def test_load_distribution(self, num_requests: int = 100):
        """Test load distribution across providers"""
        logger.info(f"Testing load distribution with {num_requests} requests...")
        
        # Track which providers handle requests
        provider_usage = {}
        response_times = []
        success_count = 0
        
        def make_request(request_id: int) -> Dict[str, Any]:
            """Make a single request and track results"""
            try:
                model = random.choice(TEST_CONFIG["models_to_test"])
                start_time = time.time()
                
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": f"Load test request {request_id}"}],
                        "max_tokens": 10
                    },
                    timeout=TEST_CONFIG["timeout"]
                )
                
                response_time = time.time() - start_time
                
                return {
                    "request_id": request_id,
                    "model": model,
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "success": response.status_code in [200, 202],
                    "provider_id": response.headers.get("X-Provider-ID", "unknown"),
                    "error": None if response.status_code in [200, 202] else response.text
                }
                
            except Exception as e:
                return {
                    "request_id": request_id,
                    "model": model,
                    "status_code": 0,
                    "response_time": time.time() - start_time,
                    "success": False,
                    "provider_id": "error",
                    "error": str(e)
                }
        
        # Execute requests concurrently
        with ThreadPoolExecutor(max_workers=TEST_CONFIG["max_concurrent_requests"]) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            
            for future in as_completed(futures):
                result = future.result()
                
                # Track provider usage
                provider_id = result["provider_id"]
                if provider_id not in provider_usage:
                    provider_usage[provider_id] = 0
                provider_usage[provider_id] += 1
                
                # Track metrics
                if result["success"]:
                    success_count += 1
                    response_times.append(result["response_time"])
        
        # Calculate statistics
        success_rate = (success_count / num_requests) * 100
        avg_response_time = statistics.mean(response_times) if response_times else 0
        median_response_time = statistics.median(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0
        
        # Check load distribution balance
        if len(provider_usage) > 1:
            usage_values = list(provider_usage.values())
            usage_std_dev = statistics.stdev(usage_values)
            usage_mean = statistics.mean(usage_values)
            balance_coefficient = usage_std_dev / usage_mean if usage_mean > 0 else 1
        else:
            balance_coefficient = 0
        
        load_test_result = {
            "total_requests": num_requests,
            "successful_requests": success_count,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "median_response_time": median_response_time,
            "p95_response_time": p95_response_time,
            "provider_usage": provider_usage,
            "balance_coefficient": balance_coefficient,
            "load_balanced": balance_coefficient < 0.3  # Good balance if std dev < 30% of mean
        }
        
        self.test_results["load_balance_tests"].append(load_test_result)
        
        logger.info(f"Load distribution test completed:")
        logger.info(f"  Success rate: {success_rate:.2f}%")
        logger.info(f"  Avg response time: {avg_response_time:.3f}s")
        logger.info(f"  Load balance coefficient: {balance_coefficient:.3f}")
        logger.info(f"  Provider usage: {provider_usage}")
        
        return load_test_result
    
    def test_circuit_breaker_and_failover(self):
        """Test circuit breaker functionality and failover behavior"""
        logger.info("Testing circuit breaker and failover...")
        
        # Test scenarios for circuit breaker
        failover_tests = [
            {
                "description": "Provider failure simulation",
                "test_type": "provider_failure",
                "failure_rate": 0.8  # 80% failure rate to trigger circuit breaker
            },
            {
                "description": "High latency simulation", 
                "test_type": "high_latency",
                "latency_threshold": 10.0  # 10 second timeout
            },
            {
                "description": "Provider recovery test",
                "test_type": "recovery_test",
                "recovery_time": 30  # 30 seconds recovery time
            }
        ]
        
        results = []
        for test_case in failover_tests:
            try:
                logger.info(f"Running failover test: {test_case['description']}")
                
                # Simulate different failure scenarios
                if test_case["test_type"] == "provider_failure":
                    result = self._simulate_provider_failures(test_case["failure_rate"])
                elif test_case["test_type"] == "high_latency":
                    result = self._simulate_high_latency(test_case["latency_threshold"])
                elif test_case["test_type"] == "recovery_test":
                    result = self._simulate_provider_recovery(test_case["recovery_time"])
                
                result["description"] = test_case["description"]
                result["test_type"] = test_case["test_type"]
                results.append(result)
                
                logger.info(f"Failover test '{test_case['description']}': {'PASS' if result.get('success', False) else 'FAIL'}")
                
            except Exception as e:
                result = {
                    "description": test_case["description"],
                    "test_type": test_case["test_type"],
                    "success": False,
                    "error": str(e)
                }
                results.append(result)
                logger.error(f"Failover test '{test_case['description']}' failed: {e}")
        
        self.test_results["failover_tests"] = results
        return results
    
    def _simulate_provider_failures(self, failure_rate: float) -> Dict[str, Any]:
        """Simulate provider failures to test circuit breaker"""
        num_requests = 50
        failed_requests = 0
        circuit_breaker_triggered = False
        
        for i in range(num_requests):
            try:
                # Simulate failure by using invalid model that should fail
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "failing-provider-test",
                        "messages": [{"role": "user", "content": f"Failure test {i}"}],
                        "max_tokens": 10
                    },
                    timeout=5
                )
                
                if response.status_code >= 500:
                    failed_requests += 1
                
                # Check if circuit breaker is triggered (indicated by specific error codes)
                if response.status_code == 503 and "circuit breaker" in response.text.lower():
                    circuit_breaker_triggered = True
                    
            except Exception:
                failed_requests += 1
        
        actual_failure_rate = failed_requests / num_requests
        
        return {
            "total_requests": num_requests,
            "failed_requests": failed_requests,
            "actual_failure_rate": actual_failure_rate,
            "expected_failure_rate": failure_rate,
            "circuit_breaker_triggered": circuit_breaker_triggered,
            "success": circuit_breaker_triggered or actual_failure_rate >= failure_rate * 0.8
        }
    
    def _simulate_high_latency(self, latency_threshold: float) -> Dict[str, Any]:
        """Simulate high latency to test timeout handling"""
        num_requests = 10
        timeout_count = 0
        
        for i in range(num_requests):
            try:
                start_time = time.time()
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "slow-provider-test",
                        "messages": [{"role": "user", "content": f"Latency test {i}"}],
                        "max_tokens": 10
                    },
                    timeout=latency_threshold
                )
                response_time = time.time() - start_time
                
                if response_time >= latency_threshold * 0.9:  # Close to timeout
                    timeout_count += 1
                    
            except Exception:
                timeout_count += 1
        
        return {
            "total_requests": num_requests,
            "timeout_count": timeout_count,
            "timeout_rate": timeout_count / num_requests,
            "latency_threshold": latency_threshold,
            "success": timeout_count > 0  # At least some timeouts expected
        }
    
    def _simulate_provider_recovery(self, recovery_time: int) -> Dict[str, Any]:
        """Simulate provider recovery after failure"""
        # First, cause some failures
        failure_result = self._simulate_provider_failures(0.9)
        
        # Wait for recovery time
        logger.info(f"Waiting {recovery_time} seconds for provider recovery...")
        time.sleep(recovery_time)
        
        # Test if providers have recovered
        recovery_requests = 20
        success_count = 0
        
        for i in range(recovery_requests):
            try:
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "z.ai",  # Use known good model
                        "messages": [{"role": "user", "content": f"Recovery test {i}"}],
                        "max_tokens": 10
                    },
                    timeout=10
                )
                
                if response.status_code in [200, 202]:
                    success_count += 1
                    
            except Exception:
                pass
        
        recovery_rate = success_count / recovery_requests
        
        return {
            "recovery_time": recovery_time,
            "recovery_requests": recovery_requests,
            "successful_recoveries": success_count,
            "recovery_rate": recovery_rate,
            "success": recovery_rate > 0.5  # At least 50% recovery expected
        }
    
    def test_performance_benchmarks(self):
        """Run performance benchmarks and stress tests"""
        logger.info("Running performance benchmarks...")
        
        benchmark_tests = [
            {"name": "Light Load", "concurrent_users": 10, "requests_per_user": 10, "duration": 30},
            {"name": "Medium Load", "concurrent_users": 25, "requests_per_user": 20, "duration": 60},
            {"name": "Heavy Load", "concurrent_users": 50, "requests_per_user": 30, "duration": 120},
            {"name": "Stress Test", "concurrent_users": 100, "requests_per_user": 50, "duration": 180}
        ]
        
        results = []
        for test_case in benchmark_tests:
            logger.info(f"Running benchmark: {test_case['name']}")
            
            try:
                result = self._run_performance_benchmark(
                    concurrent_users=test_case["concurrent_users"],
                    requests_per_user=test_case["requests_per_user"],
                    duration=test_case["duration"]
                )
                
                result["name"] = test_case["name"]
                results.append(result)
                
                logger.info(f"Benchmark '{test_case['name']}' completed:")
                logger.info(f"  Total requests: {result['total_requests']}")
                logger.info(f"  Success rate: {result['success_rate']:.2f}%")
                logger.info(f"  Avg response time: {result['avg_response_time']:.3f}s")
                logger.info(f"  Throughput: {result['throughput']:.2f} req/s")
                
            except Exception as e:
                result = {
                    "name": test_case["name"],
                    "success": False,
                    "error": str(e)
                }
                results.append(result)
                logger.error(f"Benchmark '{test_case['name']}' failed: {e}")
        
        self.test_results["performance_tests"] = results
        return results
    
    def _run_performance_benchmark(self, concurrent_users: int, requests_per_user: int, duration: int) -> Dict[str, Any]:
        """Run a single performance benchmark"""
        total_requests = concurrent_users * requests_per_user
        start_time = time.time()
        
        # Track metrics
        response_times = []
        success_count = 0
        error_count = 0
        provider_usage = {}
        
        def user_simulation(user_id: int) -> List[Dict[str, Any]]:
            """Simulate a single user making multiple requests"""
            user_results = []
            
            for request_id in range(requests_per_user):
                try:
                    model = random.choice(TEST_CONFIG["models_to_test"])
                    request_start = time.time()
                    
                    response = client.post(
                        "/v1/chat/completions",
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": f"Benchmark request {user_id}-{request_id}"}],
                            "max_tokens": 10
                        },
                        timeout=TEST_CONFIG["timeout"]
                    )
                    
                    request_time = time.time() - request_start
                    
                    user_results.append({
                        "user_id": user_id,
                        "request_id": request_id,
                        "model": model,
                        "response_time": request_time,
                        "status_code": response.status_code,
                        "success": response.status_code in [200, 202],
                        "provider_id": response.headers.get("X-Provider-ID", "unknown")
                    })
                    
                    # Stop if duration exceeded
                    if time.time() - start_time > duration:
                        break
                        
                except Exception as e:
                    user_results.append({
                        "user_id": user_id,
                        "request_id": request_id,
                        "model": model,
                        "response_time": 0,
                        "status_code": 0,
                        "success": False,
                        "error": str(e),
                        "provider_id": "error"
                    })
            
            return user_results
        
        # Execute concurrent user simulations
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(user_simulation, user_id) for user_id in range(concurrent_users)]
            
            for future in as_completed(futures):
                user_results = future.result()
                
                for result in user_results:
                    if result["success"]:
                        success_count += 1
                        response_times.append(result["response_time"])
                    else:
                        error_count += 1
                    
                    # Track provider usage
                    provider_id = result["provider_id"]
                    if provider_id not in provider_usage:
                        provider_usage[provider_id] = 0
                    provider_usage[provider_id] += 1
        
        # Calculate final metrics
        end_time = time.time()
        total_duration = end_time - start_time
        actual_requests = success_count + error_count
        
        success_rate = (success_count / actual_requests) * 100 if actual_requests > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        median_response_time = statistics.median(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) > 100 else 0
        throughput = actual_requests / total_duration if total_duration > 0 else 0
        
        return {
            "concurrent_users": concurrent_users,
            "requests_per_user": requests_per_user,
            "planned_duration": duration,
            "actual_duration": total_duration,
            "total_requests": actual_requests,
            "successful_requests": success_count,
            "failed_requests": error_count,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "median_response_time": median_response_time,
            "p95_response_time": p95_response_time,
            "p99_response_time": p99_response_time,
            "throughput": throughput,
            "provider_usage": provider_usage,
            "success": success_rate > 90 and avg_response_time < 5.0  # Success criteria
        }
    
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        logger.info("Generating test report...")
        
        # Calculate overall statistics
        total_tests = sum(len(tests) for tests in self.test_results.values())
        passed_tests = 0
        failed_tests = 0
        
        for test_category, tests in self.test_results.items():
            for test in tests:
                if test.get("success", False):
                    passed_tests += 1
                else:
                    failed_tests += 1
        
        overall_success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": overall_success_rate,
                "test_duration": time.time() - self.start_time if self.start_time else 0
            },
            "test_results": self.test_results,
            "recommendations": self._generate_recommendations(),
            "generated_at": datetime.now().isoformat()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check routing tests
        routing_failures = [t for t in self.test_results.get("routing_tests", []) if not t.get("success", False)]
        if routing_failures:
            recommendations.append(f"Fix {len(routing_failures)} routing test failures - check model mapping configuration")
        
        # Check load balance tests
        load_tests = self.test_results.get("load_balance_tests", [])
        if load_tests:
            unbalanced_tests = [t for t in load_tests if not t.get("load_balanced", True)]
            if unbalanced_tests:
                recommendations.append("Improve load balancing - some providers are receiving disproportionate traffic")
        
        # Check performance tests
        perf_tests = self.test_results.get("performance_tests", [])
        slow_tests = [t for t in perf_tests if t.get("avg_response_time", 0) > 3.0]
        if slow_tests:
            recommendations.append("Optimize response times - some tests show high latency")
        
        # Check failover tests
        failover_failures = [t for t in self.test_results.get("failover_tests", []) if not t.get("success", False)]
        if failover_failures:
            recommendations.append("Improve failover mechanisms - circuit breaker may not be working correctly")
        
        if not recommendations:
            recommendations.append("All tests passed - system is performing well")
        
        return recommendations


# Test execution functions
async def run_comprehensive_load_balance_tests():
    """Run the complete load balance test suite"""
    logger.info("Starting comprehensive load balance tests...")
    
    test_suite = LoadBalanceTestSuite()
    test_suite.start_time = time.time()
    
    try:
        # Setup test environment
        await test_suite.setup_test_environment()
        
        # Run all test categories
        logger.info("=" * 60)
        logger.info("RUNNING MODEL ROUTING TESTS")
        logger.info("=" * 60)
        test_suite.test_model_routing_logic()
        
        logger.info("=" * 60)
        logger.info("RUNNING PROVIDER MANAGEMENT TESTS")
        logger.info("=" * 60)
        test_suite.test_provider_management_endpoints()
        
        logger.info("=" * 60)
        logger.info("RUNNING LOAD DISTRIBUTION TESTS")
        logger.info("=" * 60)
        test_suite.test_load_distribution(num_requests=200)
        
        logger.info("=" * 60)
        logger.info("RUNNING CIRCUIT BREAKER AND FAILOVER TESTS")
        logger.info("=" * 60)
        test_suite.test_circuit_breaker_and_failover()
        
        logger.info("=" * 60)
        logger.info("RUNNING PERFORMANCE BENCHMARKS")
        logger.info("=" * 60)
        test_suite.test_performance_benchmarks()
        
        # Generate final report
        logger.info("=" * 60)
        logger.info("GENERATING TEST REPORT")
        logger.info("=" * 60)
        report = test_suite.generate_test_report()
        
        # Save report to file
        report_filename = f"load_balance_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Test report saved to: {report_filename}")
        logger.info(f"Overall success rate: {report['test_summary']['success_rate']:.2f}%")
        
        # Print recommendations
        logger.info("RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            logger.info(f"  - {rec}")
        
        return report
        
    finally:
        # Cleanup test environment
        await test_suite.cleanup_test_environment()


# Main execution
if __name__ == "__main__":
    # Run the comprehensive test suite
    asyncio.run(run_comprehensive_load_balance_tests())
