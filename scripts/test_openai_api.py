#!/usr/bin/env python3
"""
Test the OpenAI API compatibility with all 5 services.
This simulates real usage scenarios.
"""

import asyncio
import sys
import os
import json
import httpx
from pathlib import Path


class OpenAIAPITester:
    """Test OpenAI API compatibility with all services."""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        
    async def test_models_endpoint(self):
        """Test the /v1/models endpoint."""
        print("🔍 Testing /v1/models endpoint...")
        
        try:
            response = await self.client.get(f"{self.base_url}/v1/models")
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                print(f"   ✅ Found {len(models)} models:")
                for model in models:
                    print(f"      - {model['id']} (owned by {model['owned_by']})")
                return True
            else:
                print(f"   ❌ Failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return False
    
    async def test_health_endpoint(self):
        """Test the /v1/health endpoint."""
        print("🏥 Testing /v1/health endpoint...")
        
        try:
            response = await self.client.get(f"{self.base_url}/v1/health")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status: {data.get('status')}")
                print(f"   📊 Services: {len(data.get('services', []))}")
                print(f"   🎯 Models: {len(data.get('models', []))}")
                return True
            else:
                print(f"   ❌ Failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return False
    
    async def test_chat_completion(self, model: str, service_name: str):
        """Test chat completion for a specific model."""
        print(f"💬 Testing chat completion for {model} ({service_name})...")
        
        try:
            request_data = {
                "model": model,
                "messages": [
                    {"role": "user", "content": f"Hello from {service_name}! Please respond with 'Hello from {service_name} API test!' and nothing else."}
                ],
                "max_tokens": 50,
                "temperature": 0.1
            }
            
            response = await self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                message = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                
                print(f"   ✅ Response: {message}")
                print(f"   📊 Tokens: {usage.get('total_tokens', 'N/A')}")
                return True, message
            else:
                print(f"   ❌ Failed: {response.status_code} - {response.text}")
                return False, None
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return False, None
    
    async def test_all_services(self):
        """Test all 5 services via OpenAI API."""
        print("🚀 Testing OpenAI API compatibility with all services...")
        print("=" * 70)
        
        # Test basic endpoints first
        models_ok = await self.test_models_endpoint()
        health_ok = await self.test_health_endpoint()
        
        if not (models_ok and health_ok):
            print("❌ Basic endpoints failed. Check if server is running.")
            return False
        
        print("\n" + "=" * 70)
        print("🎯 Testing chat completions for each service...")
        print("=" * 70)
        
        # Test each service
        services_to_test = [
            ("k2think-chat", "K2Think.AI"),
            ("qwen-max", "Qwen.AI"),
            ("deepseek-chat", "DeepSeek"),
            ("grok-beta", "Grok"),
            ("gpt-3.5-turbo", "Z.AI")  # Maps to Z.AI
        ]
        
        successful_services = []
        failed_services = []
        
        for model, service_name in services_to_test:
            success, response = await self.test_chat_completion(model, service_name)
            
            if success:
                successful_services.append((model, service_name, response))
            else:
                failed_services.append((model, service_name))
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 FINAL API TEST RESULTS:")
        print("=" * 70)
        
        for model, service_name, response in successful_services:
            print(f"✅ {service_name} ({model})")
            print(f"   Response: {response[:80]}...")
        
        for model, service_name in failed_services:
            print(f"❌ {service_name} ({model}) - FAILED")
        
        success_rate = len(successful_services)
        total_services = len(services_to_test)
        
        print(f"\n🎯 API SUCCESS RATE: {success_rate}/{total_services} services working")
        
        if success_rate == total_services:
            print("🎉 ALL SERVICES WORKING VIA OPENAI API!")
            print("✅ Ready for production use!")
            return True
        else:
            print(f"⚠️  {total_services - success_rate} services need fixing")
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def main():
    """Main test function."""
    print("🧪 OpenAI API Compatibility Test")
    print("Make sure the chat proxy server is running on localhost:8000")
    print()
    
    tester = OpenAIAPITester()
    
    try:
        success = await tester.test_all_services()
        
        if success:
            print("\n🚀 All services confirmed working via OpenAI API!")
            print("You can now use any OpenAI-compatible client with these services.")
            sys.exit(0)
        else:
            print("\n❌ Some services failed via OpenAI API.")
            sys.exit(1)
            
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
