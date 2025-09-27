#!/usr/bin/env python3
"""
Test script for the Provider Management System.
Tests smart scaling, browser instances, and provider management.
"""

import asyncio
import json
import time
import requests
import websockets
from typing import Dict, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
API_BASE = f"{BASE_URL}/api/provider-management"


class ProviderManagementTester:
    """Test suite for provider management system."""
    
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
    
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """Log test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}: {message}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message
        })
    
    def test_system_status(self):
        """Test system status endpoint."""
        try:
            response = self.session.get(f"{API_BASE}/status")
            response.raise_for_status()
            
            data = response.json()
            required_fields = [
                "system_healthy",
                "scaling_engine_active",
                "browser_manager_active"
            ]
            
            for field in required_fields:
                if field not in data:
                    self.log_test("System Status", False, f"Missing field: {field}")
                    return
            
            self.log_test("System Status", True, f"System healthy: {data['system_healthy']}")
            return data
            
        except Exception as e:
            self.log_test("System Status", False, str(e))
            return None
    
    def test_list_providers(self):
        """Test listing providers."""
        try:
            response = self.session.get(f"{API_BASE}/providers")
            response.raise_for_status()
            
            data = response.json()
            providers = data.get("providers", [])
            
            if not providers:
                self.log_test("List Providers", False, "No providers found")
                return None
            
            # Check for expected services
            expected_services = ["k2think", "qwen", "deepseek", "grok", "zai"]
            found_services = [p["service_type"] for p in providers]
            
            missing_services = [s for s in expected_services if s not in found_services]
            if missing_services:
                self.log_test("List Providers", False, f"Missing services: {missing_services}")
                return None
            
            self.log_test("List Providers", True, f"Found {len(providers)} providers")
            return data
            
        except Exception as e:
            self.log_test("List Providers", False, str(e))
            return None
    
    def test_list_instances(self):
        """Test listing browser instances."""
        try:
            response = self.session.get(f"{API_BASE}/instances")
            response.raise_for_status()
            
            data = response.json()
            instances = data.get("instances", {})
            
            # Should have at least Instance 1
            if "1" not in instances:
                self.log_test("List Instances", False, "Instance 1 not found")
                return None
            
            instance_1 = instances["1"]
            if not instance_1 or not instance_1.get("is_active"):
                self.log_test("List Instances", False, "Instance 1 not active")
                return None
            
            self.log_test("List Instances", True, f"Found {len(instances)} instances")
            return data
            
        except Exception as e:
            self.log_test("List Instances", False, str(e))
            return None
    
    def test_instance_health(self, instance_id: int = 1):
        """Test instance health check."""
        try:
            response = self.session.get(f"{API_BASE}/instances/{instance_id}/health")
            response.raise_for_status()
            
            data = response.json()
            
            if not isinstance(data.get("healthy"), bool):
                self.log_test(f"Instance {instance_id} Health", False, "Invalid health response")
                return None
            
            self.log_test(f"Instance {instance_id} Health", True, f"Healthy: {data['healthy']}")
            return data
            
        except Exception as e:
            self.log_test(f"Instance {instance_id} Health", False, str(e))
            return None
    
    def test_scaling_status(self):
        """Test scaling engine status."""
        try:
            response = self.session.get(f"{API_BASE}/scaling/status")
            response.raise_for_status()
            
            data = response.json()
            
            required_sections = ["metrics", "instances", "providers"]
            for section in required_sections:
                if section not in data:
                    self.log_test("Scaling Status", False, f"Missing section: {section}")
                    return None
            
            metrics = data["metrics"]
            self.log_test("Scaling Status", True, 
                         f"Active instances: {metrics.get('total_active_instances', 0)}, "
                         f"Active providers: {metrics.get('total_active_providers', 0)}")
            return data
            
        except Exception as e:
            self.log_test("Scaling Status", False, str(e))
            return None
    
    def test_scaling_rules(self):
        """Test scaling rules configuration."""
        try:
            response = self.session.get(f"{API_BASE}/scaling/rules")
            response.raise_for_status()
            
            data = response.json()
            
            expected_fields = [
                "idle_timeout_minutes",
                "max_instances",
                "providers_per_instance",
                "scaling_cooldown_seconds"
            ]
            
            for field in expected_fields:
                if field not in data:
                    self.log_test("Scaling Rules", False, f"Missing field: {field}")
                    return None
            
            # Verify expected values
            if data["max_instances"] != 3:
                self.log_test("Scaling Rules", False, f"Expected max_instances=3, got {data['max_instances']}")
                return None
            
            if data["providers_per_instance"] != 5:
                self.log_test("Scaling Rules", False, f"Expected providers_per_instance=5, got {data['providers_per_instance']}")
                return None
            
            if data["idle_timeout_minutes"] != 30:
                self.log_test("Scaling Rules", False, f"Expected idle_timeout_minutes=30, got {data['idle_timeout_minutes']}")
                return None
            
            self.log_test("Scaling Rules", True, "All scaling rules configured correctly")
            return data
            
        except Exception as e:
            self.log_test("Scaling Rules", False, str(e))
            return None
    
    def test_provider_enable_disable(self, service_type: str = "k2think"):
        """Test enabling and disabling providers."""
        try:
            # Test disable
            response = self.session.post(f"{API_BASE}/providers/{service_type}/disable")
            response.raise_for_status()
            
            disable_data = response.json()
            if not disable_data.get("success"):
                self.log_test(f"Disable {service_type}", False, "Disable request failed")
                return False
            
            # Test enable
            response = self.session.post(f"{API_BASE}/providers/{service_type}/enable")
            response.raise_for_status()
            
            enable_data = response.json()
            if not enable_data.get("success"):
                self.log_test(f"Enable {service_type}", False, "Enable request failed")
                return False
            
            self.log_test(f"Provider Enable/Disable", True, f"Successfully toggled {service_type}")
            return True
            
        except Exception as e:
            self.log_test(f"Provider Enable/Disable", False, str(e))
            return False
    
    def test_instance_start_stop(self, instance_id: int = 2):
        """Test starting and stopping browser instances."""
        try:
            # Test start
            response = self.session.post(f"{API_BASE}/instances/{instance_id}/start")
            response.raise_for_status()
            
            start_data = response.json()
            if not start_data.get("success"):
                self.log_test(f"Start Instance {instance_id}", False, "Start request failed")
                return False
            
            # Wait a moment for instance to start
            time.sleep(2)
            
            # Verify instance is running
            health_data = self.test_instance_health(instance_id)
            if not health_data or not health_data.get("healthy"):
                logger.warning(f"Instance {instance_id} may not be fully healthy yet")
            
            # Test stop (only for instances 2 and 3)
            if instance_id != 1:
                response = self.session.post(f"{API_BASE}/instances/{instance_id}/stop")
                response.raise_for_status()
                
                stop_data = response.json()
                if not stop_data.get("success"):
                    self.log_test(f"Stop Instance {instance_id}", False, "Stop request failed")
                    return False
            
            self.log_test(f"Instance Start/Stop", True, f"Successfully controlled Instance {instance_id}")
            return True
            
        except Exception as e:
            self.log_test(f"Instance Start/Stop", False, str(e))
            return False
    
    async def test_websocket_connection(self):
        """Test WebSocket real-time updates."""
        try:
            uri = f"{WS_URL}/api/provider-management/ws"
            
            async with websockets.connect(uri) as websocket:
                # Wait for initial status message
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)
                
                if data.get("type") != "initial_status":
                    self.log_test("WebSocket Connection", False, f"Unexpected message type: {data.get('type')}")
                    return False
                
                # Send ping
                await websocket.send(json.dumps({"type": "ping"}))
                
                # Wait for pong
                pong_message = await asyncio.wait_for(websocket.recv(), timeout=5)
                pong_data = json.loads(pong_message)
                
                if pong_data.get("type") != "pong":
                    self.log_test("WebSocket Connection", False, "Ping/pong failed")
                    return False
                
                self.log_test("WebSocket Connection", True, "Real-time connection working")
                return True
                
        except Exception as e:
            self.log_test("WebSocket Connection", False, str(e))
            return False
    
    def test_openai_api_integration(self):
        """Test OpenAI API integration with scaling engine."""
        try:
            # Test chat completion request
            openai_url = f"{BASE_URL}/api/v1/chat/completions"
            
            payload = {
                "model": "k2think-chat",
                "messages": [
                    {"role": "user", "content": "Hello, this is a test message for the scaling system."}
                ],
                "temperature": 0.7,
                "max_tokens": 50
            }
            
            response = self.session.post(openai_url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    self.log_test("OpenAI API Integration", True, "Chat completion successful")
                    return True
                else:
                    self.log_test("OpenAI API Integration", False, "Invalid response format")
                    return False
            else:
                # This might fail if Stagehand/Browserbase is not configured
                self.log_test("OpenAI API Integration", False, 
                             f"HTTP {response.status_code} - May need Stagehand/Browserbase setup")
                return False
                
        except Exception as e:
            self.log_test("OpenAI API Integration", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests."""
        logger.info("🚀 Starting Provider Management System Tests")
        logger.info("=" * 60)
        
        # Basic system tests
        self.test_system_status()
        self.test_list_providers()
        self.test_list_instances()
        self.test_instance_health()
        
        # Scaling engine tests
        self.test_scaling_status()
        self.test_scaling_rules()
        
        # Provider management tests
        self.test_provider_enable_disable()
        
        # Instance management tests
        self.test_instance_start_stop()
        
        # WebSocket tests
        try:
            asyncio.run(self.test_websocket_connection())
        except Exception as e:
            self.log_test("WebSocket Connection", False, f"Async test failed: {e}")
        
        # OpenAI API integration test
        self.test_openai_api_integration()
        
        # Summary
        logger.info("=" * 60)
        logger.info("📊 Test Results Summary")
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        logger.info(f"✅ Passed: {passed}/{total}")
        logger.info(f"❌ Failed: {total - passed}/{total}")
        
        if passed == total:
            logger.info("🎉 All tests passed! Provider Management System is working correctly.")
        else:
            logger.info("⚠️  Some tests failed. Check the logs above for details.")
            
            # Show failed tests
            failed_tests = [r for r in self.test_results if not r["success"]]
            for test in failed_tests:
                logger.info(f"   ❌ {test['test']}: {test['message']}")
        
        return passed == total


def main():
    """Main test runner."""
    tester = ProviderManagementTester()
    
    try:
        success = tester.run_all_tests()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Tests interrupted by user")
        exit(1)
    except Exception as e:
        logger.error(f"💥 Test runner failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
