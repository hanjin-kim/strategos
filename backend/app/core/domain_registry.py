from __future__ import annotations
from typing import Any
import logging

logger = logging.getLogger(__name__)

_registry: dict[str, Any] = {}


def register(domain_name: str, factory: Any) -> None:
    """Register a domain factory."""
    _registry[domain_name] = factory
    logger.info("Registered domain: %s", domain_name)


def get(domain_name: str) -> Any:
    """Get a domain factory by name."""
    if domain_name not in _registry:
        raise KeyError(f"Domain '{domain_name}' not registered. Available: {list(_registry.keys())}")
    return _registry[domain_name]


def list_domains() -> list[str]:
    """List all registered domain names."""
    return list(_registry.keys())


def clear() -> None:
    """Clear all registered domains (for testing)."""
    _registry.clear()
