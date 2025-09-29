#!/usr/bin/env python3
"""
Comprehensive test script for FlareProx integration with chat proxy endpoints.
Tests reusability, scalability, and load balancing of all endpoints.
"""

import asyncio
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any
import httpx
import aiohttp
from pathlib import Path

# Add the backend to Python path
backend_path = Path(__file__).parent.parent / "autogpt_platform" / "backend"
sys.path.insert(0, str(backend_path))

from backend.util.flareprox_integration import (
    FlareProxManager,
    initialize_flareprox,
    test_flareprox_endpoints,
    get_proxied_url,
    cleanup_flareprox
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_CONFIG = {
    "server_url": "http://localhost:8000",
    "test_services": ["k2think", "qwen", "deepseek", "grok", "zai"],
    "concurrent_requests": [1, 5, 10, 20],
    "test_duration": 60,  # seconds
    "endpoints": {
        "health": "/v1/health",
        "models": "/v1/models", 
        "stats": "/v1/stats",
        "chat_completions": "/v1/chat/completions"
    }
}

class FlareProxTester:
    """Comprehensive tester for FlareProx integration."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        self.results = {
            "flareprox_status": {},
            "endpoint_tests": {},
            "load_tests": {},
            "scalability_tests": {},
            "error_analysis": {}
        }
        
    async def run_all_tests(self):
        """Run all FlareProx integration tests."""
        logger.info("🚀 Starting comprehensive FlareProx integration tests...")
        
        try:
            # Test 1: FlareProx System Status
            await self.test_flareprox_system()
            
            # Test 2: Basic Endpoint Connectivity
            await self.test_basic_endpoints()
            
            # Test 3: Chat Completions with FlareProx
            await self.test_chat_completions()
            
            # Test 4: Load Balancing Tests
            await self.test_load_balancing()
            
            # Test 5: Scalability Tests
            await self.test_scalability()
            
            # Test 6: Error Handling and Recovery
            await self.test_error_handling()
            
            # Test 7: Performance Analysis
            await self.test_performance()
            
            # Generate comprehensive report
            await self.generate_report()
            
        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            raise
        finally:
            await self.client.aclose()
    
    async def test_flareprox_system(self):
        """Test FlareProx system initialization and status."""
        logger.info("🔧 Testing FlareProx system...")
        
        try:
            # Initialize FlareProx
            flareprox_initialized = await initialize_flareprox()
            
            self.results["flareprox_status"]["initialized"] = flareprox_initialized
            
            if flareprox_initialized:
                # Test all endpoints
                endpoint_status = await test_flareprox_endpoints()
                self.results["flareprox_status"]["endpoints"] = endpoint_status
                
                logger.info(f"✅ FlareProx initialized with {endpoint_status['working_endpoints']} working endpoints")
            else:
                logger.warning("⚠️ FlareProx failed to initialize")
                
        except Exception as e:
            logger.error(f"❌ FlareProx system test failed: {e}")
            self.results["flareprox_status"]["error"] = str(e)
    
    async def test_basic_endpoints(self):
        """Test basic API endpoints."""
        logger.info("🔍 Testing basic endpoints...")
        
        for endpoint_name, endpoint_path in TEST_CONFIG["endpoints"].items():
            try:
                url = f"{TEST_CONFIG['server_url']}{endpoint_path}"
                
                start_time = time.time()
                response = await self.client.get(url)
                response_time = time.time() - start_time
                
                self.results["endpoint_tests"][endpoint_name] = {
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "success": response.status_code == 200,
                    "content_length": len(response.content)
                }
                
                if response.status_code == 200:
                    logger.info(f"✅ {endpoint_name}: {response.status_code} ({response_time:.2f}s)")
                else:
                    logger.warning(f"⚠️ {endpoint_name}: {response.status_code} ({response_time:.2f}s)")
                    
            except Exception as e:
                logger.error(f"❌ {endpoint_name} failed: {e}")
                self.results["endpoint_tests"][endpoint_name] = {
                    "error": str(e),
                    "success": False
                }
    
    async def test_chat_completions(self):
        """Test chat completions with different services."""
        logger.info("💬 Testing chat completions...")
        
        test_messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "user", "content": "What is 2+2?"},
            {"role": "user", "content": "Tell me a short joke."}
        ]
        
        # Model mappings for different services
        model_mappings = {
            "gpt-3.5-turbo": "zai",
            "qwen-max": "qwen", 
            "deepseek-chat": "deepseek",
            "grok-beta": "grok",
            "k2-think": "k2think"
        }
        
        for model, service in model_mappings.items():
            for i, messages in enumerate([test_messages[:1], test_messages[:2], test_messages]):
                try:
                    payload = {
                        "model": model,
                        "messages": messages,
                        "max_tokens": 100,
                        "temperature": 0.7
                    }
                    
                    start_time = time.time()
                    response = await self.client.post(
                        f"{TEST_CONFIG['server_url']}/v1/chat/completions",
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    response_time = time.time() - start_time
                    
                    test_key = f"{service}_test_{i+1}"
                    
                    if response.status_code == 200:
                        data = response.json()
                        self.results["endpoint_tests"][test_key] = {
                            "model": model,
                            "service": service,
                            "status_code": response.status_code,
                            "response_time": response_time,
                            "success": True,
                            "response_length": len(data.get("choices", [{}])[0].get("message", {}).get("content", "")),
                            "usage": data.get("usage", {})
                        }
                        logger.info(f"✅ {service} ({model}): Success in {response_time:.2f}s")
                    else:
                        self.results["endpoint_tests"][test_key] = {
                            "model": model,
                            "service": service,
                            "status_code": response.status_code,
                            "response_time": response_time,
                            "success": False,
                            "error": response.text
                        }
                        logger.warning(f"⚠️ {service} ({model}): {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"❌ {service} test failed: {e}")
                    self.results["endpoint_tests"][f"{service}_test_{i+1}"] = {
                        "model": model,
                        "service": service,
                        "error": str(e),
                        "success": False
                    }
                
                # Wait between requests to avoid rate limiting
                await asyncio.sleep(2)
    
    async def test_load_balancing(self):
        """Test load balancing across FlareProx endpoints."""
        logger.info("⚖️ Testing load balancing...")
        
        if not self.results["flareprox_status"].get("initialized"):
            logger.warning("⚠️ Skipping load balancing tests - FlareProx not initialized")
            return
        
        # Test URL proxying with different endpoints
        test_urls = [
            "https://httpbin.org/ip",
            "https://httpbin.org/user-agent", 
            "https://httpbin.org/headers"
        ]
        
        for i in range(10):  # Test 10 requests
            try:
                test_url = test_urls[i % len(test_urls)]
                
                # Get proxied URL
                proxied_url = await get_proxied_url(test_url, use_random=True)
                
                start_time = time.time()
                response = await self.client.get(proxied_url)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    ip_address = data.get("origin", "unknown")
                    
                    test_key = f"load_balance_test_{i+1}"
                    self.results["load_tests"][test_key] = {
                        "original_url": test_url,
                        "proxied_url": proxied_url,
                        "ip_address": ip_address,
                        "response_time": response_time,
                        "success": True
                    }
                    
                    logger.info(f"✅ Load test {i+1}: IP {ip_address} ({response_time:.2f}s)")
                else:
                    logger.warning(f"⚠️ Load test {i+1}: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ Load test {i+1} failed: {e}")
                
            await asyncio.sleep(1)
    
    async def test_scalability(self):
        """Test system scalability with concurrent requests."""
        logger.info("📈 Testing scalability...")
        
        for concurrent_count in TEST_CONFIG["concurrent_requests"]:
            logger.info(f"Testing with {concurrent_count} concurrent requests...")
            
            async def make_request(request_id: int):
                try:
                    payload = {
                        "model": "gpt-3.5-turbo",
                        "messages": [{"role": "user", "content": f"Test request {request_id}"}],
                        "max_tokens": 50
                    }
                    
                    start_time = time.time()
                    response = await self.client.post(
                        f"{TEST_CONFIG['server_url']}/v1/chat/completions",
                        json=payload,
                        timeout=120.0
                    )
                    response_time = time.time() - start_time
                    
                    return {
                        "request_id": request_id,
                        "status_code": response.status_code,
                        "response_time": response_time,
                        "success": response.status_code == 200
                    }
                    
                except Exception as e:
                    return {
                        "request_id": request_id,
                        "error": str(e),
                        "success": False
                    }
            
            # Run concurrent requests
            start_time = time.time()
            tasks = [make_request(i) for i in range(concurrent_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start_time
            
            # Analyze results
            successful_requests = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            failed_requests = concurrent_count - successful_requests
            avg_response_time = sum(r.get("response_time", 0) for r in results if isinstance(r, dict)) / len(results)
            
            self.results["scalability_tests"][f"concurrent_{concurrent_count}"] = {
                "total_requests": concurrent_count,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate": successful_requests / concurrent_count,
                "total_time": total_time,
                "avg_response_time": avg_response_time,
                "requests_per_second": concurrent_count / total_time
            }
            
            logger.info(f"✅ {concurrent_count} concurrent: {successful_requests}/{concurrent_count} success ({successful_requests/concurrent_count*100:.1f}%)")
            
            # Wait between scalability tests
            await asyncio.sleep(5)
    
    async def test_error_handling(self):
        """Test error handling and recovery mechanisms."""
        logger.info("🛡️ Testing error handling...")
        
        error_tests = [
            {
                "name": "invalid_model",
                "payload": {
                    "model": "invalid-model-name",
                    "messages": [{"role": "user", "content": "test"}]
                }
            },
            {
                "name": "empty_messages",
                "payload": {
                    "model": "gpt-3.5-turbo",
                    "messages": []
                }
            },
            {
                "name": "invalid_message_format",
                "payload": {
                    "model": "gpt-3.5-turbo",
                    "messages": [{"invalid": "format"}]
                }
            }
        ]
        
        for test in error_tests:
            try:
                response = await self.client.post(
                    f"{TEST_CONFIG['server_url']}/v1/chat/completions",
                    json=test["payload"]
                )
                
                self.results["error_analysis"][test["name"]] = {
                    "status_code": response.status_code,
                    "response": response.text[:500],  # First 500 chars
                    "handled_gracefully": 400 <= response.status_code < 500
                }
                
                if 400 <= response.status_code < 500:
                    logger.info(f"✅ {test['name']}: Handled gracefully ({response.status_code})")
                else:
                    logger.warning(f"⚠️ {test['name']}: Unexpected response ({response.status_code})")
                    
            except Exception as e:
                logger.error(f"❌ {test['name']} error test failed: {e}")
                self.results["error_analysis"][test["name"]] = {
                    "error": str(e),
                    "handled_gracefully": False
                }
    
    async def test_performance(self):
        """Test performance characteristics."""
        logger.info("⚡ Testing performance...")
        
        # Test response times for different message lengths
        message_lengths = [10, 100, 500, 1000]  # characters
        
        for length in message_lengths:
            message = "x" * length
            
            try:
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": message}],
                    "max_tokens": 100
                }
                
                start_time = time.time()
                response = await self.client.post(
                    f"{TEST_CONFIG['server_url']}/v1/chat/completions",
                    json=payload
                )
                response_time = time.time() - start_time
                
                self.results["endpoint_tests"][f"performance_length_{length}"] = {
                    "message_length": length,
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "success": response.status_code == 200
                }
                
                logger.info(f"✅ Message length {length}: {response_time:.2f}s")
                
            except Exception as e:
                logger.error(f"❌ Performance test (length {length}) failed: {e}")
                
            await asyncio.sleep(2)
    
    async def generate_report(self):
        """Generate comprehensive test report."""
        logger.info("📊 Generating test report...")
        
        report = {
            "test_summary": {
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                "flareprox_initialized": self.results["flareprox_status"].get("initialized", False),
                "total_endpoint_tests": len(self.results["endpoint_tests"]),
                "successful_endpoint_tests": sum(1 for t in self.results["endpoint_tests"].values() if t.get("success")),
                "total_load_tests": len(self.results["load_tests"]),
                "successful_load_tests": sum(1 for t in self.results["load_tests"].values() if t.get("success")),
            },
            "detailed_results": self.results
        }
        
        # Save report to file
        report_file = f"flareprox_test_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📄 Test report saved to: {report_file}")
        
        # Print summary
        print("\n" + "="*80)
        print("🎯 FLAREPROX INTEGRATION TEST SUMMARY")
        print("="*80)
        
        print(f"FlareProx Status: {'✅ Initialized' if report['test_summary']['flareprox_initialized'] else '❌ Failed'}")
        
        if self.results["flareprox_status"].get("endpoints"):
            endpoints = self.results["flareprox_status"]["endpoints"]
            print(f"FlareProx Endpoints: {endpoints['working_endpoints']}/{endpoints['total_endpoints']} working")
        
        print(f"Endpoint Tests: {report['test_summary']['successful_endpoint_tests']}/{report['test_summary']['total_endpoint_tests']} passed")
        print(f"Load Tests: {report['test_summary']['successful_load_tests']}/{report['test_summary']['total_load_tests']} passed")
        
        # Scalability summary
        if self.results["scalability_tests"]:
            print("\nScalability Results:")
            for test_name, result in self.results["scalability_tests"].items():
                print(f"  {test_name}: {result['success_rate']*100:.1f}% success rate, {result['requests_per_second']:.1f} req/s")
        
        print("\n" + "="*80)
        
        return report


async def main():
    """Main test execution."""
    print("🚀 Starting FlareProx Integration Tests...")
    
    # Check if server is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{TEST_CONFIG['server_url']}/v1/health", timeout=10.0)
            if response.status_code != 200:
                print(f"❌ Server not responding properly: {response.status_code}")
                return
    except Exception as e:
        print(f"❌ Cannot connect to server at {TEST_CONFIG['server_url']}: {e}")
        print("Please ensure the chat proxy server is running with: python scripts/start_chat_proxy_server.py")
        return
    
    # Run tests
    tester = FlareProxTester()
    try:
        await tester.run_all_tests()
        print("✅ All tests completed successfully!")
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
