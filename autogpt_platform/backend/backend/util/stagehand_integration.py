"""
Stagehand Integration for AI-powered browser automation.

This module provides the implementation of AI-powered element detection
and browser automation using the Stagehand service.
"""

import asyncio
import logging
import os
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import aiohttp
import base64

from backend.core.provider_interfaces import (
    AIElementDetector, ProviderAuthenticator, ChatProvider,
    ElementDetectionResult, ElementType, ProviderConfiguration,
    ChatMessage, ChatResponse
)


logger = logging.getLogger(__name__)


class StagehandElementDetector(AIElementDetector):
    """
    AI-powered element detector using Stagehand.
    
    This implementation uses Stagehand's AI capabilities to detect and interact
    with web elements without requiring hardcoded selectors.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.stagehand.dev"):
        self.api_key = api_key or os.getenv("STAGEHAND_API_KEY")
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        
        if not self.api_key:
            logger.warning("No Stagehand API key provided - AI detection will be limited")

    async def _ensure_session(self):
        """Ensure HTTP session is available."""
        if not self.session:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            )

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def detect_elements(
        self, 
        page_url: str, 
        element_types: List[ElementType],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ElementDetectionResult]:
        """
        Detect UI elements on a page using Stagehand AI.
        
        This method uses Stagehand's AI to analyze the page and find elements
        based on their semantic meaning rather than hardcoded selectors.
        """
        logger.info(f"Detecting elements on {page_url}: {[et.value for et in element_types]}")
        
        await self._ensure_session()
        
        if not self.api_key:
            # Fallback to basic heuristic detection
            return await self._fallback_detection(page_url, element_types, context)
        
        results = []
        
        try:
            # Create detection prompts for each element type
            detection_tasks = []
            for element_type in element_types:
                prompt = self._create_detection_prompt(element_type, context)
                detection_tasks.append(self._detect_single_element(page_url, element_type, prompt))
            
            # Execute all detection tasks concurrently
            detection_results = await asyncio.gather(*detection_tasks, return_exceptions=True)
            
            for i, result in enumerate(detection_results):
                if isinstance(result, Exception):
                    logger.warning(f"Detection failed for {element_types[i]}: {result}")
                    continue
                
                if result:
                    results.append(result)
            
            logger.info(f"Detected {len(results)} elements on {page_url}")
            
        except Exception as e:
            logger.error(f"Element detection failed for {page_url}: {e}")
            # Try fallback detection
            results = await self._fallback_detection(page_url, element_types, context)
        
        return results

    async def _detect_single_element(
        self, 
        page_url: str, 
        element_type: ElementType, 
        prompt: str
    ) -> Optional[ElementDetectionResult]:
        """Detect a single element using Stagehand AI."""
        try:
            payload = {
                "url": page_url,
                "instruction": prompt,
                "action": "observe",
                "modelName": "claude-3-5-sonnet-20241022",
                "domSettleTimeoutMs": 3000
            }
            
            async with self.session.post(f"{self.base_url}/v1/act", json=payload) as response:
                if response.status != 200:
                    logger.warning(f"Stagehand API error {response.status}: {await response.text()}")
                    return None
                
                data = await response.json()
                
                # Parse Stagehand response to extract element information
                return self._parse_stagehand_response(data, element_type)
                
        except Exception as e:
            logger.error(f"Stagehand detection error for {element_type}: {e}")
            return None

    def _create_detection_prompt(self, element_type: ElementType, context: Optional[Dict[str, Any]]) -> str:
        """Create AI prompt for detecting specific element types."""
        domain = context.get("domain", "this website") if context else "this website"
        purpose = context.get("purpose", "interaction") if context else "interaction"
        
        prompts = {
            ElementType.LOGIN_EMAIL: f"Find the email or username input field on {domain}. This is typically labeled 'Email', 'Username', 'Login', or similar. Look for input fields that accept email addresses or usernames for authentication.",
            
            ElementType.LOGIN_PASSWORD: f"Find the password input field on {domain}. This is typically labeled 'Password' and is an input field with type='password' or similar security masking.",
            
            ElementType.LOGIN_SUBMIT: f"Find the login or sign-in button on {domain}. This is typically a button labeled 'Login', 'Sign In', 'Submit', or similar that submits the login form.",
            
            ElementType.CHAT_INPUT: f"Find the main chat input field or text area on {domain}. This is where users type their messages to send to the AI or chat system. Look for text areas, input fields, or contenteditable elements that accept chat messages.",
            
            ElementType.SEND_BUTTON: f"Find the send button for the chat interface on {domain}. This is typically labeled 'Send', has a send icon (arrow, paper plane), or is positioned next to the chat input field.",
            
            ElementType.RESPONSE_AREA: f"Find the area where chat responses or AI messages are displayed on {domain}. This is typically a scrollable container, div, or section that shows the conversation history or AI responses.",
            
            ElementType.ERROR_MESSAGE: f"Find any error message or alert on {domain}. Look for elements that display error text, warnings, or failure notifications.",
            
            ElementType.SUCCESS_INDICATOR: f"Find any success indicator or confirmation message on {domain}. Look for elements that show successful operations, checkmarks, or positive feedback."
        }
        
        base_prompt = prompts.get(element_type, f"Find elements related to {element_type.value} on {domain}")
        
        return f"{base_prompt} Return the most likely element that matches this description. Focus on elements that are currently visible and interactive."

    def _parse_stagehand_response(self, data: Dict[str, Any], element_type: ElementType) -> Optional[ElementDetectionResult]:
        """Parse Stagehand API response to extract element information."""
        try:
            # Stagehand returns observation data with element information
            observation = data.get("observation", "")
            
            # Try to extract selector information from the observation
            # This is a simplified parser - in practice, you'd need more sophisticated parsing
            selector = self._extract_selector_from_observation(observation)
            
            if selector:
                return ElementDetectionResult(
                    element_type=element_type,
                    selector=selector,
                    confidence=0.8,  # Stagehand AI confidence
                    detection_method="stagehand_ai",
                    timestamp=datetime.now()
                )
            
        except Exception as e:
            logger.error(f"Failed to parse Stagehand response: {e}")
        
        return None

    def _extract_selector_from_observation(self, observation: str) -> Optional[str]:
        """Extract CSS selector from Stagehand observation text."""
        # This is a simplified implementation
        # In practice, you'd need more sophisticated parsing of the AI observation
        
        # Look for common selector patterns in the observation
        import re
        
        # Try to find CSS selectors in the observation
        selector_patterns = [
            r'selector[:\s]+["\']([^"\']+)["\']',
            r'element[:\s]+["\']([^"\']+)["\']',
            r'#[\w-]+',  # ID selectors
            r'\.[\w-]+',  # Class selectors
            r'\[[\w-]+[=~|^$*]*["\']?[^"\']*["\']?\]',  # Attribute selectors
        ]
        
        for pattern in selector_patterns:
            matches = re.findall(pattern, observation, re.IGNORECASE)
            if matches:
                return matches[0] if isinstance(matches[0], str) else matches[0][0]
        
        # If no selector found, try to extract from common phrases
        if "input" in observation.lower() and "email" in observation.lower():
            return 'input[type="email"], input[name*="email"], input[placeholder*="email"]'
        elif "input" in observation.lower() and "password" in observation.lower():
            return 'input[type="password"]'
        elif "button" in observation.lower() and ("login" in observation.lower() or "sign" in observation.lower()):
            return 'button[type="submit"], input[type="submit"], button:contains("Login"), button:contains("Sign")'
        
        return None

    async def _fallback_detection(
        self, 
        page_url: str, 
        element_types: List[ElementType],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ElementDetectionResult]:
        """Fallback element detection using heuristic selectors."""
        logger.info(f"Using fallback detection for {page_url}")
        
        # Common selector patterns for different element types
        fallback_selectors = {
            ElementType.LOGIN_EMAIL: [
                'input[type="email"]',
                'input[name*="email"]',
                'input[placeholder*="email" i]',
                'input[name*="username"]',
                'input[placeholder*="username" i]',
                '#email',
                '#username',
                '.email-input',
                '.username-input'
            ],
            ElementType.LOGIN_PASSWORD: [
                'input[type="password"]',
                'input[name*="password"]',
                '#password',
                '.password-input'
            ],
            ElementType.LOGIN_SUBMIT: [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:contains("Login")',
                'button:contains("Sign in")',
                'button:contains("Log in")',
                '.login-button',
                '.submit-button'
            ],
            ElementType.CHAT_INPUT: [
                'textarea[placeholder*="message" i]',
                'textarea[placeholder*="chat" i]',
                'input[placeholder*="message" i]',
                'div[contenteditable="true"]',
                '.chat-input',
                '.message-input',
                '#chat-input',
                '#message-input'
            ],
            ElementType.SEND_BUTTON: [
                'button:contains("Send")',
                'button[title*="send" i]',
                'button[aria-label*="send" i]',
                '.send-button',
                '.submit-button',
                'button[type="submit"]'
            ],
            ElementType.RESPONSE_AREA: [
                '.chat-messages',
                '.conversation',
                '.messages',
                '.chat-history',
                '.response-area',
                '#messages',
                '#chat-messages'
            ]
        }
        
        results = []
        
        for element_type in element_types:
            selectors = fallback_selectors.get(element_type, [])
            if selectors:
                # Use the first selector as a fallback
                results.append(ElementDetectionResult(
                    element_type=element_type,
                    selector=selectors[0],
                    confidence=0.5,  # Lower confidence for fallback
                    detection_method="fallback_heuristic",
                    timestamp=datetime.now()
                ))
        
        return results

    async def verify_element(
        self, 
        page_url: str, 
        selector: str, 
        element_type: ElementType
    ) -> bool:
        """Verify that an element selector is still valid using Stagehand."""
        try:
            await self._ensure_session()
            
            if not self.api_key:
                # Can't verify without API access
                return True  # Assume valid
            
            payload = {
                "url": page_url,
                "instruction": f"Check if there is an element matching the selector '{selector}' that appears to be a {element_type.value.replace('_', ' ')}. Return true if found and appears correct, false otherwise.",
                "action": "observe",
                "modelName": "claude-3-5-sonnet-20241022"
            }
            
            async with self.session.post(f"{self.base_url}/v1/act", json=payload) as response:
                if response.status != 200:
                    return False
                
                data = await response.json()
                observation = data.get("observation", "").lower()
                
                # Simple verification based on observation content
                return "true" in observation or "found" in observation or "exists" in observation
                
        except Exception as e:
            logger.error(f"Element verification failed: {e}")
            return False

    async def adapt_to_changes(
        self, 
        page_url: str, 
        failed_selector: str, 
        element_type: ElementType
    ) -> Optional[ElementDetectionResult]:
        """Adapt to UI changes by finding new selectors."""
        logger.info(f"Adapting to UI changes for {element_type} on {page_url}")
        
        # Re-detect the element with additional context about the failure
        context = {
            "failed_selector": failed_selector,
            "adaptation": True
        }
        
        results = await self.detect_elements(page_url, [element_type], context)
        
        if results:
            result = results[0]
            # Mark as adapted
            result.detection_method = "ai_adaptation"
            logger.info(f"Successfully adapted selector for {element_type}: {result.selector}")
            return result
        
        logger.warning(f"Failed to adapt selector for {element_type} on {page_url}")
        return None


class StagehandAuthenticator(ProviderAuthenticator):
    """
    AI-powered authenticator using Stagehand for login automation.
    """

    def __init__(self, element_detector: StagehandElementDetector):
        self.element_detector = element_detector

    async def authenticate(
        self, 
        config: ProviderConfiguration,
        browser_session: Any
    ) -> Tuple[bool, Optional[str]]:
        """
        Authenticate with a provider using AI-powered automation.
        """
        logger.info(f"Authenticating with {config.domain}")
        
        try:
            login_url = config.login_url or config.base_url
            
            # Detect login elements if not already cached
            if not config.custom_selectors:
                login_elements = await self.element_detector.detect_elements(
                    login_url,
                    [ElementType.LOGIN_EMAIL, ElementType.LOGIN_PASSWORD, ElementType.LOGIN_SUBMIT]
                )
                
                # Cache detected selectors
                config.custom_selectors = {}
                for element in login_elements:
                    config.custom_selectors[element.element_type] = element.selector
            
            # Perform authentication using Stagehand
            success = await self._perform_stagehand_login(config, login_url)
            
            if success:
                logger.info(f"Successfully authenticated with {config.domain}")
                return True, None
            else:
                return False, "Authentication failed"
                
        except Exception as e:
            error_msg = f"Authentication error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def _perform_stagehand_login(self, config: ProviderConfiguration, login_url: str) -> bool:
        """Perform login using Stagehand AI automation."""
        try:
            await self.element_detector._ensure_session()
            
            if not self.element_detector.api_key:
                return False
            
            # Create login instruction for Stagehand
            instruction = f"""
            Navigate to {login_url} and log in with the following credentials:
            - Email/Username: {config.username}
            - Password: {config.password}
            
            Steps:
            1. Find and fill the email/username field
            2. Find and fill the password field  
            3. Click the login/submit button
            4. Wait for the login to complete
            
            Return success if login is successful, or describe any errors encountered.
            """
            
            payload = {
                "url": login_url,
                "instruction": instruction,
                "action": "act",
                "modelName": "claude-3-5-sonnet-20241022",
                "domSettleTimeoutMs": 5000
            }
            
            async with self.element_detector.session.post(
                f"{self.element_detector.base_url}/v1/act", 
                json=payload
            ) as response:
                if response.status != 200:
                    logger.error(f"Stagehand login failed: {response.status}")
                    return False
                
                data = await response.json()
                observation = data.get("observation", "").lower()
                
                # Check for success indicators
                success_indicators = ["success", "logged in", "dashboard", "welcome", "authenticated"]
                failure_indicators = ["error", "failed", "invalid", "incorrect", "denied"]
                
                has_success = any(indicator in observation for indicator in success_indicators)
                has_failure = any(indicator in observation for indicator in failure_indicators)
                
                if has_success and not has_failure:
                    return True
                else:
                    logger.warning(f"Login may have failed. Observation: {observation}")
                    return False
                    
        except Exception as e:
            logger.error(f"Stagehand login error: {e}")
            return False

    async def verify_authentication(
        self, 
        config: ProviderConfiguration,
        browser_session: Any
    ) -> bool:
        """Verify that authentication is still valid."""
        try:
            # Check if we can access authenticated areas
            chat_url = config.chat_url or config.base_url
            
            await self.element_detector._ensure_session()
            
            if not self.element_detector.api_key:
                return True  # Assume valid if we can't check
            
            payload = {
                "url": chat_url,
                "instruction": "Check if this page shows that the user is logged in. Look for user profile information, logout buttons, or authenticated content. Return true if authenticated, false if showing login page or errors.",
                "action": "observe",
                "modelName": "claude-3-5-sonnet-20241022"
            }
            
            async with self.element_detector.session.post(
                f"{self.element_detector.base_url}/v1/act", 
                json=payload
            ) as response:
                if response.status != 200:
                    return False
                
                data = await response.json()
                observation = data.get("observation", "").lower()
                
                # Check for authentication indicators
                auth_indicators = ["logged in", "authenticated", "profile", "logout", "dashboard"]
                unauth_indicators = ["login", "sign in", "authenticate", "unauthorized"]
                
                has_auth = any(indicator in observation for indicator in auth_indicators)
                has_unauth = any(indicator in observation for indicator in unauth_indicators)
                
                return has_auth and not has_unauth
                
        except Exception as e:
            logger.error(f"Authentication verification failed: {e}")
            return False

    async def refresh_session(
        self, 
        config: ProviderConfiguration,
        browser_session: Any
    ) -> bool:
        """Refresh authentication session if needed."""
        # For most web services, we'd need to re-authenticate
        return await self.authenticate(config, browser_session)


class StagehandChatProvider(ChatProvider):
    """
    AI-powered chat provider using Stagehand for chat interaction.
    """

    def __init__(self, element_detector: StagehandElementDetector):
        self.element_detector = element_detector

    async def send_message(
        self, 
        message: ChatMessage,
        browser_session: Any
    ) -> ChatResponse:
        """Send a message to the chat provider using AI automation."""
        provider_id = browser_session.get("provider_id", "unknown")
        
        try:
            # This would use the browser_session to get the current page URL
            # For now, we'll use a placeholder implementation
            
            await self.element_detector._ensure_session()
            
            if not self.element_detector.api_key:
                return ChatResponse(
                    content="",
                    provider_id=provider_id,
                    success=False,
                    error_message="Stagehand API key not configured"
                )
            
            # Create chat instruction for Stagehand
            instruction = f"""
            Send the following message in the chat interface: "{message.content}"
            
            Steps:
            1. Find the chat input field or text area
            2. Clear any existing text
            3. Type the message
            4. Click the send button or press Enter
            5. Wait for the response to appear
            6. Extract and return the AI's response text
            """
            
            # This would use the actual page URL from the browser session
            page_url = browser_session.get("current_url", "about:blank")
            
            payload = {
                "url": page_url,
                "instruction": instruction,
                "action": "act",
                "modelName": "claude-3-5-sonnet-20241022",
                "domSettleTimeoutMs": 10000  # Wait longer for AI response
            }
            
            start_time = time.time()
            
            async with self.element_detector.session.post(
                f"{self.element_detector.base_url}/v1/act", 
                json=payload
            ) as response:
                if response.status != 200:
                    return ChatResponse(
                        content="",
                        provider_id=provider_id,
                        success=False,
                        error_message=f"Stagehand API error: {response.status}"
                    )
                
                data = await response.json()
                observation = data.get("observation", "")
                
                # Extract response from observation
                response_content = self._extract_response_from_observation(observation)
                
                response_time = time.time() - start_time
                
                if response_content:
                    return ChatResponse(
                        content=response_content,
                        provider_id=provider_id,
                        success=True,
                        response_time=response_time
                    )
                else:
                    return ChatResponse(
                        content="",
                        provider_id=provider_id,
                        success=False,
                        error_message="Could not extract response from chat interface",
                        response_time=response_time
                    )
                    
        except Exception as e:
            return ChatResponse(
                content="",
                provider_id=provider_id,
                success=False,
                error_message=str(e)
            )

    def _extract_response_from_observation(self, observation: str) -> Optional[str]:
        """Extract chat response from Stagehand observation."""
        # This is a simplified implementation
        # In practice, you'd need more sophisticated parsing
        
        # Look for response patterns in the observation
        import re
        
        # Try to find response text patterns
        response_patterns = [
            r'response[:\s]+["\']([^"\']+)["\']',
            r'reply[:\s]+["\']([^"\']+)["\']',
            r'message[:\s]+["\']([^"\']+)["\']',
            r'AI[:\s]+["\']([^"\']+)["\']',
        ]
        
        for pattern in response_patterns:
            matches = re.findall(pattern, observation, re.IGNORECASE | re.DOTALL)
            if matches:
                return matches[0].strip()
        
        # If no structured response found, try to extract from the observation text
        lines = observation.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 20 and not line.startswith(('http', 'www', 'element', 'selector')):
                # This might be the response content
                return line
        
        return None

    async def get_response(
        self, 
        browser_session: Any,
        timeout: int = 30
    ) -> Optional[str]:
        """Get the response from the chat provider."""
        # This would typically wait for and extract the latest response
        # For Stagehand integration, this is handled in send_message
        return None

    async def is_ready(self, browser_session: Any) -> bool:
        """Check if the provider is ready to receive messages."""
        try:
            page_url = browser_session.get("current_url", "about:blank")
            
            # Use element detector to check if chat interface is ready
            chat_elements = await self.element_detector.detect_elements(
                page_url,
                [ElementType.CHAT_INPUT, ElementType.SEND_BUTTON]
            )
            
            # Ready if we can find both chat input and send button
            has_input = any(e.element_type == ElementType.CHAT_INPUT for e in chat_elements)
            has_send = any(e.element_type == ElementType.SEND_BUTTON for e in chat_elements)
            
            return has_input and has_send
            
        except Exception as e:
            logger.error(f"Ready check failed: {e}")
            return False
