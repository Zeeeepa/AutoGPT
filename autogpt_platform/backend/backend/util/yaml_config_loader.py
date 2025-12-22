"""
YAML Configuration Loader for Dynamic Provider Management.

This module provides functionality to load provider configurations from YAML files
with URL + username + password entries, supporting hot-reloading and validation.
"""

import asyncio
import logging
import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pydantic import BaseModel, Field, validator
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)


class ProviderConfig(BaseModel):
    """Configuration for a single provider from YAML."""
    name: str = Field(..., description="Display name of the provider")
    url: str = Field(..., description="Base URL of the chat service")
    username: str = Field(..., description="Username or email for authentication")
    password: str = Field(..., description="Password for authentication")
    
    # Optional fields
    models: Optional[List[str]] = Field(default=None, description="Supported model names")
    tags: Optional[List[str]] = Field(default=None, description="Tags for organization")
    enabled: bool = Field(default=True, description="Whether provider is enabled")
    is_default: bool = Field(default=False, description="Whether this is the default provider")
    
    # UI hints for better element detection
    login_url: Optional[str] = Field(default=None, description="Specific login URL if different from base")
    chat_url: Optional[str] = Field(default=None, description="Specific chat URL if different from base")
    ui_hints: Optional[Dict[str, Any]] = Field(default=None, description="UI detection hints")
    
    # Metadata
    description: Optional[str] = Field(default=None, description="Provider description")
    priority: int = Field(default=1, description="Priority for load balancing (higher = preferred)")
    timeout_seconds: int = Field(default=120, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    @validator('url')
    def validate_url(cls, v):
        """Ensure URL has proper format."""
        if not v.startswith(('http://', 'https://')):
            v = f'https://{v}'
        return v.rstrip('/')

    @validator('models', pre=True)
    def validate_models(cls, v):
        """Ensure models is a list."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    @validator('tags', pre=True)
    def validate_tags(cls, v):
        """Ensure tags is a list."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v


class YAMLConfig(BaseModel):
    """Root configuration structure."""
    providers: List[ProviderConfig] = Field(..., description="List of provider configurations")
    default_provider: Optional[str] = Field(default=None, description="Name of default provider")
    
    # Global settings
    settings: Optional[Dict[str, Any]] = Field(default=None, description="Global settings")
    encryption_enabled: bool = Field(default=True, description="Whether to encrypt stored credentials")
    auto_reload: bool = Field(default=True, description="Whether to auto-reload on file changes")


class YAMLConfigWatcher(FileSystemEventHandler):
    """File system watcher for YAML configuration changes."""
    
    def __init__(self, config_loader: 'YAMLConfigLoader'):
        self.config_loader = config_loader
        self.last_modified = {}
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
            
        file_path = event.src_path
        if not file_path.endswith(('.yaml', '.yml')):
            return
            
        # Debounce rapid file changes
        current_time = datetime.now().timestamp()
        last_time = self.last_modified.get(file_path, 0)
        
        if current_time - last_time < 1.0:  # 1 second debounce
            return
            
        self.last_modified[file_path] = current_time
        
        logger.info(f"YAML configuration file changed: {file_path}")
        asyncio.create_task(self.config_loader.reload_config())


class CredentialEncryption:
    """Handles encryption/decryption of sensitive credentials."""
    
    def __init__(self, key_file: str = "config/encryption.key"):
        self.key_file = Path(key_file)
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        self._key = self._load_or_create_key()
        self._cipher = Fernet(self._key)
    
    def _load_or_create_key(self) -> bytes:
        """Load existing key or create a new one."""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            logger.info(f"Created new encryption key: {self.key_file}")
            return key
    
    def encrypt(self, data: str) -> str:
        """Encrypt a string."""
        encrypted = self._cipher.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt a string."""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            raise ValueError("Invalid encrypted data")


class YAMLConfigLoader:
    """
    Main YAML configuration loader with hot-reloading and encryption support.
    """
    
    def __init__(self, 
                 config_path: str = "providers.yaml",
                 enable_encryption: bool = True,
                 enable_hot_reload: bool = True):
        self.config_path = Path(config_path)
        self.enable_encryption = enable_encryption
        self.enable_hot_reload = enable_hot_reload
        
        # Initialize encryption if enabled
        self.encryption = CredentialEncryption() if enable_encryption else None
        
        # Configuration state
        self.config: Optional[YAMLConfig] = None
        self.providers: Dict[str, ProviderConfig] = {}
        self.default_provider: Optional[str] = None
        
        # File watching
        self.observer: Optional[Observer] = None
        self.watcher: Optional[YAMLConfigWatcher] = None
        
        # Change callbacks
        self.change_callbacks: List[Callable[[Dict[str, ProviderConfig]], None]] = []
        
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
    
    def add_change_callback(self, callback: Callable[[Dict[str, ProviderConfig]], None]):
        """Add a callback to be called when configuration changes."""
        self.change_callbacks.append(callback)
    
    async def start(self):
        """Start the configuration loader."""
        logger.info(f"Starting YAML configuration loader: {self.config_path}")
        
        # Create default config if it doesn't exist
        if not self.config_path.exists():
            await self._create_default_config()
        
        # Load initial configuration
        await self.load_config()
        
        # Start file watching if enabled
        if self.enable_hot_reload:
            await self._start_file_watching()
        
        logger.info("YAML configuration loader started successfully")
    
    async def stop(self):
        """Stop the configuration loader."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        logger.info("YAML configuration loader stopped")
    
    async def load_config(self) -> Dict[str, ProviderConfig]:
        """Load configuration from YAML file."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Configuration file not found: {self.config_path}")
                return {}
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f)
            
            if not raw_data:
                logger.warning("Empty configuration file")
                return {}
            
            # Parse and validate configuration
            self.config = YAMLConfig(**raw_data)
            
            # Process providers
            new_providers = {}
            for provider_config in self.config.providers:
                if not provider_config.enabled:
                    continue
                
                # Decrypt credentials if encryption is enabled
                if self.encryption:
                    try:
                        # Check if password is encrypted (starts with 'enc:')
                        if provider_config.password.startswith('enc:'):
                            provider_config.password = self.encryption.decrypt(
                                provider_config.password[4:]  # Remove 'enc:' prefix
                            )
                    except Exception as e:
                        logger.error(f"Failed to decrypt password for {provider_config.name}: {e}")
                        continue
                
                # Generate provider ID
                provider_id = self._generate_provider_id(provider_config.name)
                new_providers[provider_id] = provider_config
                
                # Set default models if not specified
                if not provider_config.models:
                    provider_config.models = [provider_config.name.lower().replace(' ', '.')]
            
            # Update provider registry
            old_providers = self.providers.copy()
            self.providers = new_providers
            
            # Set default provider
            if self.config.default_provider:
                self.default_provider = self._find_provider_id_by_name(self.config.default_provider)
            elif not self.default_provider and self.providers:
                # Set first provider as default if none specified
                self.default_provider = list(self.providers.keys())[0]
            
            # Notify callbacks of changes
            if old_providers != new_providers:
                for callback in self.change_callbacks:
                    try:
                        callback(self.providers)
                    except Exception as e:
                        logger.error(f"Error in configuration change callback: {e}")
            
            logger.info(f"Loaded {len(self.providers)} providers from configuration")
            return self.providers
            
        except Exception as e:
            logger.error(f"Failed to load YAML configuration: {e}")
            return {}
    
    async def reload_config(self):
        """Reload configuration from file."""
        logger.info("Reloading YAML configuration...")
        await self.load_config()
    
    async def save_config(self):
        """Save current configuration to file."""
        if not self.config:
            return
        
        try:
            # Encrypt passwords if encryption is enabled
            config_data = self.config.dict()
            
            if self.encryption:
                for provider in config_data['providers']:
                    if not provider['password'].startswith('enc:'):
                        encrypted_password = self.encryption.encrypt(provider['password'])
                        provider['password'] = f'enc:{encrypted_password}'
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Configuration saved to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
    
    async def add_provider(self, provider_config: ProviderConfig) -> str:
        """Add a new provider to the configuration."""
        if not self.config:
            self.config = YAMLConfig(providers=[])
        
        # Check for duplicate names
        existing_names = [p.name for p in self.config.providers]
        if provider_config.name in existing_names:
            raise ValueError(f"Provider with name '{provider_config.name}' already exists")
        
        # Add to configuration
        self.config.providers.append(provider_config)
        
        # Save configuration
        await self.save_config()
        
        # Reload to update internal state
        await self.load_config()
        
        provider_id = self._generate_provider_id(provider_config.name)
        logger.info(f"Added provider '{provider_config.name}' with ID '{provider_id}'")
        
        return provider_id
    
    async def remove_provider(self, provider_name: str) -> bool:
        """Remove a provider from the configuration."""
        if not self.config:
            return False
        
        # Find and remove provider
        original_count = len(self.config.providers)
        self.config.providers = [p for p in self.config.providers if p.name != provider_name]
        
        if len(self.config.providers) == original_count:
            return False  # Provider not found
        
        # Save configuration
        await self.save_config()
        
        # Reload to update internal state
        await self.load_config()
        
        logger.info(f"Removed provider '{provider_name}'")
        return True
    
    def get_provider_by_model(self, model: str) -> Optional[ProviderConfig]:
        """Get provider that supports the specified model."""
        for provider in self.providers.values():
            if model.lower() in [m.lower() for m in provider.models]:
                return provider
        return None
    
    def get_provider_by_name(self, name: str) -> Optional[ProviderConfig]:
        """Get provider by name."""
        provider_id = self._find_provider_id_by_name(name)
        return self.providers.get(provider_id) if provider_id else None
    
    def get_default_provider(self) -> Optional[ProviderConfig]:
        """Get the default provider."""
        if self.default_provider and self.default_provider in self.providers:
            return self.providers[self.default_provider]
        elif self.providers:
            return list(self.providers.values())[0]
        return None
    
    def list_providers(self) -> List[Dict[str, Any]]:
        """List all providers with their information."""
        return [
            {
                "provider_id": provider_id,
                "name": provider.name,
                "url": provider.url,
                "models": provider.models,
                "enabled": provider.enabled,
                "is_default": provider_id == self.default_provider,
                "tags": provider.tags,
                "description": provider.description,
                "priority": provider.priority
            }
            for provider_id, provider in self.providers.items()
        ]
    
    def _generate_provider_id(self, name: str) -> str:
        """Generate a unique provider ID from name."""
        return name.lower().replace(' ', '_').replace('.', '_').replace('-', '_')
    
    def _find_provider_id_by_name(self, name: str) -> Optional[str]:
        """Find provider ID by name."""
        for provider_id, provider in self.providers.items():
            if provider.name.lower() == name.lower():
                return provider_id
        return None
    
    async def _create_default_config(self):
        """Create a default configuration file."""
        default_config = {
            "providers": [
                {
                    "name": "Z.AI",
                    "url": "https://chat.z.ai",
                    "username": "your-email@example.com",
                    "password": "your-password",
                    "models": ["z.ai", "gpt-3.5-turbo", "gpt-4"],
                    "is_default": True,
                    "description": "Z.AI chat service",
                    "tags": ["ai", "chat"]
                }
            ],
            "default_provider": "Z.AI",
            "settings": {
                "encryption_enabled": True,
                "auto_reload": True,
                "request_timeout": 120,
                "max_retries": 3
            }
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"Created default configuration file: {self.config_path}")
    
    async def _start_file_watching(self):
        """Start watching the configuration file for changes."""
        if not self.enable_hot_reload:
            return
        
        try:
            self.watcher = YAMLConfigWatcher(self)
            self.observer = Observer()
            self.observer.schedule(
                self.watcher,
                str(self.config_path.parent),
                recursive=False
            )
            self.observer.start()
            logger.info(f"Started watching configuration file: {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to start file watching: {e}")


# Global instance
yaml_config_loader: Optional[YAMLConfigLoader] = None


async def get_yaml_config_loader() -> YAMLConfigLoader:
    """Get or create the global YAML configuration loader."""
    global yaml_config_loader
    
    if yaml_config_loader is None:
        config_path = os.getenv("PROVIDERS_CONFIG_PATH", "providers.yaml")
        yaml_config_loader = YAMLConfigLoader(config_path)
        await yaml_config_loader.start()
    
    return yaml_config_loader


async def initialize_yaml_config() -> YAMLConfigLoader:
    """Initialize the YAML configuration system."""
    return await get_yaml_config_loader()


async def shutdown_yaml_config():
    """Shutdown the YAML configuration system."""
    global yaml_config_loader
    if yaml_config_loader:
        await yaml_config_loader.stop()
        yaml_config_loader = None
