#!/usr/bin/env python3
"""
Simple test server to validate FlareProx integration without full AutoGPT dependencies.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import httpx

# Add the backend to Python path
backend_path = Path(__file__).parent.parent / "autogpt_platform" / "backend"
sys.path.insert(0, str(backend_path))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FlareProx Test Server", version="1.0.0")

# Global state
flareprox_manager = None
test_results = {}

@app.on_event("startup")
async def startup_event():
    """Initialize FlareProx on startup."""
    global flareprox_manager
    
    try:
        from backend.util.flareprox_integration import FlareProxManager, initialize_flareprox
        
        logger.info("Initializing FlareProx system...")
        flareprox_initialized = await initialize_flareprox()
        
        if flareprox_initialized:
            logger.info("✅ FlareProx system initialized successfully")
        else:
            logger.warning("⚠️ FlareProx system failed to initialize")
            
    except Exception as e:
        logger.error(f"❌ FlareProx initialization error: {e}")

@app.get("/v1/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/v1/models")
async def list_models():
    """List available models."""
    models = [
        {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "zai"},
        {"id": "qwen-max", "object": "model", "owned_by": "qwen"},
        {"id": "deepseek-chat", "object": "model", "owned_by": "deepseek"},
        {"id": "grok-beta", "object": "model", "owned_by": "grok"},
        {"id": "k2-think", "object": "model", "owned_by": "k2think"}
    ]
    return {"object": "list", "data": models}

@app.get("/v1/stats")
async def get_stats():
    """Get system statistics."""
    return {
        "flareprox_status": "initialized" if flareprox_manager else "not_initialized",
        "endpoints_count": len(getattr(flareprox_manager, 'endpoints', [])),
        "uptime": time.time(),
        "test_results": test_results
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Dict[str, Any]):
    """Mock chat completions endpoint."""
    
    # Validate request
    if "model" not in request or "messages" not in request:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    model = request["model"]
    messages = request["messages"]
    
    if not messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty")
    
    # Mock response based on model
    service_map = {
        "gpt-3.5-turbo": "Z.AI",
        "qwen-max": "Qwen.AI", 
        "deepseek-chat": "DeepSeek",
        "grok-beta": "Grok",
        "k2-think": "K2Think.AI"
    }
    
    service = service_map.get(model, "Unknown")
    last_message = messages[-1].get("content", "")
    
    # Simulate FlareProx usage
    flareprox_used = False
    ip_address = "127.0.0.1"
    
    try:
        from backend.util.flareprox_integration import get_proxied_url
        
        # Test FlareProx with a dummy URL
        test_url = "https://httpbin.org/ip"
        proxied_url = await get_proxied_url(test_url, use_random=True)
        
        if proxied_url != test_url:
            flareprox_used = True
            
            # Try to get actual IP through FlareProx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(proxied_url)
                if response.status_code == 200:
                    data = response.json()
                    ip_address = data.get("origin", "127.0.0.1")
                    
    except Exception as e:
        logger.warning(f"FlareProx test failed: {e}")
    
    # Generate mock response
    response_content = f"Hello! This is a mock response from {service}. You said: '{last_message}'"
    
    if flareprox_used:
        response_content += f" [Routed through FlareProx IP: {ip_address}]"
    
    response = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": len(str(messages)),
            "completion_tokens": len(response_content),
            "total_tokens": len(str(messages)) + len(response_content)
        },
        "flareprox_used": flareprox_used,
        "ip_address": ip_address
    }
    
    return response

@app.get("/test/flareprox")
async def test_flareprox():
    """Test FlareProx endpoints directly."""
    try:
        from backend.util.flareprox_integration import test_flareprox_endpoints
        
        results = await test_flareprox_endpoints()
        test_results["flareprox_test"] = results
        
        return results
        
    except Exception as e:
        logger.error(f"FlareProx test failed: {e}")
        return {"error": str(e)}

@app.get("/test/proxy/{path:path}")
async def test_proxy_url(path: str):
    """Test proxying a specific URL."""
    try:
        from backend.util.flareprox_integration import get_proxied_url
        
        target_url = f"https://{path}"
        proxied_url = await get_proxied_url(target_url, use_random=True)
        
        # Test the proxied URL
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(proxied_url)
            
            return {
                "target_url": target_url,
                "proxied_url": proxied_url,
                "status_code": response.status_code,
                "response_preview": response.text[:500] if response.status_code == 200 else None,
                "flareprox_used": proxied_url != target_url
            }
            
    except Exception as e:
        logger.error(f"Proxy test failed: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    print("🚀 Starting FlareProx Test Server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("🔍 Test endpoints:")
    print("   - GET  /v1/health")
    print("   - GET  /v1/models") 
    print("   - GET  /v1/stats")
    print("   - POST /v1/chat/completions")
    print("   - GET  /test/flareprox")
    print("   - GET  /test/proxy/{url}")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
