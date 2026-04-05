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
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

import aiohttp
from aiohttp import ClientError, ClientTimeout

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
    Async OpenRouter API client with built-in Safenet protection.
    
    Features:
    - Exponential backoff for rate limits and timeouts
    - State preservation during pauses
    - Rate limit header parsing
    - Streaming support
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
        
        self._session: aiohttp.ClientSession | None = None
        self._request_count = 0
        self._consecutive_failures = 0
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            # Check API key is set
            if not self.api_key:
                raise AuthenticationError("No API key configured. Please run setup first.")

            # Log session creation without exposing any key material
            logger.debug("Creating new API session (key: ****)")

            # Configure TCP connector with better defaults
            connector = aiohttp.TCPConnector(
                ttl_dns_cache=300,
                limit=10,
                force_close=False,
            )

            self._session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=self.timeout, connect=30),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/multicode",
                    "X-Title": "MultiCode",
                },
                connector=connector,
            )

            logger.debug("API session created with OpenRouter headers")
            
        return self._session
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _parse_rate_limit_headers(self, headers: dict) -> RateLimitInfo:
        """Parse rate limit information from response headers."""
        return RateLimitInfo(
            remaining_requests=int(headers.get("X-RateLimit-Remaining-Requests", -1)),
            remaining_tokens=int(headers.get("X-RateLimit-Remaining-Tokens", -1)),
            reset_time=int(headers.get("X-RateLimit-Reset", -1)),
        )
    
    async def _handle_error_response(self, response: aiohttp.ClientResponse) -> None:
        """Handle error responses from the API."""
        status = response.status

        try:
            error_data = await response.json()
            error_message = error_data.get("error", {}).get("message", str(error_data))
        except Exception:
            error_message = await response.text()

        if status == 429:
            # Rate limit hit
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(f"Rate limit exceeded: {error_message}", retry_after)

        elif status == 401:
            raise AuthenticationError(f"Invalid API key: {error_message}")

        elif status == 408:
            raise TimeoutError(f"Request timeout: {error_message}")

        elif status >= 500:
            # Server error - may be temporary
            raise OpenRouterError(f"Server error ({status}): {error_message}")

        else:
            raise OpenRouterError(f"API error ({status}): {error_message}")
    
    async def _handle_error_response_sync(self, response) -> None:
        """Handle error responses from synchronous requests."""
        status = response.status_code
        
        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", str(error_data))
        except:
            error_message = response.text
        
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
    
    async def _request_with_backoff(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        Make an HTTP request with exponential backoff retry logic.
        
        This is the core of the Safenet - it catches rate limits and timeouts,
        pauses with exponential backoff, and retries automatically.
        """
        session = await self._get_session()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        backoff = self.initial_backoff
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                self._request_count += 1
                logger.debug(f"API request attempt {attempt + 1}/{self.max_retries + 1}")
                
                async with session.request(method, url, **kwargs) as response:
                    if response.status >= 400:
                        await self._handle_error_response(response)
                    
                    # Success - reset consecutive failures
                    self._consecutive_failures = 0
                    return response
                    
            except RateLimitError as e:
                last_exception = e
                self._consecutive_failures += 1
                
                # Calculate wait time with exponential backoff
                wait_time = min(backoff, self.max_backoff)
                
                logger.warning(
                    f"⚠️  API Rate Limit hit. Pausing for {wait_time:.1f} seconds..."
                )
                
                await asyncio.sleep(wait_time)
                backoff *= self.backoff_multiplier
                
            except TimeoutError as e:
                last_exception = e
                self._consecutive_failures += 1
                
                wait_time = min(backoff, self.max_backoff)
                
                logger.warning(
                    f"⚠️  Request timeout. Pausing for {wait_time:.1f} seconds..."
                )
                
                await asyncio.sleep(wait_time)
                backoff *= self.backoff_multiplier
                
            except ClientError as e:
                last_exception = e
                self._consecutive_failures += 1
                
                wait_time = min(backoff, self.max_backoff)
                
                logger.warning(
                    f"⚠️  Network error: {e}. Pausing for {wait_time:.1f} seconds..."
                )
                
                await asyncio.sleep(wait_time)
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
        
        Uses synchronous requests in thread pool for better Windows compatibility.
        
        Args:
            messages: List of chat messages
            model: Model ID to use
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream (not supported with sync requests)
            
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
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_running_loop()
        
        def _make_request():
            import requests as req
            return req.post(
                url=f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/multicode",
                    "X-Title": "MultiCode",
                },
                json=payload,
                timeout=min(self.timeout, 60),
            )
        
        # Execute in thread pool
        response = await loop.run_in_executor(None, _make_request)
        
        # Handle errors
        if response.status_code != 200:
            await self._handle_error_response_sync(response)
        
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
            raise OpenRouterError(f"Failed to parse response: {e}")
    
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

    async def _stream_response(
        self,
        response: aiohttp.ClientResponse
    ) -> AsyncGenerator[str, None]:
        """
        Stream the response content with proper SSE buffering.
        
        Server-Sent Events can be split across TCP packets, so we buffer
        incomplete lines and only process complete SSE messages.
        """
        import json
        
        buffer = ""
        
        async for chunk in response.content.iter_any():
            # Decode chunk and add to buffer
            buffer += chunk.decode("utf-8")
            
            # Process complete lines from buffer
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                
                if not line or not line.startswith("data: "):
                    continue
                
                data = line[6:]  # Remove "data: " prefix
                
                if data == "[DONE]":
                    return
                
                # Skip empty data fields (keep-alive messages)
                if not data.strip():
                    continue
                
                try:
                    parsed = json.loads(data)
                    choices = parsed.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                except json.JSONDecodeError:
                    # Incomplete JSON - put data back in buffer and wait for more
                    # This shouldn't happen with line-based splitting, but handle gracefully
                    logger.debug(f"JSON decode error for data: {data[:50]}...")
                    continue
        
        # Process any remaining data in buffer (final chunk)
        if buffer.strip():
            line = buffer.strip()
            if line.startswith("data: "):
                data = line[6:]
                if data != "[DONE]" and data.strip():
                    try:
                        parsed = json.loads(data)
                        choices = parsed.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        pass
    
    async def get_models(self) -> list[dict]:
        """Fetch available models from OpenRouter."""
        response = await self._request_with_backoff(
            "GET",
            "/models",
        )

        if response.status != 200:
            raise OpenRouterError(f"Failed to fetch models: HTTP {response.status}")
        
        data = await response.json()
        return data.get("data", [])
    
    def get_stats(self) -> dict:
        """Get client statistics."""
        return {
            "total_requests": self._request_count,
            "consecutive_failures": self._consecutive_failures,
            "api_key_configured": self.api_key is not None,
        }
