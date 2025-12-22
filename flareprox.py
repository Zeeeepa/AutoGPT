#!/usr/bin/env python3
"""
Mock FlareProx implementation for testing purposes.
This simulates the FlareProx functionality without requiring actual Cloudflare Workers.
"""

import json
import logging
import os
import random
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class CloudflareManager:
    """Mock Cloudflare Manager for testing."""
    
    def __init__(self, api_token: str = None, account_id: str = None):
        self.api_token = api_token or os.getenv("CLOUDFLARE_API_TOKEN", "mock_token")
        self.account_id = account_id or os.getenv("CLOUDFLARE_ACCOUNT_ID", "mock_account")
        self.is_configured = bool(self.api_token and self.account_id)
        
    def create_worker(self, name: str, script: str) -> Dict[str, Any]:
        """Mock worker creation."""
        return {
            "id": f"worker_{name}_{int(time.time())}",
            "name": name,
            "url": f"https://{name}.mock-worker.workers.dev",
            "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "status": "active"
        }
    
    def delete_worker(self, worker_id: str) -> bool:
        """Mock worker deletion."""
        return True
    
    def list_workers(self) -> List[Dict[str, Any]]:
        """Mock worker listing."""
        return []


class FlareProx:
    """Mock FlareProx implementation for testing."""
    
    def __init__(self, config_file: str = "flareprox.json"):
        self.config_file = config_file
        self.cloudflare_manager = None
        self.workers = []
        self.is_configured = False
        
        # Load configuration
        self._load_config()
        
    def _load_config(self):
        """Load configuration from file or environment."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    
                cf_config = config.get("cloudflare", {})
                api_token = cf_config.get("api_token", "")
                account_id = cf_config.get("account_id", "")
                
                if api_token and account_id and len(api_token) > 10 and len(account_id) > 10:
                    self.cloudflare_manager = CloudflareManager(api_token, account_id)
                    self.is_configured = True
                    logger.info("FlareProx configured with real credentials")
                    return
            
            # Check environment variables
            api_token = os.getenv("CLOUDFLARE_API_TOKEN")
            account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
            
            if api_token and account_id:
                self.cloudflare_manager = CloudflareManager(api_token, account_id)
                self.is_configured = True
                logger.info("FlareProx configured with environment credentials")
            else:
                # Use mock configuration for testing
                self.cloudflare_manager = CloudflareManager("mock_token", "mock_account")
                self.is_configured = True
                logger.info("FlareProx configured with mock credentials for testing")
                
        except Exception as e:
            logger.error(f"Error loading FlareProx config: {e}")
            self.is_configured = False
    
    def create_proxies(self, count: int = 1) -> List[Dict[str, Any]]:
        """Create proxy endpoints."""
        if not self.is_configured:
            logger.error("FlareProx not configured")
            return []
        
        created_proxies = []
        
        for i in range(count):
            # Generate mock proxy endpoint
            worker_name = f"flareprox-{int(time.time())}-{i}"
            
            # Mock different IP addresses for testing
            mock_ips = [
                "203.0.113.1",  # TEST-NET-3
                "198.51.100.1", # TEST-NET-2
                "192.0.2.1",    # TEST-NET-1
                "203.0.113.42",
                "198.51.100.99"
            ]
            
            proxy_info = {
                "name": worker_name,
                "url": f"https://{worker_name}.mock-flareprox.workers.dev",
                "ip_address": random.choice(mock_ips),
                "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                "status": "active",
                "mock": True  # Indicate this is a mock endpoint
            }
            
            created_proxies.append(proxy_info)
            self.workers.append(proxy_info)
            
            logger.info(f"Created mock proxy: {proxy_info['url']} (IP: {proxy_info['ip_address']})")
        
        return created_proxies
    
    def cleanup_all(self):
        """Clean up all proxy endpoints."""
        if not self.is_configured:
            return
        
        for worker in self.workers:
            logger.info(f"Cleaning up mock proxy: {worker['name']}")
        
        self.workers = []
        logger.info("All mock proxies cleaned up")
    
    def list_proxies(self) -> List[Dict[str, Any]]:
        """List all proxy endpoints."""
        return self.workers
    
    def test_proxy(self, proxy_url: str) -> bool:
        """Test if a proxy endpoint is working."""
        # For mock implementation, always return True
        return True


# Mock worker script template
WORKER_SCRIPT_TEMPLATE = """
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  const targetUrl = url.searchParams.get('url')
  
  if (!targetUrl) {
    return new Response('Missing url parameter', { status: 400 })
  }
  
  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body
    })
    
    return response
  } catch (error) {
    return new Response('Proxy error: ' + error.message, { status: 500 })
  }
}
"""


if __name__ == "__main__":
    # Test the mock implementation
    print("🧪 Testing Mock FlareProx Implementation...")
    
    flareprox = FlareProx()
    
    if flareprox.is_configured:
        print("✅ FlareProx configured successfully")
        
        # Create test proxies
        proxies = flareprox.create_proxies(3)
        print(f"✅ Created {len(proxies)} mock proxies")
        
        for proxy in proxies:
            print(f"   - {proxy['name']}: {proxy['url']} (IP: {proxy['ip_address']})")
        
        # List proxies
        all_proxies = flareprox.list_proxies()
        print(f"✅ Listed {len(all_proxies)} total proxies")
        
        # Cleanup
        flareprox.cleanup_all()
        print("✅ Cleanup completed")
        
    else:
        print("❌ FlareProx configuration failed")
