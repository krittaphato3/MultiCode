"""
OpenRouter API client with robust error handling (The Safenet).

Features:
- Model fallback chain for reliability
- Rate limit protection with exponential backoff
- State preservation during pauses
- Automatic retry on failures
"""

import asyncio
import logging
from dataclasses import dataclass, field

import requests

from config import OPENROUTER_BASE_URL, get_api_key

logger = logging.getLogger(__name__)


# Model fallback chain - ordered by preference
# Used when primary model fails or is rate-limited
MODEL_FALLBACK_CHAIN = [
    # Primary models (high quality)
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "google/gemini-pro-1.5",
    
    # Secondary models (good balance)
    "meta-llama/llama-3.1-405b-instruct",
    "mistralai/mistral-large",
    
    # Free fallbacks (when paid models fail)
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-2-27b-it:free",
    "meta-llama/llama-3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
]

# Free-only fallback chain for testing/low-budget mode
FREE_MODEL_FALLBACK_CHAIN = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-2-27b-it:free",
    "meta-llama/llama-3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "google/gemma-2-9b-it:free",
    "mistralai/mistral-7b-instruct:free",
]


@dataclass
class RateLimitInfo:
    """Information about rate limit status."""
    remaining_requests: int | None = None
    remaining_tokens: int | None = None
    reset_time: int | None = None


@dataclass
class ChatMessage:
    """A single chat message in the conversation."""
    role: str  # "system", "user", or "assistant"
    content: str
    name: str | None = None  # For agent identification


@dataclass
class ChatResponse:
    """Response from the OpenRouter chat API."""
    content: str
    model: str
    finish_reason: str
    usage: dict = field(default_factory=dict)
    rate_limit_info: RateLimitInfo | None = None


class OpenRouterError(Exception):
    """Base exception for OpenRouter API errors."""
    pass


class RateLimitError(OpenRouterError):
    """Raised when rate limit is hit (429)."""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class TimeoutError(OpenRouterError):
    """Raised when request times out."""
    pass


class AuthenticationError(OpenRouterError):
    """Raised when API key is invalid (401)."""
    pass


