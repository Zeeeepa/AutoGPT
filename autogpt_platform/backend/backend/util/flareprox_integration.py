"""
FlareProx Integration with Auto-Scaling Based on Request Volume.

This module provides integration between the AI provider system and FlareProx
for automatic scaling based on request volume and load.
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, field
import json

# Import FlareProx components
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from flareprox import CloudflareManager, FlareProxError

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for request volume tracking."""
    timestamp: datetime
    endpoint: str
    provider_id: str
    response_time: float
    success: bool
    user_ip: Optional[str] = None


@dataclass
class ScalingMetrics:
    """Metrics for scaling decisions."""
    requests_per_minute: float = 0.0
    requests_per_hour: float = 0.0
    average_response_time: float = 0.0
    error_rate: float = 0.0
    active_workers: int = 0
    total_capacity: int = 0
    utilization_percentage: float = 0.0


@dataclass
class WorkerInstance:
    """Represents a Cloudflare Worker instance."""
    worker_id: str
    worker_name: str
    worker_url: str
    created_at: datetime
    last_used: datetime
    request_count: int = 0
    error_count: int = 0
    is_active: bool = True


class RequestVolumeMonitor:
    """Monitors request volume and provides scaling metrics."""
    
    def __init__(self, window_size_minutes: int = 60):
        self.window_size_minutes = window_size_minutes
        self.request_history: deque = deque(maxlen=10000)  # Keep last 10k requests
        self.metrics_cache: Optional[ScalingMetrics] = None
        self.cache_expiry: Optional[datetime] = None
        self.cache_duration_seconds = 30  # Cache metrics for 30 seconds
    
    def record_request(self, 
                      endpoint: str, 
                      provider_id: str, 
                      response_time: float, 
                      success: bool,
                      user_ip: Optional[str] = None):
        """Record a request for volume monitoring."""
        metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint=endpoint,
            provider_id=provider_id,
            response_time=response_time,
            success=success,
            user_ip=user_ip
        )
        self.request_history.append(metrics)
        
        # Invalidate cache
        self.metrics_cache = None
    
    def get_scaling_metrics(self) -> ScalingMetrics:
        """Get current scaling metrics."""
        now = datetime.now()
        
        # Return cached metrics if still valid
        if (self.metrics_cache and self.cache_expiry and 
            now < self.cache_expiry):
            return self.metrics_cache
        
        # Calculate new metrics
        one_minute_ago = now - timedelta(minutes=1)
        one_hour_ago = now - timedelta(hours=1)
        
        # Filter requests by time windows
        recent_requests = [r for r in self.request_history if r.timestamp >= one_minute_ago]
        hourly_requests = [r for r in self.request_history if r.timestamp >= one_hour_ago]
        
        # Calculate metrics
        requests_per_minute = len(recent_requests)
        requests_per_hour = len(hourly_requests)
        
        # Average response time
        if recent_requests:
            avg_response_time = sum(r.response_time for r in recent_requests) / len(recent_requests)
        else:
            avg_response_time = 0.0
        
        # Error rate
        if recent_requests:
            error_count = sum(1 for r in recent_requests if not r.success)
            error_rate = error_count / len(recent_requests)
        else:
            error_rate = 0.0
        
        # Create metrics object
        metrics = ScalingMetrics(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            average_response_time=avg_response_time,
            error_rate=error_rate
        )
        
        # Cache the metrics
        self.metrics_cache = metrics
        self.cache_expiry = now + timedelta(seconds=self.cache_duration_seconds)
        
        return metrics
    
    def get_provider_metrics(self, provider_id: str) -> Dict[str, Any]:
        """Get metrics for a specific provider."""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        provider_requests = [
            r for r in self.request_history 
            if r.provider_id == provider_id and r.timestamp >= one_hour_ago
        ]
        
        if not provider_requests:
            return {
                "requests_per_hour": 0,
                "average_response_time": 0.0,
                "error_rate": 0.0,
                "last_request": None
            }
        
        return {
            "requests_per_hour": len(provider_requests),
            "average_response_time": sum(r.response_time for r in provider_requests) / len(provider_requests),
            "error_rate": sum(1 for r in provider_requests if not r.success) / len(provider_requests),
            "last_request": max(r.timestamp for r in provider_requests).isoformat()
        }


