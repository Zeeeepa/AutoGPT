"""
AI-Powered Provider Engine - Core implementation of the dynamic chat proxy system.

This module provides the main engine that orchestrates AI-powered element detection,
provider management, authentication, and chat functionality.
"""

import asyncio
import logging
import os
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from backend.core.provider_interfaces import (
    AIElementDetector, ProviderAuthenticator, ChatProvider, ProviderValidator,
    ProviderManager, ScalingEngine, ProviderEventHandler,
    ProviderConfiguration, ChatMessage, ChatResponse, ElementDetectionResult,
    ElementType, ProviderStatus, ProviderEvent, ProviderEventData,
    AIProviderEngineConfig
)


logger = logging.getLogger(__name__)


class AIProviderEngine:
    """
    Main engine for AI-powered dynamic chat proxy system.
    
    This engine coordinates all components to provide a seamless experience
    for adding and managing chat providers with minimal configuration.
    """

    def __init__(self, config: AIProviderEngineConfig):
        self.config = config
        self.providers: Dict[str, ProviderConfiguration] = {}
        self.provider_status: Dict[str, ProviderStatus] = {}
        self.active_sessions: Dict[str, Any] = {}
        self.event_handlers: List[ProviderEventHandler] = []
        
        # Component instances (will be injected)
        self.element_detector: Optional[AIElementDetector] = None
        self.authenticator: Optional[ProviderAuthenticator] = None
        self.chat_provider: Optional[ChatProvider] = None
        self.validator: Optional[ProviderValidator] = None
        self.scaling_engine: Optional[ScalingEngine] = None
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        
        # Ensure storage directories exist
        self._ensure_storage_directories()

    def _ensure_storage_directories(self):
        """Ensure storage directories exist."""
        Path(self.config.provider_storage_path).mkdir(parents=True, exist_ok=True)
        Path(self.config.session_storage_path).mkdir(parents=True, exist_ok=True)

    def set_element_detector(self, detector: AIElementDetector):
        """Set the AI element detector implementation."""
        self.element_detector = detector

    def set_authenticator(self, authenticator: ProviderAuthenticator):
        """Set the provider authenticator implementation."""
        self.authenticator = authenticator

    def set_chat_provider(self, chat_provider: ChatProvider):
        """Set the chat provider implementation."""
        self.chat_provider = chat_provider

    def set_validator(self, validator: ProviderValidator):
        """Set the provider validator implementation."""
        self.validator = validator

    def set_scaling_engine(self, scaling_engine: ScalingEngine):
        """Set the scaling engine implementation."""
        self.scaling_engine = scaling_engine

    def add_event_handler(self, handler: ProviderEventHandler):
        """Add an event handler for provider lifecycle events."""
        self.event_handlers.append(handler)

    async def start(self):
        """Start the AI provider engine."""
        logger.info("Starting AI Provider Engine")
        
        # Load existing providers
        await self._load_providers()
        
        # Start background tasks
        if self.config.enable_monitoring:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("AI Provider Engine started successfully")

    async def stop(self):
        """Stop the AI provider engine."""
        logger.info("Stopping AI Provider Engine")
        
        # Cancel background tasks
        for task in [self._monitoring_task, self._health_check_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Save provider configurations
        await self._save_providers()
        
        # Close active sessions
        for session_id, session in self.active_sessions.items():
            try:
                if hasattr(session, 'close'):
                    await session.close()
            except Exception as e:
                logger.warning(f"Error closing session {session_id}: {e}")
        
        logger.info("AI Provider Engine stopped")

    async def add_provider_simple(
        self, 
        domain: str, 
        username: str, 
        password: str,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Add a provider with simple domain/username/password configuration.
        
        This is the main entry point for the user's requirement to add providers
        with minimal configuration.
        
        Args:
            domain: Domain of the chat service (e.g., "chat.mistral.ai")
            username: Username/email for authentication
            password: Password for authentication
            **kwargs: Additional optional configuration
            
        Returns:
            Tuple of (provider_id, test_results)
        """
        logger.info(f"Adding provider for domain: {domain}")
        
        try:
            # Create provider configuration
            config = ProviderConfiguration(
                domain=domain,
                username=username,
                password=password,
                **kwargs
            )
            
            # Validate configuration
            if self.validator:
                is_valid, errors = await self.validator.validate_configuration(config)
                if not is_valid:
                    raise ValueError(f"Invalid configuration: {', '.join(errors)}")
            
            # Discover and test the provider
            discovery_results = await self._discover_provider(config)
            
            # Register the provider
            provider_id = await self._register_provider(config)
            
            # Test the provider end-to-end
            test_results = await self._test_provider_full(provider_id)
            
            # Emit registration event
            await self._emit_event(ProviderEvent.REGISTERED, provider_id, {
                "domain": domain,
                "discovery_results": discovery_results,
                "test_results": test_results
            })
            
            logger.info(f"Successfully added provider {provider_id} for domain {domain}")
            
            return provider_id, {
                "success": True,
                "provider_id": provider_id,
                "domain": domain,
                "discovery_results": discovery_results,
                "test_results": test_results,
                "status": "active" if test_results.get("success") else "error"
            }
            
        except Exception as e:
            logger.error(f"Failed to add provider for domain {domain}: {e}")
            await self._emit_event(ProviderEvent.ERROR, f"unknown_{domain}", {
                "error": str(e),
                "domain": domain
            })
            
            return "", {
                "success": False,
                "error": str(e),
                "domain": domain
            }

    async def _discover_provider(self, config: ProviderConfiguration) -> Dict[str, Any]:
        """
        Discover provider interface using AI-powered element detection.
        
        This method implements the core AI discovery functionality that makes
        the system adaptive to different chat interfaces.
        """
        logger.info(f"Discovering provider interface for {config.domain}")
        
        if not self.element_detector:
            raise RuntimeError("AI element detector not configured")
        
        discovery_results = {
            "login_elements": {},
            "chat_elements": {},
            "success": False,
            "errors": []
        }
        
        try:
            # Discover login elements
            login_url = config.login_url or config.base_url
            login_elements = await self.element_detector.detect_elements(
                login_url,
                [ElementType.LOGIN_EMAIL, ElementType.LOGIN_PASSWORD, ElementType.LOGIN_SUBMIT],
                context={"domain": config.domain, "purpose": "login"}
            )
            
            for element in login_elements:
                discovery_results["login_elements"][element.element_type.value] = {
                    "selector": element.selector,
                    "confidence": element.confidence,
                    "method": element.detection_method
                }
            
            # Try to discover chat elements (may require authentication first)
            chat_url = config.chat_url or config.base_url
            try:
                chat_elements = await self.element_detector.detect_elements(
                    chat_url,
                    [ElementType.CHAT_INPUT, ElementType.SEND_BUTTON, ElementType.RESPONSE_AREA],
                    context={"domain": config.domain, "purpose": "chat"}
                )
                
                for element in chat_elements:
                    discovery_results["chat_elements"][element.element_type.value] = {
                        "selector": element.selector,
                        "confidence": element.confidence,
                        "method": element.detection_method
                    }
            except Exception as e:
                discovery_results["errors"].append(f"Chat element discovery failed: {e}")
            
            # Update configuration with discovered elements
            if discovery_results["login_elements"] or discovery_results["chat_elements"]:
                discovery_results["success"] = True
                
                # Store discovered selectors in configuration
                if not config.custom_selectors:
                    config.custom_selectors = {}
                
                for element_type, data in discovery_results["login_elements"].items():
                    config.custom_selectors[ElementType(element_type)] = data["selector"]
                
                for element_type, data in discovery_results["chat_elements"].items():
                    config.custom_selectors[ElementType(element_type)] = data["selector"]
            
            logger.info(f"Discovery completed for {config.domain}: {discovery_results['success']}")
            
        except Exception as e:
            error_msg = f"Provider discovery failed: {e}"
            logger.error(error_msg)
            discovery_results["errors"].append(error_msg)
        
        return discovery_results

    async def _register_provider(self, config: ProviderConfiguration) -> str:
        """Register a provider configuration."""
        provider_id = config.provider_id
        self.providers[provider_id] = config
        self.provider_status[provider_id] = ProviderStatus.INITIALIZING
        
        # Save to persistent storage
        await self._save_provider_config(config)
        
        return provider_id

    async def _test_provider_full(self, provider_id: str) -> Dict[str, Any]:
        """Test provider functionality end-to-end."""
        if not self.validator:
            return {"success": False, "error": "Validator not configured"}
        
        try:
            config = self.providers[provider_id]
            test_results = await self.validator.test_provider(config)
            
            # Update provider status based on test results
            if test_results.get("success"):
                self.provider_status[provider_id] = ProviderStatus.ACTIVE
            else:
                self.provider_status[provider_id] = ProviderStatus.ERROR
            
            return test_results
            
        except Exception as e:
            self.provider_status[provider_id] = ProviderStatus.ERROR
            return {"success": False, "error": str(e)}

    async def send_message(
        self, 
        provider_id: str, 
        message: str,
        **kwargs
    ) -> ChatResponse:
        """
        Send a message to a provider.
        
        This is the main entry point for chat functionality.
        """
        if provider_id not in self.providers:
            return ChatResponse(
                content="",
                provider_id=provider_id,
                success=False,
                error_message=f"Provider {provider_id} not found"
            )
        
        if self.provider_status.get(provider_id) != ProviderStatus.ACTIVE:
            return ChatResponse(
                content="",
                provider_id=provider_id,
                success=False,
                error_message=f"Provider {provider_id} is not active"
            )
        
        chat_message = ChatMessage(content=message, **kwargs)
        
        try:
            # Use scaling engine if available, otherwise direct chat provider
            if self.scaling_engine:
                response = await self.scaling_engine.handle_request(provider_id, chat_message)
            elif self.chat_provider:
                # Get or create browser session for this provider
                session = await self._get_or_create_session(provider_id)
                response = await self.chat_provider.send_message(chat_message, session)
            else:
                raise RuntimeError("No chat provider or scaling engine configured")
            
            # Emit message event
            await self._emit_event(ProviderEvent.MESSAGE_SENT, provider_id, {
                "message": message,
                "response_length": len(response.content) if response.success else 0,
                "success": response.success
            })
            
            return response
            
        except Exception as e:
            error_response = ChatResponse(
                content="",
                provider_id=provider_id,
                success=False,
                error_message=str(e)
            )
            
            await self._emit_event(ProviderEvent.MESSAGE_FAILED, provider_id, {
                "message": message,
                "error": str(e)
            })
            
            return error_response

    async def _get_or_create_session(self, provider_id: str) -> Any:
        """Get or create a browser session for a provider."""
        if provider_id in self.active_sessions:
            return self.active_sessions[provider_id]
        
        # Create new session (implementation depends on browser automation library)
        # This is a placeholder - actual implementation would create browser session
        session = {"provider_id": provider_id, "created_at": datetime.now()}
        self.active_sessions[provider_id] = session
        
        return session

    async def list_providers(self) -> List[Dict[str, Any]]:
        """List all registered providers with their status."""
        providers = []
        
        for provider_id, config in self.providers.items():
            status = self.provider_status.get(provider_id, ProviderStatus.UNKNOWN)
            
            providers.append({
                "provider_id": provider_id,
                "domain": config.domain,
                "display_name": config.display_name,
                "status": status.value,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None,
                "tags": config.tags or []
            })
        
        return providers

    async def get_provider_info(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a provider."""
        if provider_id not in self.providers:
            return None
        
        config = self.providers[provider_id]
        status = self.provider_status.get(provider_id, ProviderStatus.UNKNOWN)
        
        return {
            "provider_id": provider_id,
            "domain": config.domain,
            "display_name": config.display_name,
            "base_url": config.base_url,
            "status": status.value,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
            "tags": config.tags or [],
            "has_custom_selectors": bool(config.custom_selectors),
            "ui_hints": config.ui_hints or {}
        }

    async def remove_provider(self, provider_id: str) -> bool:
        """Remove a provider."""
        if provider_id not in self.providers:
            return False
        
        try:
            # Close active session if exists
            if provider_id in self.active_sessions:
                session = self.active_sessions[provider_id]
                if hasattr(session, 'close'):
                    await session.close()
                del self.active_sessions[provider_id]
            
            # Remove from memory
            del self.providers[provider_id]
            if provider_id in self.provider_status:
                del self.provider_status[provider_id]
            
            # Remove from persistent storage
            await self._remove_provider_config(provider_id)
            
            # Emit removal event
            await self._emit_event(ProviderEvent.REMOVED, provider_id)
            
            logger.info(f"Removed provider {provider_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove provider {provider_id}: {e}")
            return False

    async def _emit_event(
        self, 
        event: ProviderEvent, 
        provider_id: str, 
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """Emit a provider event to all registered handlers."""
        event_data = ProviderEventData(
            event=event,
            provider_id=provider_id,
            timestamp=datetime.now(),
            data=data,
            error=error
        )
        
        for handler in self.event_handlers:
            try:
                await handler.handle_event(event_data)
            except Exception as e:
                logger.warning(f"Event handler failed: {e}")

    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                await asyncio.sleep(self.config.metrics_collection_interval)
                
                # Collect metrics for all providers
                for provider_id in self.providers:
                    # This would collect actual metrics in a real implementation
                    pass
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

    async def _health_check_loop(self):
        """Background health check loop."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                # Perform health checks on all active providers
                for provider_id, status in self.provider_status.items():
                    if status == ProviderStatus.ACTIVE and self.validator:
                        try:
                            health_result = await self.validator.health_check(provider_id)
                            if not health_result.get("healthy", False):
                                self.provider_status[provider_id] = ProviderStatus.ERROR
                                await self._emit_event(ProviderEvent.ERROR, provider_id, health_result)
                        except Exception as e:
                            logger.warning(f"Health check failed for {provider_id}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    async def _load_providers(self):
        """Load provider configurations from persistent storage."""
        try:
            provider_dir = Path(self.config.provider_storage_path)
            if not provider_dir.exists():
                return
            
            for config_file in provider_dir.glob("*.json"):
                try:
                    with open(config_file, 'r') as f:
                        config_data = json.load(f)
                    
                    config = ProviderConfiguration(**config_data)
                    self.providers[config.provider_id] = config
                    self.provider_status[config.provider_id] = ProviderStatus.INACTIVE
                    
                    logger.info(f"Loaded provider {config.provider_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to load provider config {config_file}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to load providers: {e}")

    async def _save_providers(self):
        """Save all provider configurations to persistent storage."""
        for provider_id, config in self.providers.items():
            await self._save_provider_config(config)

    async def _save_provider_config(self, config: ProviderConfiguration):
        """Save a single provider configuration."""
        try:
            config_file = Path(self.config.provider_storage_path) / f"{config.provider_id}.json"
            
            # Convert to dict for JSON serialization
            config_dict = {
                "domain": config.domain,
                "username": config.username,
                "password": config.password,  # In production, this should be encrypted
                "provider_id": config.provider_id,
                "display_name": config.display_name,
                "base_url": config.base_url,
                "login_url": config.login_url,
                "chat_url": config.chat_url,
                "ui_hints": config.ui_hints,
                "custom_selectors": {k.value: v for k, v in (config.custom_selectors or {}).items()},
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None,
                "tags": config.tags
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save provider config {config.provider_id}: {e}")

    async def _remove_provider_config(self, provider_id: str):
        """Remove a provider configuration file."""
        try:
            config_file = Path(self.config.provider_storage_path) / f"{provider_id}.json"
            if config_file.exists():
                config_file.unlink()
        except Exception as e:
            logger.error(f"Failed to remove provider config {provider_id}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "total_providers": len(self.providers),
            "active_providers": sum(1 for status in self.provider_status.values() 
                                  if status == ProviderStatus.ACTIVE),
            "active_sessions": len(self.active_sessions),
            "provider_status_breakdown": {
                status.value: sum(1 for s in self.provider_status.values() if s == status)
                for status in ProviderStatus
            }
        }
