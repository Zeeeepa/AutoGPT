#!/usr/bin/env python3
"""
Test script to verify all 5 chat services work with real credentials.
This will test each service individually and confirm we can get responses.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "autogpt_platform" / "backend"
sys.path.insert(0, str(backend_dir))

from backend.data.chat_proxy_models import (
    ChatServiceType,
    DEFAULT_SERVICE_CONFIGS,
    DEFAULT_ACCOUNTS
)
from backend.blocks.chat_proxy.blocks import (
    ChatProxyLoginBlock,
    ChatProxySendMessageBlock,
    ChatProxyHealthCheckBlock
)


class ServiceTester:
    """Test individual chat services with real credentials."""
    
    def __init__(self):
        self.results = {}
        
    async def test_service(self, service_type: ChatServiceType) -> dict:
        """Test a single service and return results."""
        print(f"\n🧪 Testing {service_type.value}...")
        
        try:
            # Get service config and account
            config = DEFAULT_SERVICE_CONFIGS[service_type]
            accounts = DEFAULT_ACCOUNTS[service_type]
            account = accounts[0]  # Use first account
            
            print(f"   URL: {config.base_url}")
            print(f"   Email: {account.email}")
            print(f"   Password: {'*' * len(account.password)}")
            
            # Test login
            print("   🔐 Testing login...")
            login_block = ChatProxyLoginBlock()
            login_result = await login_block.run(
                service_type=service_type,
                email=account.email,
                password=account.password
            )
            
            if not login_result.get("success", False):
                return {
                    "success": False,
                    "error": f"Login failed: {login_result.get('error', 'Unknown error')}",
                    "stage": "login"
                }
            
            print("   ✅ Login successful!")
            session_id = login_result.get("session_id")
            
            # Test sending message
            print("   💬 Testing message sending...")
            message_block = ChatProxySendMessageBlock()
            message_result = await message_block.run(
                service_type=service_type,
                session_id=session_id,
                message="Hello! Please respond with 'Service test successful' and nothing else.",
                max_wait_time=30
            )
            
            if not message_result.get("success", False):
                return {
                    "success": False,
                    "error": f"Message failed: {message_result.get('error', 'Unknown error')}",
                    "stage": "message"
                }
            
            response_text = message_result.get("response", "")
            print(f"   📝 Response: {response_text}")
            
            # Test health check
            print("   🏥 Testing health check...")
            health_block = ChatProxyHealthCheckBlock()
            health_result = await health_block.run(
                service_type=service_type,
                session_id=session_id
            )
            
            return {
                "success": True,
                "response": response_text,
                "health": health_result.get("healthy", False),
                "session_id": session_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "stage": "exception"
            }
    
    async def test_all_services(self):
        """Test all 5 services."""
        print("🚀 Starting real service tests...")
        print("=" * 60)
        
        services_to_test = [
            ChatServiceType.K2THINK,
            ChatServiceType.QWEN,
            ChatServiceType.DEEPSEEK,
            ChatServiceType.GROK,
            ChatServiceType.ZAI
        ]
        
        for service_type in services_to_test:
            result = await self.test_service(service_type)
            self.results[service_type] = result
            
            if result["success"]:
                print(f"   ✅ {service_type.value} - SUCCESS")
            else:
                print(f"   ❌ {service_type.value} - FAILED: {result['error']}")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 FINAL RESULTS:")
        print("=" * 60)
        
        successful_services = []
        failed_services = []
        
        for service_type, result in self.results.items():
            if result["success"]:
                successful_services.append(service_type.value)
                print(f"✅ {service_type.value}")
                if "response" in result:
                    print(f"   Response: {result['response'][:100]}...")
            else:
                failed_services.append(service_type.value)
                print(f"❌ {service_type.value} - {result['error']}")
        
        print(f"\n🎯 SUCCESS RATE: {len(successful_services)}/5 services working")
        
        if len(successful_services) == 5:
            print("🎉 ALL SERVICES WORKING! Ready to proceed with dynamic system.")
            return True
        else:
            print(f"⚠️  Need to fix {len(failed_services)} services before proceeding:")
            for service in failed_services:
                print(f"   - {service}")
            return False


async def main():
    """Main test function."""
    # Set up environment
    os.environ.setdefault("STAGEHAND_API_KEY", "test-key")
    os.environ.setdefault("BROWSERBASE_PROJECT_ID", "test-project")
    
    tester = ServiceTester()
    success = await tester.test_all_services()
    
    if success:
        print("\n🚀 All services confirmed working! You can now proceed with dynamic implementation.")
        sys.exit(0)
    else:
        print("\n❌ Some services failed. Please check credentials and service availability.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
