"""
Anthropic provider implementation for MultiCode.

Provides access to Claude models via Anthropic's API.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from .base import (
    AuthenticationError,
    BaseProvider,
    ChatMessage,
    ChatResponse,
    ModelInfo,
    ProviderInfo,
    ProviderType,
    RateLimitError,
    TimeoutError,
    register_provider,
)

logger = logging.getLogger(__name__)

ANTHROPIC_API_BASE = "https://api.anthropic.com/v1"
ANTHROPIC_DEFAULT_MODEL = "claude-3-5-sonnet-20241022"


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic's API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        super().__init__(api_key, base_url or ANTHROPIC_API_BASE)

    @property
    def provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=ProviderType.ANTHROPIC,
            name="Anthropic",
            description="Access Claude 3.5, Claude 3, and Claude 2 models",
            requires_api_key=True,
            supports_streaming=True,
            supports_functions=True,
            base_url=ANTHROPIC_API_BASE,
            default_model=ANTHROPIC_DEFAULT_MODEL,
            website_url="https://anthropic.com",
        )

    async def validate_credentials(self) -> bool:
        """Validate the Anthropic API key."""
        if not self.api_key:
            return False

        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-3-5-haiku-20241022",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "test"}],
                },
                timeout=30,
            )

            if response.status_code == 200:
                self._configured = True
                return True
            elif response.status_code == 401:
                raise AuthenticationError("Invalid Anthropic API key")
            elif response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            else:
                return False
        except requests.exceptions.Timeout:
            raise TimeoutError("Request timed out") from None
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Anthropic validation error: {e}")
            return False

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
        """Send a chat completion request to Anthropic."""
        if not self.api_key:
            raise AuthenticationError("No API key configured")

        api_messages = []
        if system_prompt:
            api_messages.append({"role": "user", "content": f"\n\nAssistant: "})

        for msg in messages:
            role = msg.role if msg.role in ("user", "assistant") else "user"
            api_messages.append({
                "role": role,
                "content": msg.content,
            })

        payload: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if max_tokens is None:
            max_tokens = 4096
        payload["max_tokens"] = max_tokens

        if stream:
            payload["stream"] = True

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
                timeout=120,
            )

            if response.status_code == 401:
                raise AuthenticationError("Invalid Anthropic API key")
            elif response.status_code == 429:
                retry_after = int(response.headers.get("retry-after", 60))
                raise RateLimitError(f"Rate limit exceeded", retry_after)
            elif response.status_code >= 400:
                raise Exception(f"Anthropic API error: {response.status_code}")

            data = response.json()
            return self.parse_response(data, model)

        except requests.exceptions.Timeout:
            raise TimeoutError("Request timed out") from None
        except Exception as e:
            if isinstance(e, (AuthenticationError, RateLimitError, TimeoutError)):
                raise
            logger.error(f"Anthropic API error: {e}")
            raise

    def parse_response(self, data: dict, model: str | None = None) -> ChatResponse:
        """Parse Anthropic API response."""
        content = data.get("content", [])
        if isinstance(content, list) and content:
            text = content[0].get("text", "")
        else:
            text = str(content)

        usage = data.get("usage", {})

        return ChatResponse(
            content=text,
            model=data.get("model", model) or "",
            finish_reason=data.get("stop_reason", "stop"),
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
            provider=ProviderType.ANTHROPIC,
        )

    async def list_models(self) -> list[ModelInfo]:
        """List available Anthropic models."""
        return [
            ModelInfo(
                id="claude-3-5-sonnet-20241022",
                name="Claude 3.5 Sonnet",
                provider=ProviderType.ANTHROPIC,
                context_length=200000,
                description="Most intelligent model, excellent for coding",
            ),
            ModelInfo(
                id="claude-3-opus-20240229",
                name="Claude 3 Opus",
                provider=ProviderType.ANTHROPIC,
                context_length=200000,
                description="Most powerful model for complex tasks",
            ),
            ModelInfo(
                id="claude-3-haiku-20240307",
                name="Claude 3 Haiku",
                provider=ProviderType.ANTHROPIC,
                context_length=200000,
                description="Fastest and most affordable",
            ),
            ModelInfo(
                id="claude-2.1",
                name="Claude 2.1",
                provider=ProviderType.ANTHROPIC,
                context_length=200000,
                description="Previous generation model",
            ),
        ]

    async def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get information about a specific Anthropic model."""
        models = await self.list_models()
        for model in models:
            if model.id == model_id:
                return model
        return None

    def get_supported_models(self) -> list[str]:
        """Get list of supported Anthropic models."""
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
        ]


# Register the provider
register_provider(AnthropicProvider)