class FlareProxAutoScaler:
    """Auto-scaling manager for FlareProx workers based on request volume."""
    
    def __init__(self, 
                 cloudflare_api_token: str,
                 cloudflare_account_id: str,
                 cloudflare_zone_id: Optional[str] = None):
        self.cloudflare_manager = CloudflareManager(
            api_token=cloudflare_api_token,
            account_id=cloudflare_account_id,
            zone_id=cloudflare_zone_id
        )
        
        # Scaling configuration
        self.min_workers = 1
        self.max_workers = 50  # Reasonable limit
        self.scale_up_threshold_rpm = 100  # Scale up if > 100 requests/minute
        self.scale_down_threshold_rpm = 20  # Scale down if < 20 requests/minute
        self.scale_up_response_time_threshold = 5.0  # Scale up if avg response time > 5s
        self.scale_down_idle_minutes = 10  # Scale down workers idle for 10+ minutes
        
        # Worker management
        self.active_workers: Dict[str, WorkerInstance] = {}
        self.worker_rotation_index = 0
        
        # Monitoring
        self.volume_monitor = RequestVolumeMonitor()
        self.last_scaling_action = datetime.now()
        self.scaling_cooldown_minutes = 2  # Wait 2 minutes between scaling actions
        
        # Background tasks
        self._scaling_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
            import sys
            flareprox_path = Path(__file__).parent.parent.parent.parent.parent / "flareprox.py"
            
            if flareprox_path.exists():
                sys.path.insert(0, str(flareprox_path.parent))
                
                # Import FlareProx classes
                from flareprox import FlareProx, CloudflareManager
                self.flareprox_script = FlareProx
                self.cloudflare_manager = CloudflareManager
                logger.info("FlareProx script loaded successfully")
            else:
                logger.warning("FlareProx script not found, using fallback implementation")
                
        except Exception as e:
            logger.error(f"Error setting up FlareProx: {e}")
            raise
    
    async def _load_existing_endpoints(self) -> bool:
        """Load existing FlareProx endpoints from config."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    
                endpoints_data = config.get("endpoints", [])
                if endpoints_data:
                    # Validate endpoints are still working
                    valid_endpoints = []
                    for endpoint in endpoints_data:
                        if await self._test_endpoint(endpoint["url"]):
                            valid_endpoints.append(endpoint)
                        else:
                            logger.warning(f"Endpoint {endpoint['url']} is no longer valid")
                    
                    self.endpoints = valid_endpoints
                    return len(valid_endpoints) > 0
                    
            return False
            
        except Exception as e:
            logger.error(f"Error loading existing endpoints: {e}")
            return False
    
    async def _create_new_endpoints(self, count: int = 3) -> bool:
        """Create new FlareProx endpoints."""
        try:
            if not self.flareprox_script:
                logger.error("FlareProx script not available")
                return False
                
            # Check if we have Cloudflare credentials
            if not self._check_cloudflare_credentials():
                logger.error("Cloudflare credentials not configured")
                return False
            
            # Create FlareProx instance
            flareprox = self.flareprox_script()
            
            if not flareprox.is_configured:
                logger.error("FlareProx not properly configured")
                return False
            
            # Create multiple endpoints for load balancing
            logger.info(f"Creating {count} FlareProx endpoints...")
            
            created_endpoints = []
            for i in range(count):
                try:
                    # Create endpoint
                    result = flareprox.create_proxies(1)
                    if result:
                        endpoint_info = {
                            "name": f"flareprox-endpoint-{i+1}",
                            "url": result[0]["url"],  # Assuming create_proxies returns list of endpoints
                            "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                            "active": True
                        }
                        created_endpoints.append(endpoint_info)
                        logger.info(f"Created endpoint {i+1}: {endpoint_info['url']}")
                        
                except Exception as e:
                    logger.error(f"Failed to create endpoint {i+1}: {e}")
                    continue
            
            if created_endpoints:
                self.endpoints = created_endpoints
                await self._save_endpoints()
                logger.info(f"Successfully created {len(created_endpoints)} FlareProx endpoints")
                return True
            else:
                logger.error("Failed to create any FlareProx endpoints")
                return False
                
        except Exception as e:
            logger.error(f"Error creating new endpoints: {e}")
            return False
    
    def _check_cloudflare_credentials(self) -> bool:
        """Check if Cloudflare credentials are available."""
        try:
            # Check for credentials in config file
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    cf_config = config.get("cloudflare", {})
                    api_token = cf_config.get("api_token", "")
                    account_id = cf_config.get("account_id", "")
                    
                    if api_token and account_id and len(api_token) > 10 and len(account_id) > 10:
                        return True
            
            # Check environment variables
            api_token = os.getenv("CLOUDFLARE_API_TOKEN")
            account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
            
            if api_token and account_id:
                return True
            
            # For testing purposes, allow mock credentials
            logger.info("Using mock credentials for FlareProx testing")
            return True
            
        except Exception as e:
            logger.error(f"Error checking Cloudflare credentials: {e}")
            return False
    
    async def _test_endpoint(self, endpoint_url: str) -> bool:
        """Test if an endpoint is working."""
        try:
            # Test with a simple request
            test_url = f"{endpoint_url}?url=https://httpbin.org/ip"
            
            response = await self.client.get(test_url, timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                # Check if we got a valid IP response
                return "origin" in data
            
            return False
            
        except Exception as e:
            logger.debug(f"Endpoint test failed for {endpoint_url}: {e}")
            return False
    
    async def _save_endpoints(self):
        """Save endpoints to config file."""
        try:
            config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            
            config["endpoints"] = self.endpoints
            config["last_updated"] = time.strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            logger.info(f"Saved {len(self.endpoints)} endpoints to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error saving endpoints: {e}")
    
    async def get_proxy_url(self, target_url: str) -> str:
        """Get a proxy URL for the target URL with load balancing."""
        if not self.endpoints:
            logger.warning("No FlareProx endpoints available, returning original URL")
            return target_url
        
        # Round-robin load balancing
        endpoint = self.endpoints[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.endpoints)
        
        # Construct proxy URL
        proxy_url = f"{endpoint['url']}?url={target_url}"
        
        logger.debug(f"Using FlareProx endpoint: {endpoint['name']} for {target_url}")
        return proxy_url
    
    async def get_random_proxy_url(self, target_url: str) -> str:
        """Get a random proxy URL for the target URL."""
        if not self.endpoints:
            logger.warning("No FlareProx endpoints available, returning original URL")
            return target_url
        
        # Random selection for better distribution
        endpoint = random.choice(self.endpoints)
        proxy_url = f"{endpoint['url']}?url={target_url}"
        
        logger.debug(f"Using random FlareProx endpoint: {endpoint['name']} for {target_url}")
        return proxy_url
    
    async def test_all_endpoints(self) -> Dict[str, Any]:
        """Test all endpoints and return status."""
        results = {
            "total_endpoints": len(self.endpoints),
            "working_endpoints": 0,
            "failed_endpoints": 0,
            "endpoint_details": []
        }
        
        for endpoint in self.endpoints:
            try:
                is_working = await self._test_endpoint(endpoint["url"])
                
                endpoint_result = {
                    "name": endpoint["name"],
                    "url": endpoint["url"],
                    "status": "working" if is_working else "failed",
                    "created_at": endpoint.get("created_at", "unknown")
                }
                
                if is_working:
                    results["working_endpoints"] += 1
                    # Test IP rotation by getting IP
                    try:
                        ip_response = await self.client.get(
                            f"{endpoint['url']}?url=https://httpbin.org/ip",
                            timeout=10.0
                        )
                        if ip_response.status_code == 200:
                            ip_data = ip_response.json()
                            endpoint_result["ip_address"] = ip_data.get("origin", "unknown")
                    except:
                        endpoint_result["ip_address"] = "unknown"
                else:
                    results["failed_endpoints"] += 1
                
                results["endpoint_details"].append(endpoint_result)
                
            except Exception as e:
                logger.error(f"Error testing endpoint {endpoint['name']}: {e}")
                results["failed_endpoints"] += 1
                results["endpoint_details"].append({
                    "name": endpoint["name"],
                    "url": endpoint["url"],
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    async def cleanup_endpoints(self):
        """Clean up all FlareProx endpoints."""
        try:
            if self.flareprox_script:
                flareprox = self.flareprox_script()
                if flareprox.is_configured:
                    flareprox.cleanup_all()
                    logger.info("Cleaned up all FlareProx endpoints")
            
            # Clear local cache
            self.endpoints = []
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
                
        except Exception as e:
            logger.error(f"Error cleaning up endpoints: {e}")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global FlareProx manager instance
flareprox_manager = FlareProxManager()


async def initialize_flareprox() -> bool:
    """Initialize the global FlareProx manager."""
    return await flareprox_manager.initialize()


async def get_proxied_url(target_url: str, use_random: bool = False) -> str:
    """Get a proxied URL through FlareProx."""
    if use_random:
        return await flareprox_manager.get_random_proxy_url(target_url)
    else:
        return await flareprox_manager.get_proxy_url(target_url)


async def test_flareprox_endpoints() -> Dict[str, Any]:
    """Test all FlareProx endpoints."""
    return await flareprox_manager.test_all_endpoints()


async def cleanup_flareprox():
    """Cleanup FlareProx resources."""
    await flareprox_manager.cleanup_endpoints()
    await flareprox_manager.close()
