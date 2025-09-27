"""
Pytest configuration and fixtures for chat proxy integration tests.
"""

import asyncio
import os
import pytest
import logging
from typing import Dict, Any, AsyncGenerator
from unittest.mock import AsyncMock

# Set up logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
TEST_CONFIG = {
    "stagehand_api_key": os.getenv("TEST_STAGEHAND_API_KEY", "test-key"),
    "browserbase_project_id": os.getenv("TEST_BROWSERBASE_PROJECT_ID", "test-project"),
    "test_timeout": int(os.getenv("TEST_TIMEOUT", "300")),  # 5 minutes
    "api_base_url": os.getenv("TEST_API_BASE_URL", "http://localhost:8000"),
    "enable_real_services": os.getenv("ENABLE_REAL_SERVICES", "false").lower() == "true",
}

# Test accounts configuration
TEST_ACCOUNTS = {
    "zai": {
        "email": os.getenv("TEST_ZAI_EMAIL", "test@example.com"),
        "password": os.getenv("TEST_ZAI_PASSWORD", "test-password"),
    },
    "qwen": {
        "email": os.getenv("TEST_QWEN_EMAIL", "test@example.com"),
        "password": os.getenv("TEST_QWEN_PASSWORD", "test-password"),
    },
    "deepseek": {
        "email": os.getenv("TEST_DEEPSEEK_EMAIL", "test@example.com"),
        "password": os.getenv("TEST_DEEPSEEK_PASSWORD", "test-password"),
    },
    "k2think": {
        "email": os.getenv("TEST_K2THINK_EMAIL", "test@example.com"),
        "password": os.getenv("TEST_K2THINK_PASSWORD", "test-password"),
    },
    "grok": {
        "email": os.getenv("TEST_GROK_EMAIL", "test@example.com"),
        "password": os.getenv("TEST_GROK_PASSWORD", "test-password"),
    },
}


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Provide test configuration."""
    return TEST_CONFIG.copy()


@pytest.fixture
def test_accounts() -> Dict[str, Dict[str, str]]:
    """Provide test account credentials."""
    return TEST_ACCOUNTS.copy()


@pytest.fixture
async def api_client():
    """Create an HTTP client for API testing."""
    import httpx
    
    async with httpx.AsyncClient(
        base_url=TEST_CONFIG["api_base_url"],
        timeout=TEST_CONFIG["test_timeout"]
    ) as client:
        yield client


@pytest.fixture
def stagehand_credentials():
    """Provide Stagehand credentials for testing."""
    return {
        "api_key": TEST_CONFIG["stagehand_api_key"],
        "project_id": TEST_CONFIG["browserbase_project_id"],
    }


@pytest.fixture
async def chat_proxy_server():
    """Start the chat proxy server for testing."""
    if not TEST_CONFIG["enable_real_services"]:
        # For unit tests, we'll mock the server
        yield AsyncMock()
        return
    
    # For integration tests, we assume the server is already running
    # In a real CI environment, you'd start the server here
    import httpx
    
    # Wait for server to be ready
    max_retries = 30
    for i in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{TEST_CONFIG['api_base_url']}/api/v1/health")
                if response.status_code == 200:
                    logger.info("Chat proxy server is ready")
                    break
        except Exception as e:
            if i == max_retries - 1:
                pytest.skip(f"Chat proxy server not available: {e}")
            await asyncio.sleep(1)
    
    yield "server_running"


@pytest.fixture
def openai_client():
    """Create an OpenAI client configured to use our proxy."""
    try:
        import openai
    except ImportError:
        pytest.skip("OpenAI client library not installed")
    
    client = openai.AsyncOpenAI(
        api_key="test-key",  # Our proxy doesn't validate this
        base_url=f"{TEST_CONFIG['api_base_url']}/api/v1"
    )
    
    return client


@pytest.fixture
async def stagehand_client():
    """Create a Stagehand client for browser automation testing."""
    if not TEST_CONFIG["enable_real_services"]:
        # Mock Stagehand for unit tests
        mock_stagehand = AsyncMock()
        mock_page = AsyncMock()
        mock_stagehand.page = mock_page
        mock_stagehand.init = AsyncMock()
        yield mock_stagehand
        return
    
    try:
        from stagehand import Stagehand
    except ImportError:
        pytest.skip("Stagehand not installed")
    
    if not TEST_CONFIG["stagehand_api_key"] or TEST_CONFIG["stagehand_api_key"] == "test-key":
        pytest.skip("Real Stagehand API key not provided")
    
    stagehand = Stagehand(
        api_key=TEST_CONFIG["stagehand_api_key"],
        project_id=TEST_CONFIG["browserbase_project_id"],
        model_name="claude-3-5-sonnet-20241022"
    )
    
    try:
        await stagehand.init()
        yield stagehand
    finally:
        # Cleanup
        if hasattr(stagehand, 'close'):
            await stagehand.close()


@pytest.fixture
def skip_if_no_real_services():
    """Skip test if real services are not enabled."""
    if not TEST_CONFIG["enable_real_services"]:
        pytest.skip("Real services not enabled (set ENABLE_REAL_SERVICES=true)")


@pytest.fixture
def skip_if_no_credentials():
    """Skip test if required credentials are not provided."""
    required_vars = [
        "TEST_STAGEHAND_API_KEY",
        "TEST_BROWSERBASE_PROJECT_ID",
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        pytest.skip(f"Required environment variables not set: {', '.join(missing_vars)}")


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "real_services: mark test as requiring real services"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add integration marker to all tests in integration directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add real_services marker to tests that need real services
        if "real_services" in item.keywords or "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.real_services)


# Test utilities
class TestUtils:
    """Utility functions for tests."""
    
    @staticmethod
    async def wait_for_condition(condition_func, timeout=30, interval=1):
        """Wait for a condition to be true."""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if await condition_func():
                return True
            await asyncio.sleep(interval)
        
        return False
    
    @staticmethod
    def create_test_message(content="Hello, this is a test message"):
        """Create a test message for chat testing."""
        return {
            "role": "user",
            "content": content
        }
    
    @staticmethod
    def create_openai_request(model="gpt-3.5-turbo", messages=None, **kwargs):
        """Create an OpenAI-compatible request."""
        if messages is None:
            messages = [TestUtils.create_test_message()]
        
        return {
            "model": model,
            "messages": messages,
            **kwargs
        }


@pytest.fixture
def test_utils():
    """Provide test utilities."""
    return TestUtils
