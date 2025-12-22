#!/usr/bin/env python3
"""
Start the chat proxy server for testing.
"""

import sys
import os
import uvicorn
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "autogpt_platform" / "backend"
sys.path.insert(0, str(backend_dir))

def main():
    """Start the chat proxy server."""
    print("🚀 Starting Chat Proxy Server...")
    print("Server will be available at: http://localhost:8000")
    print("OpenAI API endpoints:")
    print("  - POST /v1/chat/completions")
    print("  - GET /v1/models")
    print("  - GET /v1/health")
    print("  - GET /v1/stats")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Set up environment variables
    os.environ.setdefault("STAGEHAND_API_KEY", "your-stagehand-api-key")
    os.environ.setdefault("BROWSERBASE_PROJECT_ID", "your-browserbase-project-id")
    
    try:
        # Import and start the FastAPI app
        from backend.server.main import app
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            reload=False
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
