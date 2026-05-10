"""
NVIDIA NIM provider implementation for MultiCode.

Provides access to NVIDIA NIM endpoints including NIM for Llama, Mistral, and other models.
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

NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"
NVIDIA_DEFAULT_MODEL = "nvidia/llama-3.1-nemotron-70b-instruct"


class NVIDIAProvider(BaseProvider):
    """Provider for NVIDIA NIM API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        super().__init__(api_key, base_url or NVIDIA_API_BASE)

    @property
    def provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=ProviderType.NVIDIA,
            name="NVIDIA NIM",
            description="Access NVIDIA NIM endpoints including Llama, Mistral, and Nemotron models",
            requires_api_key=True,
            supports_streaming=True,
            supports_functions=True,
            base_url=NVIDIA_API_BASE,
            default_model=NVIDIA_DEFAULT_MODEL,
            website_url="https://developer.nvidia.com/nim",
        )

    async def validate_credentials(self) -> bool:
        """Validate the NVIDIA API key."""
        if not self.api_key:
            return False

        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
                timeout=30,
            )

            if response.status_code == 200:
                self._configured = True
                return True
            elif response.status_code == 401:
                raise AuthenticationError("Invalid NVIDIA API key")
            elif response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            else:
                return False
        except requests.exceptions.Timeout:
            raise TimeoutError("Request timed out") from None
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"NVIDIA validation error: {e}")
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
        """Send a chat completion request to NVIDIA NIM."""
        if not self.api_key:
            raise AuthenticationError("No API key configured")

        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        api_messages.extend(self.format_messages(messages))

        payload: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if stream:
            payload["stream"] = True

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=180,
            )

            if response.status_code == 401:
                raise AuthenticationError("Invalid NVIDIA API key")
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(f"Rate limit exceeded", retry_after)
            elif response.status_code >= 400:
                raise Exception(f"NVIDIA API error: {response.status_code}")

            data = response.json()
            return self.parse_response(data, model)

        except requests.exceptions.Timeout:
            raise TimeoutError("Request timed out") from None
        except Exception as e:
            if isinstance(e, (AuthenticationError, RateLimitError, TimeoutError)):
                raise
            logger.error(f"NVIDIA API error: {e}")
            raise

    def parse_response(self, data: dict, model: str | None = None) -> ChatResponse:
        """Parse NVIDIA NIM API response."""
        choices = data.get("choices", [])
        if not choices:
            raise Exception("No choices in response")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        return ChatResponse(
            content=content or "",
            model=data.get("model", model) or "",
            finish_reason=choice.get("finish_reason", "stop"),
            usage=data.get("usage", {}),
            provider=ProviderType.NVIDIA,
        )

    async def list_models(self) -> list[ModelInfo]:
        """List available NVIDIA NIM models."""
        if not self.api_key:
            return []

        popular_nim_models = [
            ("nvidia/llama-3.1-nemotron-70b-instruct", "Nemotron 70B", 128000),
            ("nvidia/llama-3.1-nemotron-8b-instruct", "Nemotron 8B", 128000),
            ("meta/llama-3.1-70b-instruct", "Llama 3.1 70B", 128000),
            ("meta/llama-3.1-8b-instruct", "Llama 3.1 8B", 128000),
            ("mistralai/mistral-large-2", "Mistral Large 2", 128000),
            ("mistralai/mixtral-8x7b-instruct-v0.1", "Mixtral 8x7B", 32000),
            ("google/gemma-2-27b-it", "Gemma 2 27B", 8192),
            ("deepseek-ai/deepseek-coder-33b-instruct", "DeepSeek Coder 33B", 64000),
        ]

        models = []
        for model_id, name, ctx in popular_nim_models:
            models.append(ModelInfo(
                id=model_id,
                name=name,
                provider=ProviderType.NVIDIA,
                context_length=ctx,
                description=f"{name} via NVIDIA NIM",
            ))

        return models

    async def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get information about a specific NVIDIA NIM model."""
        models = await self.list_models()
        for model in models:
            if model.id == model_id:
                return model
        return None

    def get_supported_models(self) -> list[str]:
        """Get list of supported NVIDIA NIM models."""
        return [
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "nvidia/llama-3.1-nemotron-8b-instruct",
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "mistralai/mistral-large-2",
            "mistralai/mixtral-8x7b-instruct-v0.1",
            "google/gemma-2-27b-it",
            "deepseek-ai/deepseek-coder-33b-instruct",
        ]


# Register the provider
register_provider(NVIDIAProvider)