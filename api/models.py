"""
Model fetching and selection utilities for OpenRouter.
"""

from dataclasses import dataclass

from .openrouter import OpenRouterClient

# Known free model IDs on OpenRouter (updated periodically)
FREE_MODEL_IDS = {
    "google/gemma-2-9b-it:free",
    "google/gemma-2-27b-it:free",
    "meta-llama/llama-3-8b-instruct:free",
    "meta-llama/llama-3-70b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "openchat/openchat-7b:free",
    "huggingfaceh4/zephyr-7b-beta:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "microsoft/phi-3-medium-128k-instruct:free",
    "qwen/qwen-2-7b-instruct:free",
    "qwen/qwen-2.5-7b-instruct:free",
    "qwen/qwen-2.5-coder-7b-instruct:free",
    "deepseek/deepseek-coder-v2-lite-instruct:free",
    "nousresearch/hermes-2-pro-8b:free",
    "neversleep/llama-3-lumimaid-8b:free",
    "sonar/sonar-medium-chat:free",
    "sonar/sonar-medium-code:free",
    "sonar/sonar-pro-chat:free",
    "sonar/sonar-pro-code:free",
    "01-ai/yi-large:free",
    "alibaba/qwen-2.5-72b-instruct:free",
    "x-ai/grok-beta:free",
    "deepseek/deepseek-r1-distill-llama-70b:free",
    "deepseek/deepseek-r1-distill-qwen-32b:free",
    "tngtech/deepseek-r1t-chimera:free",
}

# Default free model to use when testing
DEFAULT_FREE_MODEL = "google/gemma-2-9b-it:free"

# Fallback free models if default is unavailable
FALLBACK_FREE_MODELS = [
    "meta-llama/llama-3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-2-27b-it:free",
]


@dataclass
class ModelInfo:
    """Information about an available model."""
    id: str
    name: str
    description: str | None = None
    context_length: int | None = None
    pricing_prompt: float | None = None
    pricing_completion: float | None = None
    is_archived: bool = False
    provider: str | None = None
    is_free: bool = False
    
    @classmethod
    def from_api_response(cls, data: dict) -> "ModelInfo":
        """Create ModelInfo from OpenRouter API response."""
        pricing = data.get("pricing", {})
        model_id = data.get("id", "unknown")
        
        # Check if model is free based on ID suffix or pricing
        is_free = (
            model_id.endswith(":free") or
            (pricing.get("prompt") == "0" and pricing.get("completion") == "0") or
            (pricing.get("prompt") == 0 and pricing.get("completion") == 0) or
            model_id in FREE_MODEL_IDS
        )
        
        return cls(
            id=model_id,
            name=data.get("name", model_id),
            description=data.get("description"),
            context_length=data.get("context_length"),
            pricing_prompt=pricing.get("prompt") if pricing else None,
            pricing_completion=pricing.get("completion") if pricing else None,
            is_archived=data.get("top_provider", {}).get("is_archived", False),
            provider=model_id.split("/")[0] if "/" in model_id else None,
            is_free=is_free,
        )

    def display_name(self) -> str:
        """Get a formatted display name."""
        base = self.name
        if self.context_length:
            base += f" ({self.context_length:,} ctx)"
        if self.is_free:
            base += " [FREE]"
        return base

    def pricing_display(self) -> str:
        """Get formatted pricing string."""
        if self.is_free:
            return "[green]FREE[/green]"
        
        if self.pricing_prompt is None and self.pricing_completion is None:
            return "Price unknown"

        parts = []
        if self.pricing_prompt:
            parts.append(f"${float(self.pricing_prompt):.6f}/1K prompt")
        if self.pricing_completion:
            parts.append(f"${float(self.pricing_completion):.6f}/1K completion")

        return " | ".join(parts)
    
    def is_popular(self) -> bool:
        """Check if this is a popular coding model."""
        popular_ids = {
            "anthropic/claude-3.5-sonnet",
            "anthropic/claude-3-opus",
            "openai/gpt-4-turbo",
            "openai/gpt-4o",
            "google/gemini-pro-1.5",
            "meta-llama/llama-3-70b-instruct",
            "mistralai/mistral-large",
            "codellama/codellama-34b-instruct",
        }
        return self.id in popular_ids


