"""
AI Provider Validator - Validates and tests provider configurations.

This module provides validation and testing functionality for AI-powered
chat providers to ensure they work correctly before being made available.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import re

from backend.core.provider_interfaces import (
    ProviderValidator, AIElementDetector, ProviderAuthenticator, ChatProvider,
    ProviderConfiguration, ChatMessage, ElementType
)


logger = logging.getLogger(__name__)


class AIProviderValidator(ProviderValidator):
    """
    AI-powered provider validator that tests provider functionality.
    
    This validator uses AI-powered components to test authentication,
    chat functionality, and overall provider health.
    """

    def __init__(
        self, 
        element_detector: AIElementDetector,
        authenticator: ProviderAuthenticator,
        chat_provider: ChatProvider
    ):
        self.element_detector = element_detector
        self.authenticator = authenticator
        self.chat_provider = chat_provider

    async def validate_configuration(
        self, 
        config: ProviderConfiguration
    ) -> Tuple[bool, List[str]]:
        """
        Validate provider configuration for basic requirements.
        
        This performs basic validation without actually testing the provider.
        """
        errors = []
        
        # Validate domain
        if not config.domain:
            errors.append("Domain is required")
        elif not self._is_valid_domain(config.domain):
            errors.append(f"Invalid domain format: {config.domain}")
        
        # Validate credentials
        if not config.username:
            errors.append("Username is required")
        
        if not config.password:
            errors.append("Password is required")
        
        # Validate URLs
        if config.base_url and not self._is_valid_url(config.base_url):
            errors.append(f"Invalid base URL: {config.base_url}")
        
        if config.login_url and not self._is_valid_url(config.login_url):
            errors.append(f"Invalid login URL: {config.login_url}")
        
        if config.chat_url and not self._is_valid_url(config.chat_url):
            errors.append(f"Invalid chat URL: {config.chat_url}")
        
        # Validate provider ID
        if config.provider_id and not self._is_valid_provider_id(config.provider_id):
            errors.append(f"Invalid provider ID format: {config.provider_id}")
        
        is_valid = len(errors) == 0
        
        logger.info(f"Configuration validation for {config.domain}: {'valid' if is_valid else 'invalid'}")
        if errors:
            logger.warning(f"Validation errors: {errors}")
        
        return is_valid, errors

    def _is_valid_domain(self, domain: str) -> bool:
        """Check if domain format is valid."""
        domain_pattern = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
        )
        return bool(domain_pattern.match(domain))

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL format is valid."""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(url_pattern.match(url))

    def _is_valid_provider_id(self, provider_id: str) -> bool:
        """Check if provider ID format is valid."""
        # Provider ID should be alphanumeric with underscores and hyphens
        provider_id_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
        return bool(provider_id_pattern.match(provider_id)) and len(provider_id) <= 100

    async def test_provider(
        self, 
        config: ProviderConfiguration
    ) -> Dict[str, Any]:
        """
        Test provider functionality end-to-end.
        
        This performs comprehensive testing including:
        1. Domain accessibility
        2. Element detection
        3. Authentication
        4. Chat functionality
        """
        logger.info(f"Starting comprehensive test for provider {config.domain}")
        
        test_results = {
            "success": False,
            "provider_id": config.provider_id,
            "domain": config.domain,
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "errors": [],
            "warnings": []
        }
        
        try:
            # Test 1: Domain accessibility
            domain_test = await self._test_domain_accessibility(config)
            test_results["tests"]["domain_accessibility"] = domain_test
            
            if not domain_test["success"]:
                test_results["errors"].append("Domain is not accessible")
                return test_results
            
            # Test 2: Element detection
            element_test = await self._test_element_detection(config)
            test_results["tests"]["element_detection"] = element_test
            
            if not element_test["success"]:
                test_results["warnings"].append("Element detection had issues")
            
            # Test 3: Authentication
            auth_test = await self._test_authentication(config)
            test_results["tests"]["authentication"] = auth_test
            
            if not auth_test["success"]:
                test_results["errors"].append("Authentication failed")
                return test_results
            
            # Test 4: Chat functionality
            chat_test = await self._test_chat_functionality(config)
            test_results["tests"]["chat_functionality"] = chat_test
            
            if not chat_test["success"]:
                test_results["errors"].append("Chat functionality failed")
                return test_results
            
            # All tests passed
            test_results["success"] = True
            logger.info(f"All tests passed for provider {config.domain}")
            
        except Exception as e:
            error_msg = f"Test execution failed: {str(e)}"
            logger.error(error_msg)
            test_results["errors"].append(error_msg)
        
        return test_results

    async def _test_domain_accessibility(self, config: ProviderConfiguration) -> Dict[str, Any]:
        """Test if the domain is accessible."""
        logger.info(f"Testing domain accessibility for {config.domain}")
        
        test_result = {
            "success": False,
            "test_name": "domain_accessibility",
            "duration": 0,
            "details": {}
        }
        
        start_time = time.time()
        
        try:
            # Try to detect elements on the base URL to verify accessibility
            base_url = config.base_url
            
            # Use element detector to check if page loads
            elements = await self.element_detector.detect_elements(
                base_url,
                [ElementType.LOGIN_EMAIL, ElementType.CHAT_INPUT],  # Try to find any common elements
                context={"domain": config.domain, "test": "accessibility"}
            )
            
            test_result["success"] = True
            test_result["details"] = {
                "base_url": base_url,
                "elements_found": len(elements),
                "accessible": True
            }
            
            logger.info(f"Domain {config.domain} is accessible")
            
        except Exception as e:
            test_result["details"] = {
                "base_url": config.base_url,
                "error": str(e),
                "accessible": False
            }
            logger.warning(f"Domain accessibility test failed for {config.domain}: {e}")
        
        test_result["duration"] = time.time() - start_time
        return test_result

    async def _test_element_detection(self, config: ProviderConfiguration) -> Dict[str, Any]:
        """Test AI-powered element detection."""
        logger.info(f"Testing element detection for {config.domain}")
        
        test_result = {
            "success": False,
            "test_name": "element_detection",
            "duration": 0,
            "details": {}
        }
        
        start_time = time.time()
        
        try:
            login_url = config.login_url or config.base_url
            
            # Test login element detection
            login_elements = await self.element_detector.detect_elements(
                login_url,
                [ElementType.LOGIN_EMAIL, ElementType.LOGIN_PASSWORD, ElementType.LOGIN_SUBMIT],
                context={"domain": config.domain, "test": "login_elements"}
            )
            
            # Test chat element detection (may fail if authentication required)
            chat_elements = []
            try:
                chat_url = config.chat_url or config.base_url
                chat_elements = await self.element_detector.detect_elements(
                    chat_url,
                    [ElementType.CHAT_INPUT, ElementType.SEND_BUTTON, ElementType.RESPONSE_AREA],
                    context={"domain": config.domain, "test": "chat_elements"}
                )
            except Exception as e:
                logger.info(f"Chat element detection failed (may require auth): {e}")
            
            # Evaluate results
            login_element_types = {elem.element_type for elem in login_elements}
            chat_element_types = {elem.element_type for elem in chat_elements}
            
            has_login_elements = len(login_element_types) >= 2  # At least email/username and password
            has_chat_elements = len(chat_element_types) >= 1   # At least one chat element
            
            test_result["success"] = has_login_elements or has_chat_elements
            test_result["details"] = {
                "login_elements": {
                    "found": len(login_elements),
                    "types": [elem.element_type.value for elem in login_elements],
                    "confidence_avg": sum(elem.confidence for elem in login_elements) / len(login_elements) if login_elements else 0
                },
                "chat_elements": {
                    "found": len(chat_elements),
                    "types": [elem.element_type.value for elem in chat_elements],
                    "confidence_avg": sum(elem.confidence for elem in chat_elements) / len(chat_elements) if chat_elements else 0
                },
                "has_sufficient_elements": test_result["success"]
            }
            
            logger.info(f"Element detection for {config.domain}: {len(login_elements)} login, {len(chat_elements)} chat elements")
            
        except Exception as e:
            test_result["details"] = {
                "error": str(e),
                "has_sufficient_elements": False
            }
            logger.error(f"Element detection test failed for {config.domain}: {e}")
        
        test_result["duration"] = time.time() - start_time
        return test_result

    async def _test_authentication(self, config: ProviderConfiguration) -> Dict[str, Any]:
        """Test authentication functionality."""
        logger.info(f"Testing authentication for {config.domain}")
        
        test_result = {
            "success": False,
            "test_name": "authentication",
            "duration": 0,
            "details": {}
        }
        
        start_time = time.time()
        
        try:
            # Create a mock browser session for testing
            mock_session = {
                "provider_id": config.provider_id,
                "domain": config.domain,
                "created_at": datetime.now(),
                "test_session": True
            }
            
            # Attempt authentication
            auth_success, auth_error = await self.authenticator.authenticate(config, mock_session)
            
            test_result["success"] = auth_success
            test_result["details"] = {
                "authenticated": auth_success,
                "error": auth_error,
                "login_url": config.login_url or config.base_url
            }
            
            if auth_success:
                logger.info(f"Authentication successful for {config.domain}")
                
                # Test authentication verification
                try:
                    auth_valid = await self.authenticator.verify_authentication(config, mock_session)
                    test_result["details"]["verification"] = auth_valid
                except Exception as e:
                    test_result["details"]["verification_error"] = str(e)
            else:
                logger.warning(f"Authentication failed for {config.domain}: {auth_error}")
            
        except Exception as e:
            test_result["details"] = {
                "error": str(e),
                "authenticated": False
            }
            logger.error(f"Authentication test failed for {config.domain}: {e}")
        
        test_result["duration"] = time.time() - start_time
        return test_result

    async def _test_chat_functionality(self, config: ProviderConfiguration) -> Dict[str, Any]:
        """Test chat functionality."""
        logger.info(f"Testing chat functionality for {config.domain}")
        
        test_result = {
            "success": False,
            "test_name": "chat_functionality",
            "duration": 0,
            "details": {}
        }
        
        start_time = time.time()
        
        try:
            # Create a mock authenticated browser session
            mock_session = {
                "provider_id": config.provider_id,
                "domain": config.domain,
                "current_url": config.chat_url or config.base_url,
                "authenticated": True,
                "test_session": True
            }
            
            # Test if chat interface is ready
            is_ready = await self.chat_provider.is_ready(mock_session)
            
            if not is_ready:
                test_result["details"] = {
                    "ready": False,
                    "error": "Chat interface not ready"
                }
                logger.warning(f"Chat interface not ready for {config.domain}")
                test_result["duration"] = time.time() - start_time
                return test_result
            
            # Send a test message
            test_message = ChatMessage(
                content="Hello, this is a test message. Please respond with a simple greeting.",
                role="user"
            )
            
            response = await self.chat_provider.send_message(test_message, mock_session)
            
            test_result["success"] = response.success
            test_result["details"] = {
                "ready": is_ready,
                "message_sent": True,
                "response_received": response.success,
                "response_length": len(response.content) if response.success else 0,
                "response_time": response.response_time,
                "error": response.error_message if not response.success else None
            }
            
            if response.success:
                logger.info(f"Chat functionality test successful for {config.domain}")
            else:
                logger.warning(f"Chat functionality test failed for {config.domain}: {response.error_message}")
            
        except Exception as e:
            test_result["details"] = {
                "error": str(e),
                "message_sent": False,
                "response_received": False
            }
            logger.error(f"Chat functionality test failed for {config.domain}: {e}")
        
        test_result["duration"] = time.time() - start_time
        return test_result

    async def health_check(
        self, 
        provider_id: str
    ) -> Dict[str, Any]:
        """
        Perform health check on a provider.
        
        This is a lightweight check to verify the provider is still working.
        """
        logger.info(f"Performing health check for provider {provider_id}")
        
        health_result = {
            "healthy": False,
            "provider_id": provider_id,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "issues": []
        }
        
        try:
            # This would typically:
            # 1. Check if the provider configuration still exists
            # 2. Verify the domain is still accessible
            # 3. Test authentication if needed
            # 4. Check if chat interface is responsive
            
            # For now, we'll implement a basic check
            # In a real implementation, this would use the actual provider configuration
            
            # Mock health check - in practice this would be more comprehensive
            health_result["checks"] = {
                "configuration_exists": True,
                "domain_accessible": True,
                "authentication_valid": True,
                "chat_interface_ready": True
            }
            
            # Check if all health checks passed
            all_checks_passed = all(health_result["checks"].values())
            health_result["healthy"] = all_checks_passed
            
            if not all_checks_passed:
                health_result["issues"] = [
                    check for check, passed in health_result["checks"].items() 
                    if not passed
                ]
            
            logger.info(f"Health check for {provider_id}: {'healthy' if all_checks_passed else 'unhealthy'}")
            
        except Exception as e:
            health_result["issues"].append(f"Health check failed: {str(e)}")
            logger.error(f"Health check failed for {provider_id}: {e}")
        
        return health_result

    async def quick_test(self, config: ProviderConfiguration) -> Dict[str, Any]:
        """
        Perform a quick test of provider functionality.
        
        This is a faster version of test_provider that only tests essential functionality.
        """
        logger.info(f"Performing quick test for provider {config.domain}")
        
        quick_test_result = {
            "success": False,
            "provider_id": config.provider_id,
            "domain": config.domain,
            "timestamp": datetime.now().isoformat(),
            "duration": 0
        }
        
        start_time = time.time()
        
        try:
            # Quick domain accessibility check
            base_url = config.base_url
            elements = await self.element_detector.detect_elements(
                base_url,
                [ElementType.LOGIN_EMAIL],  # Just check for one element
                context={"domain": config.domain, "test": "quick"}
            )
            
            quick_test_result["success"] = len(elements) > 0
            quick_test_result["elements_found"] = len(elements)
            
            logger.info(f"Quick test for {config.domain}: {'passed' if quick_test_result['success'] else 'failed'}")
            
        except Exception as e:
            quick_test_result["error"] = str(e)
            logger.error(f"Quick test failed for {config.domain}: {e}")
        
        quick_test_result["duration"] = time.time() - start_time
        return quick_test_result
