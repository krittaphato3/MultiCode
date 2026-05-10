"""
Provider base classes and interfaces for multi-provider support.

This module defines the abstract base class that all API providers must implement,
enabling seamless switching between different AI services.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported API providers."""
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    NVIDIA = "nvidia"
    OLLAMA = "ollama"
    GROQ = "groq"
    MISTRAL = "mistral"
    GOOGLE = "google"


@dataclass
class ProviderInfo:
    """Information about a provider."""
    id: ProviderType
    name: str
    description: str
    requires_api_key: bool = True
    supports_streaming: bool = True
    supports_functions: bool = True
    base_url: str | None = None
    default_model: str | None = None
    website_url: str | None = None


@dataclass
class ProviderCredential:
    """Credentials for a provider."""
    provider_id: ProviderType
    api_key: str | None = None
    base_url: str | None = None
    is_configured: bool = False
    is_validated: bool = False
    last_validated: str | None = None


@dataclass
class ChatMessage:
    """A single chat message in the conversation."""
    role: str  # "system", "user", or "assistant"
    content: str
    name: str | None = None  # For agent identification


@dataclass
class ChatResponse:
    """Response from an API provider."""
    content: str
    model: str
    finish_reason: str
    usage: dict = field(default_factory=dict)
    provider: ProviderType | None = None


@dataclass
class ModelInfo:
    """Information about an available model."""
    id: str
    name: str
    provider: ProviderType
    description: str | None = None
    context_length: int | None = None
    pricing_prompt: float | None = None
    pricing_completion: float | None = None
    is_free: bool = False
    is_available: bool = True

    def display_name(self) -> str:
        """Get a formatted display name."""
        base = f"{self.name} ({self.provider.value})"
        if self.context_length:
            base += f" - {self.context_length:,} ctx"
        if self.is_free:
            base += " [FREE]"
        return base


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class AuthenticationError(ProviderError):
    """Raised when API key is invalid."""
    pass


class RateLimitError(ProviderError):
    """Raised when rate limit is hit."""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class TimeoutError(ProviderError):
    """Raised when request times out."""
    pass


class ValidationError(ProviderError):
    """Raised when validation fails."""
    pass


class BaseProvider(ABC):
    """
    Abstract base class for all API providers.

    All providers must implement these methods to ensure
    consistent behavior across different AI services.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self._configured = api_key is not None

    @property
    @abstractmethod
    def provider_info(self) -> ProviderInfo:
        """Return information about this provider."""
        pass

    @property
    def is_configured(self) -> bool:
        """Check if the provider is configured with valid credentials."""
        return self._configured and self.api_key is not None

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """
        Validate the API key by making a test request.

        Returns:
            True if credentials are valid, False otherwise
        """
        pass

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> ChatResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of chat messages
            model: Model ID to use
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response

        Returns:
            ChatResponse with the model's response
        """
        pass

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """
        List available models for this provider.

        Returns:
            List of ModelInfo objects
        """
        pass

    @abstractmethod
    async def get_model_info(self, model_id: str) -> ModelInfo | None:
        """
        Get information about a specific model.

        Args:
            model_id: The model ID to look up

        Returns:
            ModelInfo or None if not found
        """
        pass

    def get_default_model(self) -> str | None:
        """Get the default model for this provider."""
        return self.provider_info.default_model

    def get_supported_models(self) -> list[str]:
        """Get list of supported model IDs for this provider."""
        return []

    def format_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """
        Format messages for this provider's API.

        Override this if the provider has specific requirements.
        """
        formatted = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.name:
                msg_dict["name"] = msg.name
            formatted.append(msg_dict)
        return formatted

    def parse_response(self, response_data: dict, model: str | None = None) -> ChatResponse:
        """
        Parse the API response into a ChatResponse.

        Override this for provider-specific parsing.
        """
        raise NotImplementedError("Subclasses must implement parse_response")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(configured={self.is_configured})"


# Registry of available providers
_PROVIDER_REGISTRY: dict[ProviderType, type[BaseProvider]] = {}


def register_provider(provider_class: type[BaseProvider]) -> None:
    """Register a provider class in the registry."""
    instance = provider_class()
    _PROVIDER_REGISTRY[instance.provider_info.id] = provider_class


def get_provider_class(provider_type: ProviderType) -> type[BaseProvider] | None:
    """Get a provider class by type."""
    return _PROVIDER_REGISTRY.get(provider_type)


def get_registered_providers() -> list[ProviderType]:
    """Get list of all registered provider types."""
    return list(_PROVIDER_REGISTRY.keys())


__all__ = [
    "ProviderType",
    "ProviderInfo",
    "ProviderCredential",
    "ChatMessage",
    "ChatResponse",
    "ModelInfo",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
    "ValidationError",
    "BaseProvider",
    "register_provider",
    "get_provider_class",
    "get_registered_providers",
]