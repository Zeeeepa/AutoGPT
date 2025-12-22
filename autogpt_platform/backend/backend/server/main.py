"""
Main FastAPI application entry point for the chat proxy server.
"""

from backend.server.rest_api import app

# Export the app for uvicorn
__all__ = ["app"]
