"""API module for MultiCode - Multi-provider AI integration."""

from .models import ModelInfo, ModelManager
from .openrouter import ChatMessage, ChatResponse, OpenRouterClient
from .provider_manager import (
    ProviderManager,
    ProviderType,
    get_provider_manager,
    reset_provider_manager,
)
from .providers.base import (
    AuthenticationError,
    BaseProvider,
    ProviderCredential,
    ProviderError,
    ProviderInfo,
    RateLimitError,
    TimeoutError,
)
from .providers.base import (
    ChatMessage as ProviderChatMessage,
)
from .providers.base import (
    ChatResponse as ProviderChatResponse,
)
from .providers.base import (
    ModelInfo as ProviderModelInfo,
)

__all__ = [
    # Legacy exports
    "OpenRouterClient",
    "ChatMessage",
    "ChatResponse",
    "ModelInfo",
    "ModelManager",
    # Provider manager
    "ProviderManager",
    "ProviderType",
    "get_provider_manager",
    "reset_provider_manager",
    # Base classes
    "BaseProvider",
    "ProviderChatMessage",
    "ProviderChatResponse",
    "ProviderModelInfo",
    "ProviderInfo",
    "ProviderCredential",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
]