class ModelManager:
    """
    Manages fetching, caching, and selecting models from OpenRouter.
    """

    def __init__(self, client: OpenRouterClient):
        self.client = client
        self._cached_models: list[ModelInfo] = []
        self._is_loaded = False

    async def fetch_models(self, force_refresh: bool = False) -> list[ModelInfo]:
        """
        Fetch available models from OpenRouter.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of ModelInfo objects
        """
        if self._is_loaded and not force_refresh and self._cached_models:
            return self._cached_models

        # Use synchronous requests for reliability (same as API key validation)
        import requests
        
        try:
            response = requests.get(
                url="https://openrouter.ai/api/v1/models",
                headers={
                    "Authorization": f"Bearer {self.client.api_key}",
                    "HTTP-Referer": "https://github.com/multicode",
                    "X-OpenRouter-Title": "MultiCode",
                },
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to fetch models: HTTP {response.status_code}")
            
            raw_models = response.json().get("data", [])
        except requests.exceptions.Timeout:
            raise Exception("Request timed out while fetching models")
        except requests.exceptions.ConnectionError as e:
            raise Exception(f"Connection error: {e}")

        self._cached_models = [
            ModelInfo.from_api_response(model)
            for model in raw_models
            if not model.get("top_provider", {}).get("is_archived", False)
        ]

        # Sort: free models first, then by name
        self._cached_models.sort(key=lambda m: (not m.is_free, m.name.lower()))

        self._is_loaded = True
        return self._cached_models

    def get_models(self) -> list[ModelInfo]:
        """Get currently cached models."""
        return self._cached_models

    def get_free_models(self) -> list[ModelInfo]:
        """Get only free models."""
        return [m for m in self._cached_models if m.is_free]

    def get_paid_models(self) -> list[ModelInfo]:
        """Get only paid models."""
        return [m for m in self._cached_models if not m.is_free]

    def get_model_by_id(self, model_id: str) -> ModelInfo | None:
        """Get a specific model by its ID."""
        for model in self._cached_models:
            if model.id == model_id:
                return model
        return None

    def search_models(self, query: str, free_only: bool = False) -> list[ModelInfo]:
        """
        Search models by name or ID.

        Args:
            query: Search query (case-insensitive)
            free_only: If True, only search free models

        Returns:
            List of matching ModelInfo objects
        """
        query_lower = query.lower()
        models = self._cached_models
        if free_only:
            models = self.get_free_models()
        return [
            model for model in models
            if query_lower in model.id.lower() or query_lower in model.name.lower()
        ]

    def get_popular_models(self, limit: int = 10, free_only: bool = False) -> list[ModelInfo]:
        """
        Get a list of popular/recommended models for coding.

        Args:
            limit: Maximum number of models to return
            free_only: If True, only return free models

        Returns:
            List of ModelInfo objects
        """
        # Curated list of popular coding model IDs
        popular_ids = [
            "anthropic/claude-3.5-sonnet",
            "anthropic/claude-3-opus",
            "openai/gpt-4-turbo",
            "openai/gpt-4o",
            "google/gemini-pro-1.5",
            "meta-llama/llama-3-70b-instruct",
            "mistralai/mistral-large",
            "codellama/codellama-34b-instruct",
        ]
        
        # Add popular free models
        popular_free_ids = [
            "google/gemma-2-9b-it:free",
            "google/gemma-2-27b-it:free",
            "meta-llama/llama-3-8b-instruct:free",
            "meta-llama/llama-3-70b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
            "qwen/qwen-2.5-coder-7b-instruct:free",
            "deepseek/deepseek-coder-v2-lite-instruct:free",
        ]

        popular = []
        
        if free_only:
            # Only return free models
            for model_id in popular_free_ids:
                model = self.get_model_by_id(model_id)
                if model and model.is_free:
                    popular.append(model)
        else:
            # Mix of free and paid popular models
            for model_id in popular_ids:
                model = self.get_model_by_id(model_id)
                if model:
                    popular.append(model)
            
            for model_id in popular_free_ids:
                model = self.get_model_by_id(model_id)
                if model and model.is_free and model not in popular:
                    popular.append(model)

        # If we don't have enough, fill with any available models
        if len(popular) < limit:
            for model in self._cached_models:
                if model not in popular:
                    popular.append(model)
                if len(popular) >= limit:
                    break

        return popular[:limit]
    
    def get_default_free_model(self) -> str | None:
        """Get the default free model ID for testing."""
        # Check if default is available
        if self.get_model_by_id(DEFAULT_FREE_MODEL):
            return DEFAULT_FREE_MODEL
        
        # Try fallbacks
        for model_id in FALLBACK_FREE_MODELS:
            if self.get_model_by_id(model_id):
                return model_id
        
        # Return any available free model
        free_models = self.get_free_models()
        if free_models:
            return free_models[0].id
        
        return None

    def is_loaded(self) -> bool:
        """Check if models have been loaded."""
        return self._is_loaded