class OpenRouterClient:
    """
    OpenRouter API client with built-in Safenet protection.

    Features:
    - Exponential backoff for rate limits and timeouts
    - Automatic retry on failures
    - Model fallback chain
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = OPENROUTER_BASE_URL,
        timeout: int = 120,
        max_retries: int = 5,
        initial_backoff: float = 2.0,
        backoff_multiplier: float = 2.0,
        max_backoff: float = 300.0,
    ):
        self.api_key = api_key or get_api_key()
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff = max_backoff

        self._request_count = 0
        self._consecutive_failures = 0

    def _parse_rate_limit_headers(self, headers: dict) -> RateLimitInfo:
        """Parse rate limit information from response headers."""
        return RateLimitInfo(
            remaining_requests=int(headers.get("X-RateLimit-Remaining-Requests", -1)),
            remaining_tokens=int(headers.get("X-RateLimit-Remaining-Tokens", -1)),
            reset_time=int(headers.get("X-RateLimit-Reset", -1)),
        )

    def _handle_error_response(self, response) -> None:
        """Handle error responses from requests."""
        status = response.status_code

        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", str(error_data))
        except Exception:
            try:
                error_message = response.text
            except Exception:
                error_message = "Unknown error"

        if status == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(f"Rate limit exceeded: {error_message}", retry_after)
        elif status == 401:
            raise AuthenticationError(f"Invalid API key: {error_message}")
        elif status == 408:
            raise TimeoutError(f"Request timeout: {error_message}")
        elif status >= 500:
            raise OpenRouterError(f"Server error ({status}): {error_message}")
        else:
            raise OpenRouterError(f"API error ({status}): {error_message}")

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> requests.Response:
        """
        Make an HTTP request with exponential backoff retry logic.

        This is the core of the Safenet - it catches rate limits and timeouts,
        pauses with exponential backoff, and retries automatically.
        """
        backoff = self.initial_backoff
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                self._request_count += 1
                logger.debug(f"API request attempt {attempt + 1}/{self.max_retries + 1}")

                response = requests.request(method, url, timeout=self.timeout, **kwargs)

                if response.status_code >= 400:
                    self._handle_error_response(response)

                # Success - reset consecutive failures
                self._consecutive_failures = 0
                return response

            except RateLimitError as e:
                last_exception = e
                self._consecutive_failures += 1
                wait_time = min(backoff, self.max_backoff)
                logger.warning(f"⚠️  API Rate Limit hit. Pausing for {wait_time:.1f} seconds...")
                import time
                time.sleep(wait_time)
                backoff *= self.backoff_multiplier

            except TimeoutError as e:
                last_exception = e
                self._consecutive_failures += 1
                wait_time = min(backoff, self.max_backoff)
                logger.warning(f"⚠️  Request timeout. Pausing for {wait_time:.1f} seconds...")
                import time
                time.sleep(wait_time)
                backoff *= self.backoff_multiplier

            except requests.RequestException as e:
                last_exception = e
                self._consecutive_failures += 1
                wait_time = min(backoff, self.max_backoff)
                logger.warning(f"⚠️  Network error: {e}. Pausing for {wait_time:.1f} seconds...")
                import time
                time.sleep(wait_time)
                backoff *= self.backoff_multiplier

        # All retries exhausted
        raise OpenRouterError(
            f"Max retries ({self.max_retries}) exceeded. "
            f"Last error: {last_exception}"
        )

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> ChatResponse:
        """
        Send a chat completion request to OpenRouter.

        Args:
            messages: List of chat messages
            model: Model ID to use
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream (not currently supported)

        Returns:
            ChatResponse
        """
        if not self.api_key:
            raise AuthenticationError("No API key configured")

        # Build messages list
        api_messages = []

        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            api_messages.append({
                "role": msg.role,
                "content": msg.content,
                **({"name": msg.name} if msg.name else {})
            })

        # Build request payload
        payload = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Make request using thread pool to avoid blocking async event loop
        loop = asyncio.get_running_loop()

        def _make_request():
            return self._request_with_retry(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/multicode",
                    "X-Title": "MultiCode",
                },
                json=payload,
            )

        # Execute in thread pool
        response = await loop.run_in_executor(None, _make_request)

        # Parse response
        try:
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise OpenRouterError("No choices in response")
            
            choice = choices[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            
            return ChatResponse(
                content=content or "",
                model=data.get("model", model),
                finish_reason=choice.get("finish_reason", "unknown"),
                usage=data.get("usage", {}),
            )
        except Exception as e:
            raise OpenRouterError(f"Failed to parse response: {e}") from e
    
    async def chat_completion_with_fallback(
        self,
        messages: list[ChatMessage],
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_fallbacks: int = 3,
        free_only: bool = False,
    ) -> ChatResponse:
        """
        Send chat completion with automatic model fallback.
        
        When the primary model fails (rate limit, error, etc.), automatically
        tries fallback models in order of preference.
        
        Args:
            messages: List of chat messages
            model: Primary model ID to try
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            max_fallbacks: Maximum number of fallback attempts
            free_only: If True, only use free models in fallback chain
            
        Returns:
            ChatResponse from first successful model
            
        Example:
            response = await client.chat_completion_with_fallback(
                messages,
                model="anthropic/claude-3.5-sonnet",
                max_fallbacks=3
            )
            # If Claude fails, tries GPT-4o, then Gemini, then free models
        """
        # Build fallback chain
        if free_only:
            fallback_chain = FREE_MODEL_FALLBACK_CHAIN
        else:
            fallback_chain = MODEL_FALLBACK_CHAIN
        
        # Start with primary model, then fallbacks
        models_to_try = [model] + [
            m for m in fallback_chain 
            if m != model  # Don't duplicate primary model
        ][:max_fallbacks + 1]
        
        last_error = None
        
        for i, model_id in enumerate(models_to_try):
            is_primary = (i == 0)
            model_type = "primary" if is_primary else f"fallback #{i}"
            
            try:
                logger.info(f"Trying {model_type} model: {model_id}")
                
                response = await self.chat_completion(
                    messages=messages,
                    model=model_id,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                # Success!
                if not is_primary:
                    logger.warning(
                        f"Primary model failed, successfully used {model_id} instead"
                    )
                
                return response
                
            except (RateLimitError, TimeoutError, OpenRouterError) as e:
                last_error = e
                logger.warning(
                    f"Model {model_id} failed: {e}. "
                    f"{'Trying fallback...' if i < len(models_to_try) - 1 else 'No more fallbacks.'}"
                )
                continue
                
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error with {model_id}: {e}")
                continue
        
        # All models failed
        raise OpenRouterError(
            f"All {len(models_to_try)} models failed. Last error: {last_error}"
        )

    def get_stats(self) -> dict:
        """Get client statistics."""
        return {
            "total_requests": self._request_count,
            "consecutive_failures": self._consecutive_failures,
            "api_key_configured": self.api_key is not None,
        }
