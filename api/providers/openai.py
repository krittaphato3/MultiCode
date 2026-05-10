"""
OpenAI provider implementation for MultiCode.

Provides access to OpenAI's GPT models including GPT-4, GPT-4 Turbo, and GPT-3.5.
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

OPENAI_API_BASE = "https://api.openai.com/v1"
OPENAI_DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI's API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        **kwargs,
    ):
        super().__init__(api_key, base_url or OPENAI_API_BASE)
        self.organization = organization

    @property
    def provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=ProviderType.OPENAI,
            name="OpenAI",
            description="Access GPT-4, GPT-4 Turbo, and GPT-3.5 models",
            requires_api_key=True,
            supports_streaming=True,
            supports_functions=True,
            base_url=OPENAI_API_BASE,
            default_model=OPENAI_DEFAULT_MODEL,
            website_url="https://platform.openai.com",
        )

    async def validate_credentials(self) -> bool:
        """Validate the OpenAI API key."""
        if not self.api_key:
            return False

        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            if response.status_code == 200:
                self._configured = True
                return True
            elif response.status_code == 401:
                raise AuthenticationError("Invalid OpenAI API key")
            elif response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            else:
                return False
        except requests.exceptions.Timeout:
            raise TimeoutError("Request timed out") from None
        except Exception as e:
            logger.error(f"OpenAI validation error: {e}")
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
        """Send a chat completion request to OpenAI."""
        if not self.api_key:
            raise AuthenticationError("No API key configured")

        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        api_messages.extend(self.format_messages(messages))

        payload = {
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
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
            )

            if response.status_code == 401:
                raise AuthenticationError("Invalid OpenAI API key")
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(f"Rate limit exceeded", retry_after)
            elif response.status_code >= 400:
                raise Exception(f"OpenAI API error: {response.status_code}")

            data = response.json()
            return self.parse_response(data, model)

        except requests.exceptions.Timeout:
            raise TimeoutError("Request timed out") from None
        except Exception as e:
            if isinstance(e, (AuthenticationError, RateLimitError, TimeoutError)):
                raise
            logger.error(f"OpenAI API error: {e}")
            raise

    def parse_response(self, data: dict, model: str | None = None) -> ChatResponse:
        """Parse OpenAI API response."""
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
            provider=ProviderType.OPENAI,
        )

    async def list_models(self) -> list[ModelInfo]:
        """List available OpenAI models."""
        if not self.api_key:
            return []

        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )

            if response.status_code != 200:
                return []

            data = response.json()
            models = []

            for model in data.get("data", []):
                model_id = model.get("id", "")
                if model_id.startswith(("gpt-", "o1-", "o3-")):
                    models.append(ModelInfo(
                        id=model_id,
                        name=model.get("display_name", model_id),
                        provider=ProviderType.OPENAI,
                        description=model.get("description"),
                        context_length=model.get("context_window"),
                    ))

            return models

        except Exception as e:
            logger.error(f"Error listing OpenAI models: {e}")
            return []

    async def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get information about a specific OpenAI model."""
        models = await self.list_models()
        for model in models:
            if model.id == model_id:
                return model
        return None

    def get_supported_models(self) -> list[str]:
        """Get list of supported OpenAI models."""
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-4-32k",
            "gpt-3.5-turbo",
            "o1-preview",
            "o1-mini",
            "o3-mini",
        ]


# Register the provider
register_provider(OpenAIProvider)