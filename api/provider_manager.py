"""
Provider manager for handling multiple API providers.

This module provides a unified interface for managing multiple API providers,
switching between them, and handling credentials securely.
"""

from __future__ import annotations

import logging
from typing import Any

from .providers.anthropic import AnthropicProvider
from .providers.base import (
    BaseProvider,
    ChatMessage,
    ChatResponse,
    ProviderType,
    get_provider_class,
)
from .providers.nvidia import NVIDIAProvider

# Import built-in providers
from .providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


class ProviderManager:
    """
    Manages multiple API providers with unified interface.

    Handles provider switching, credentials, and routing requests
    to the active provider.
    """

    def __init__(self):
        self._providers: dict[ProviderType, BaseProvider] = {}
        self._active_provider: ProviderType = ProviderType.OPENROUTER
        self._credentials: dict[ProviderType, str | None] = {}

    def _register_provider_instance(self, provider_type: ProviderType, provider: BaseProvider) -> None:
        """Register a provider instance."""
        self._providers[provider_type] = provider
        if provider.api_key:
            self._credentials[provider_type] = provider.api_key

    def get_provider(self, provider_type: ProviderType) -> BaseProvider | None:
        """Get a provider instance by type."""
        return self._providers.get(provider_type)

    def get_active_provider(self) -> BaseProvider | None:
        """Get the currently active provider."""
        return self._providers.get(self._active_provider)

    def set_active_provider(self, provider_type: ProviderType) -> bool:
        """Set the active provider."""
        if provider_type in self._providers:
            self._active_provider = provider_type
            return True
        return False

    @property
    def active_provider_type(self) -> ProviderType:
        """Get the active provider type."""
        return self._active_provider

    def configure_provider(
        self,
        provider_type: ProviderType,
        api_key: str,
        base_url: str | None = None,
    ) -> BaseProvider | None:
        """Configure a provider with credentials."""
        provider_class = get_provider_class(provider_type)

        if not provider_class:
            logger.error(f"Unknown provider type: {provider_type}")
            return None

        try:
            provider = provider_class(api_key=api_key, base_url=base_url)
            self._providers[provider_type] = provider
            self._credentials[provider_type] = api_key

            if self._active_provider not in self._providers:
                self._active_provider = provider_type

            return provider
        except Exception as e:
            logger.error(f"Failed to configure provider {provider_type}: {e}")
            return None

    async def validate_provider(self, provider_type: ProviderType) -> bool:
        """Validate credentials for a provider."""
        provider = self.get_provider(provider_type)
        if not provider:
            return False

        try:
            is_valid = await provider.validate_credentials()
            return is_valid
        except Exception as e:
            logger.error(f"Provider {provider_type} validation failed: {e}")
            return False

    def get_configured_providers(self) -> list[ProviderType]:
        """Get list of configured provider types."""
        return [pt for pt in self._providers if self._providers[pt].is_configured]

    def get_all_providers(self) -> list[ProviderType]:
        """Get list of all registered provider types."""
        return list(self._providers.keys())

    def remove_provider(self, provider_type: ProviderType) -> None:
        """Remove a provider configuration."""
        if provider_type in self._providers:
            del self._providers[provider_type]
        if provider_type in self._credentials:
            del self._credentials[provider_type]

        if self._active_provider == provider_type:
            configured = self.get_configured_providers()
            self._active_provider = configured[0] if configured else ProviderType.OPENROUTER

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        provider_type: ProviderType | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """
        Send a chat completion request to the active or specified provider.

        Args:
            messages: List of chat messages
            model: Model ID (uses provider default if not specified)
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream response
            provider_type: Optional specific provider to use

        Returns:
            ChatResponse from the provider
        """
        if provider_type:
            provider = self.get_provider(provider_type)
        else:
            provider = self.get_active_provider()

        if not provider:
            raise Exception(f"No provider available. Active: {self._active_provider}")

        if not provider.is_configured:
            raise Exception(f"Provider {provider.provider_info.name} not configured")

        target_model = model or provider.get_default_model()
        if not target_model:
            raise Exception(f"No model specified and no default for {provider.provider_info.name}")

        return await provider.chat_completion(
            messages=messages,
            model=target_model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            **kwargs,
        )

    def has_credentials(self, provider_type: ProviderType) -> bool:
        """Check if credentials exist for a provider."""
        api_key = self._credentials.get(provider_type)
        return api_key is not None and api_key != ""

    def get_provider_status(self) -> dict[ProviderType, dict]:
        """Get status information for all providers."""
        status = {}
        for provider_type, provider in self._providers.items():
            status[provider_type] = {
                "configured": provider.is_configured,
                "name": provider.provider_info.name,
                "default_model": provider.get_default_model(),
            }
        return status

    def get_active_model(self) -> str | None:
        """Get the default model for the active provider."""
        provider = self.get_active_provider()
        return provider.get_default_model() if provider else None

    def get_model_for_provider(self, provider_type: ProviderType) -> str | None:
        """Get the default model for a specific provider."""
        provider = self.get_provider(provider_type)
        return provider.get_default_model() if provider else None


# Global provider manager instance
_provider_manager: ProviderManager | None = None


def get_provider_manager() -> ProviderManager:
    """Get the global provider manager instance."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = ProviderManager()
        # Register built-in providers
        _provider_manager._register_provider_instance(ProviderType.OPENAI, OpenAIProvider())
        _provider_manager._register_provider_instance(ProviderType.ANTHROPIC, AnthropicProvider())
        _provider_manager._register_provider_instance(ProviderType.NVIDIA, NVIDIAProvider())
    return _provider_manager


def reset_provider_manager() -> None:
    """Reset the global provider manager (for testing)."""
    global _provider_manager
    _provider_manager = None


__all__ = [
    "ProviderManager",
    "ProviderType",
    "get_provider_manager",
    "reset_provider_manager",
]