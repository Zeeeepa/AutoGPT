"""
FastAPI dependency injection for chat proxy services.
"""

import logging
from typing import Optional
from fastapi import Depends, HTTPException

from backend.util.smart_scaling_engine import SmartScalingEngine
from backend.util.dynamic_provider_manager import DynamicProviderManager

logger = logging.getLogger(__name__)

# Global instances (initialized at startup)
_scaling_engine: Optional[SmartScalingEngine] = None
_provider_manager: Optional[DynamicProviderManager] = None


def set_scaling_engine(engine: SmartScalingEngine):
    """Set the global scaling engine instance."""
    global _scaling_engine
    _scaling_engine = engine


def set_provider_manager(manager: DynamicProviderManager):
    """Set the global provider manager instance."""
    global _provider_manager
    _provider_manager = manager


def get_scaling_engine() -> SmartScalingEngine:
    """Dependency to get the scaling engine."""
    if _scaling_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Scaling engine not initialized"
        )
    return _scaling_engine


def get_provider_manager() -> DynamicProviderManager:
    """Dependency to get the provider manager."""
    if _provider_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Provider manager not initialized"
        )
    return _provider_manager


# Dependency aliases for easier use
ScalingEngineDep = Depends(get_scaling_engine)
ProviderManagerDep = Depends(get_provider_manager)
