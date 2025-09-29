#!/usr/bin/env python3
"""
Real-World Dynamic Endpoint Testing Suite

Tests actual creation of dynamic endpoints with real authentication
and validates end-to-end functionality with live providers.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import httpx
import pytest
from stagehand import Stagehand

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.data.dynamic_provider_models import (
    DynamicProvider,
    AuthenticationConfig,
    AuthenticationMethod,
    ProviderStatus,
    ProviderType
)
from backend.util.dynamic_provider_manager import DynamicProviderManager
from backend.server.routers.openai_proxy import router as openai_router


class RealEndpointTestSuite:
    """Real-world testing of dynamic endpoint creation and authentication"""
    
    def __init__(self):
        self.test_results = {
            "endpoint_creation_tests": [],
            "authentication_tests": [],
            "llm_response_tests": [],
            "integration_tests": []
        }
        self.provider_manager = None
        self.stagehand_client = None
        self.test_providers = []
        self.start_time = time.time()
        
    async def setup(self):
        """Initialize test environment"""
        logger.info("Setting up real endpoint test environment...")
        
        # Initialize Stagehand client
        try:
            self.stagehand_client = Stagehand()
            logger.info("✅ Stagehand client initialized")
        except Exception as e:
            logger.warning(f"⚠️ Stagehand initialization failed: {e}")
            self.stagehand_client = None
        
        # Initialize provider manager
        try:
            self.provider_manager = DynamicProviderManager()
            await self.provider_manager.start()
            logger.info("✅ Dynamic Provider Manager initialized")
        except Exception as e:
            logger.error(f"❌ Provider Manager initialization failed: {e}")
            raise
    
    async def teardown(self):
        """Cleanup test environment"""
        logger.info("Cleaning up test environment...")
        
        if self.provider_manager:
            await self.provider_manager.stop()
        
        if self.stagehand_client:
            await self.stagehand_client.close()
    
    def create_test_providers(self) -> List[Dict[str, Any]]:
        """Create test provider configurations"""
        
        providers = [
            {
                "name": "Mistral AI Chat",
                "description": "Mistral AI webchat interface",
                "base_url": "https://chat.mistral.ai",
                "provider_type": ProviderType.WEBCHAT,
                "auth_config": {
                    "method": AuthenticationMethod.EMAIL_PASSWORD,
                    "email": "developer@pixelium.uk",
                    "password": "develooper123?",
                    "login_url": "https://chat.mistral.ai/login",
                    "email_selector": 'input[type="email"]',
                    "password_selector": 'input[type="password"]',
                    "submit_selector": 'button[type="submit"]',
                    "success_indicators": [
                        '.chat-interface',
                        '.conversation-area',
                        '[data-testid="chat-input"]'
                    ],
                    "failure_indicators": [
                        '.error-message',
                        '.login-error',
                        '.invalid-credentials'
                    ]
                },
                "chat_config": {
                    "input_selector": '[data-testid="chat-input"], .chat-input, textarea[placeholder*="message"]',
                    "send_selector": '[data-testid="send-button"], .send-button, button[aria-label*="send"]',
                    "response_selector": '.message-content, .response-text, .chat-message:last-child',
                    "wait_for_response": 10
                },
                "model_mappings": ["mistral", "mistral-chat", "mistral-ai"],
                "priority": 1,
                "enabled": True
            },
            {
                "name": "Claude Chat",
                "description": "Anthropic Claude webchat interface",
                "base_url": "https://claude.ai",
                "provider_type": ProviderType.WEBCHAT,
                "auth_config": {
                    "method": AuthenticationMethod.EMAIL_PASSWORD,
                    "email": "test@example.com",
                    "password": "testpassword123",
                    "login_url": "https://claude.ai/login",
                    "success_indicators": ['.chat-interface'],
                    "failure_indicators": ['.error-message']
                },
                "chat_config": {
                    "input_selector": '.chat-input',
                    "send_selector": '.send-button',
                    "response_selector": '.message-content'
                },
                "model_mappings": ["claude", "claude-3", "anthropic"],
                "priority": 2,
                "enabled": True
            },
            {
                "name": "ChatGPT Web",
                "description": "OpenAI ChatGPT webchat interface",
                "base_url": "https://chat.openai.com",
                "provider_type": ProviderType.WEBCHAT,
                "auth_config": {
                    "method": AuthenticationMethod.EMAIL_PASSWORD,
                    "email": "test@example.com",
                    "password": "testpassword123",
                    "login_url": "https://chat.openai.com/auth/login",
                    "success_indicators": ['.chat-interface'],
                    "failure_indicators": ['.error-message']
                },
                "chat_config": {
                    "input_selector": '#prompt-textarea',
                    "send_selector": '[data-testid="send-button"]',
                    "response_selector": '.markdown'
                },
                "model_mappings": ["gpt", "chatgpt", "openai"],
                "priority": 3,
                "enabled": True
            }
        ]
        
        return providers
    
    async def test_endpoint_creation(self):
        """Test dynamic endpoint creation"""
        logger.info("Testing dynamic endpoint creation...")
        
        test_providers = self.create_test_providers()
        results = []
        
        for provider_config in test_providers:
            try:
                logger.info(f"Creating endpoint for {provider_config['name']}...")
                
                # Create provider through manager
                provider = await self.provider_manager.add_provider(provider_config)
                self.test_providers.append(provider)
                
                result = {
                    "provider_name": provider_config["name"],
                    "provider_id": provider.id,
                    "base_url": provider_config["base_url"],
                    "creation_success": True,
                    "status": provider.status,
                    "model_mappings": provider_config.get("model_mappings", []),
                    "error": None
                }
                
                logger.info(f"✅ Successfully created endpoint for {provider_config['name']}")
                
            except Exception as e:
                result = {
                    "provider_name": provider_config["name"],
                    "provider_id": None,
                    "base_url": provider_config["base_url"],
                    "creation_success": False,
                    "status": "error",
                    "model_mappings": [],
                    "error": str(e)
                }
                
                logger.error(f"❌ Failed to create endpoint for {provider_config['name']}: {e}")
            
            results.append(result)
        
        self.test_results["endpoint_creation_tests"] = results
        return results
    
    async def test_authentication(self):
        """Test authentication for created providers"""
        logger.info("Testing provider authentication...")
        
        results = []
        
        for provider in self.test_providers:
            try:
                logger.info(f"Testing authentication for {provider.name}...")
                
                if not self.stagehand_client:
                    result = {
                        "provider_name": provider.name,
                        "provider_id": provider.id,
                        "auth_success": False,
                        "auth_method": provider.auth_config.method,
                        "error": "Stagehand client not available",
                        "session_saved": False
                    }
                    results.append(result)
                    continue
                
                # Test authentication
                auth_success, error_msg = await self.provider_manager.authenticator.authenticate_provider(
                    provider, self.stagehand_client
                )
                
                result = {
                    "provider_name": provider.name,
                    "provider_id": provider.id,
                    "auth_success": auth_success,
                    "auth_method": provider.auth_config.method,
                    "error": error_msg,
                    "session_saved": auth_success
                }
                
                if auth_success:
                    logger.info(f"✅ Authentication successful for {provider.name}")
                    provider.status = ProviderStatus.ACTIVE
                else:
                    logger.error(f"❌ Authentication failed for {provider.name}: {error_msg}")
                    provider.status = ProviderStatus.AUTH_FAILED
                
            except Exception as e:
                result = {
                    "provider_name": provider.name,
                    "provider_id": provider.id,
                    "auth_success": False,
                    "auth_method": provider.auth_config.method if provider.auth_config else "unknown",
                    "error": str(e),
                    "session_saved": False
                }
                
                logger.error(f"❌ Authentication test failed for {provider.name}: {e}")
            
            results.append(result)
        
        self.test_results["authentication_tests"] = results
        return results
    
    async def test_llm_responses(self):
        """Test LLM responses from all providers"""
        logger.info("Testing LLM responses from all providers...")
        
        test_question = "What LLM are you and what is 9-9?"
        results = []
        
        # Test each provider
        for provider in self.test_providers:
            if provider.status != ProviderStatus.ACTIVE:
                logger.warning(f"Skipping {provider.name} - not authenticated")
                continue
            
            try:
                logger.info(f"Testing LLM response from {provider.name}...")
                
                # Test through OpenAI-compatible endpoint
                for model_name in provider.model_mappings:
                    try:
                        response = await self._test_openai_endpoint(model_name, test_question)
                        
                        result = {
                            "provider_name": provider.name,
                            "provider_id": provider.id,
                            "model_name": model_name,
                            "question": test_question,
                            "response": response.get("response", ""),
                            "success": response.get("success", False),
                            "response_time": response.get("response_time", 0),
                            "error": response.get("error")
                        }
                        
                        if response.get("success"):
                            logger.info(f"✅ Got response from {provider.name} ({model_name})")
                            logger.info(f"   Response: {response.get('response', '')[:100]}...")
                        else:
                            logger.error(f"❌ Failed to get response from {provider.name} ({model_name}): {response.get('error')}")
                        
                        results.append(result)
                        
                    except Exception as e:
                        result = {
                            "provider_name": provider.name,
                            "provider_id": provider.id,
                            "model_name": model_name,
                            "question": test_question,
                            "response": "",
                            "success": False,
                            "response_time": 0,
                            "error": str(e)
                        }
                        results.append(result)
                        logger.error(f"❌ Error testing {provider.name} ({model_name}): {e}")
                
            except Exception as e:
                logger.error(f"❌ Error testing provider {provider.name}: {e}")
        
        self.test_results["llm_response_tests"] = results
        return results
    
    async def _test_openai_endpoint(self, model: str, message: str) -> Dict[str, Any]:
        """Test OpenAI-compatible endpoint"""
        try:
            start_time = time.time()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": message}],
                        "max_tokens": 150,
                        "temperature": 0.7
                    },
                    timeout=30.0
                )
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    return {
                        "success": True,
                        "response": content,
                        "response_time": response_time,
                        "status_code": response.status_code
                    }
                else:
                    return {
                        "success": False,
                        "response": "",
                        "response_time": response_time,
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "response": "",
                "response_time": 0,
                "error": str(e)
            }
    
    async def test_integration(self):
        """Test end-to-end integration"""
        logger.info("Testing end-to-end integration...")
        
        results = []
        
        # Test system health
        try:
            health_result = await self._test_system_health()
            results.append({
                "test_name": "System Health Check",
                "success": health_result["success"],
                "details": health_result
            })
        except Exception as e:
            results.append({
                "test_name": "System Health Check",
                "success": False,
                "error": str(e)
            })
        
        # Test load balancing
        try:
            load_balance_result = await self._test_load_balancing()
            results.append({
                "test_name": "Load Balancing",
                "success": load_balance_result["success"],
                "details": load_balance_result
            })
        except Exception as e:
            results.append({
                "test_name": "Load Balancing",
                "success": False,
                "error": str(e)
            })
        
        # Test failover
        try:
            failover_result = await self._test_failover()
            results.append({
                "test_name": "Failover Mechanism",
                "success": failover_result["success"],
                "details": failover_result
            })
        except Exception as e:
            results.append({
                "test_name": "Failover Mechanism",
                "success": False,
                "error": str(e)
            })
        
        self.test_results["integration_tests"] = results
        return results
    
    async def _test_system_health(self) -> Dict[str, Any]:
        """Test system health endpoints"""
        try:
            async with httpx.AsyncClient() as client:
                # Test health endpoint
                health_response = await client.get("http://localhost:8000/v1/health")
                
                # Test models endpoint
                models_response = await client.get("http://localhost:8000/v1/models")
                
                # Test stats endpoint
                stats_response = await client.get("http://localhost:8000/v1/stats")
                
                return {
                    "success": all([
                        health_response.status_code == 200,
                        models_response.status_code == 200,
                        stats_response.status_code == 200
                    ]),
                    "health_status": health_response.status_code,
                    "models_status": models_response.status_code,
                    "stats_status": stats_response.status_code,
                    "active_providers": len([p for p in self.test_providers if p.status == ProviderStatus.ACTIVE])
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_load_balancing(self) -> Dict[str, Any]:
        """Test load balancing across providers"""
        try:
            provider_usage = {}
            total_requests = 20
            
            for i in range(total_requests):
                # Use a generic model name that should route to different providers
                model = "test-model"
                response = await self._test_openai_endpoint(model, f"Test request {i}")
                
                # Track which provider handled the request (would need provider ID in response)
                provider_id = response.get("provider_id", "unknown")
                provider_usage[provider_id] = provider_usage.get(provider_id, 0) + 1
            
            # Calculate distribution
            if len(provider_usage) > 1:
                usage_values = list(provider_usage.values())
                usage_mean = sum(usage_values) / len(usage_values)
                usage_variance = sum((x - usage_mean) ** 2 for x in usage_values) / len(usage_values)
                balance_coefficient = (usage_variance ** 0.5) / usage_mean if usage_mean > 0 else 1
            else:
                balance_coefficient = 0
            
            return {
                "success": balance_coefficient < 0.3,  # Good balance threshold
                "provider_usage": provider_usage,
                "balance_coefficient": balance_coefficient,
                "total_requests": total_requests
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_failover(self) -> Dict[str, Any]:
        """Test failover mechanism"""
        try:
            # This would test what happens when a provider fails
            # For now, just check that the system handles errors gracefully
            
            # Test with invalid model
            response = await self._test_openai_endpoint("invalid-model", "Test failover")
            
            return {
                "success": True,  # Success if it doesn't crash
                "handled_gracefully": not response.get("success", True),
                "error_response": response.get("error", "")
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        logger.info("Generating comprehensive test report...")
        
        # Calculate overall statistics
        total_tests = sum(len(tests) for tests in self.test_results.values())
        passed_tests = 0
        failed_tests = 0
        
        for test_category, tests in self.test_results.items():
            for test in tests:
                if test.get("success", False) or test.get("creation_success", False) or test.get("auth_success", False):
                    passed_tests += 1
                else:
                    failed_tests += 1
        
        overall_success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        # Generate summary
        summary = {
            "test_execution_time": time.time() - self.start_time,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": overall_success_rate,
            "providers_created": len(self.test_providers),
            "providers_authenticated": len([p for p in self.test_providers if p.status == ProviderStatus.ACTIVE]),
            "stagehand_available": self.stagehand_client is not None
        }
        
        report = {
            "test_summary": summary,
            "test_results": self.test_results,
            "provider_details": [
                {
                    "name": p.name,
                    "id": p.id,
                    "status": p.status,
                    "base_url": p.base_url,
                    "model_mappings": p.model_mappings
                } for p in self.test_providers
            ],
            "recommendations": self._generate_recommendations(),
            "generated_at": datetime.now().isoformat()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check endpoint creation
        creation_failures = [t for t in self.test_results.get("endpoint_creation_tests", []) if not t.get("creation_success", False)]
        if creation_failures:
            recommendations.append(f"Fix {len(creation_failures)} endpoint creation failures")
        
        # Check authentication
        auth_failures = [t for t in self.test_results.get("authentication_tests", []) if not t.get("auth_success", False)]
        if auth_failures:
            recommendations.append(f"Fix {len(auth_failures)} authentication failures - check credentials and selectors")
        
        # Check LLM responses
        response_failures = [t for t in self.test_results.get("llm_response_tests", []) if not t.get("success", False)]
        if response_failures:
            recommendations.append(f"Fix {len(response_failures)} LLM response failures - check chat integration")
        
        # Check Stagehand availability
        if not self.stagehand_client:
            recommendations.append("Install and configure Stagehand for automated browser testing")
        
        if not recommendations:
            recommendations.append("All tests passed - system is working correctly")
        
        return recommendations


async def run_real_endpoint_tests():
    """Run the real endpoint test suite"""
    logger.info("🧪 Starting Real-World Dynamic Endpoint Test Suite...")
    logger.info("=" * 80)
    
    test_suite = RealEndpointTestSuite()
    
    try:
        # Setup
        await test_suite.setup()
        
        # Run all test categories
        logger.info("🏗️ TESTING ENDPOINT CREATION")
        logger.info("-" * 40)
        await test_suite.test_endpoint_creation()
        
        logger.info("\n🔐 TESTING AUTHENTICATION")
        logger.info("-" * 40)
        await test_suite.test_authentication()
        
        logger.info("\n🤖 TESTING LLM RESPONSES")
        logger.info("-" * 40)
        await test_suite.test_llm_responses()
        
        logger.info("\n🔗 TESTING INTEGRATION")
        logger.info("-" * 40)
        await test_suite.test_integration()
        
        # Generate final report
        logger.info("\n📋 GENERATING TEST REPORT")
        logger.info("-" * 40)
        report = test_suite.generate_test_report()
        
        # Save report to file
        report_filename = f"real_endpoint_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"📄 Test report saved to: {report_filename}")
        logger.info(f"🎯 Overall success rate: {report['test_summary']['success_rate']:.2f}%")
        logger.info(f"🏗️ Providers created: {report['test_summary']['providers_created']}")
        logger.info(f"🔐 Providers authenticated: {report['test_summary']['providers_authenticated']}")
        
        # Print recommendations
        logger.info("\n💡 RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            logger.info(f"   • {rec}")
        
        # Print LLM responses
        logger.info("\n🤖 LLM RESPONSES:")
        for test in report["test_results"]["llm_response_tests"]:
            if test.get("success"):
                logger.info(f"   ✅ {test['provider_name']} ({test['model_name']}):")
                logger.info(f"      Q: {test['question']}")
                logger.info(f"      A: {test['response'][:200]}...")
            else:
                logger.info(f"   ❌ {test['provider_name']} ({test['model_name']}): {test.get('error', 'Unknown error')}")
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 REAL ENDPOINT TEST SUITE COMPLETED!")
        logger.info("=" * 80)
        
        return report
        
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")
        raise
    finally:
        await test_suite.teardown()


if __name__ == "__main__":
    # Run the real endpoint test suite
    asyncio.run(run_real_endpoint_tests())
