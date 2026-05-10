"""Configuration module for MultiCode settings management."""

from __future__ import annotations

from pathlib import Path

from .settings import (
    AgentSettings,
    AgentSettingsModel,
    APISettings,
    APISettingsModel,
    FileOperationSettings,
    FileOperationSettingsModel,
    MemorySettings,
    ProviderCredentialConfig,
    ProviderSettings,
    SafetySettings,
    SafetySettingsModel,
    Settings,
    SettingsModel,
    UISettings,
    UISettingsModel,
    get_active_provider,
    get_api_key,
    get_configured_providers,
    get_default_model,
    get_max_agents,
    get_provider_credential,
    get_selected_models,
    get_settings,
    is_setup_complete,
    load_config,
    reset_settings,
    save_config,
    save_settings,
    set_active_provider,
    set_api_key,
    set_default_model,
    set_max_agents,
    set_provider_credential,
    set_selected_models,
)

APP_NAME = "MultiCode"
CONFIG_DIR = Path.home() / ".multicode"
CONFIG_FILE = CONFIG_DIR / "settings.json"
CONFIG_FILE_LEGACY = CONFIG_DIR / "config.json"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_AGENTS_WARNING_THRESHOLD = 10

SUPPORTED_PROVIDERS = [
    "openrouter",
    "openai",
    "anthropic",
    "nvidia",
    "groq",
    "mistral",
    "google",
    "ollama",
]

PROVIDER_INFO = {
    "openrouter": {
        "name": "OpenRouter",
        "description": "Access 300+ models through unified API",
        "website": "https://openrouter.ai",
        "key_prefix": "sk-or-",
    },
    "openai": {
        "name": "OpenAI",
        "description": "GPT-4, GPT-4 Turbo, and GPT-3.5",
        "website": "https://platform.openai.com",
        "key_prefix": "sk-",
    },
    "anthropic": {
        "name": "Anthropic",
        "description": "Claude 3.5, Claude 3, and Claude 2",
        "website": "https://anthropic.com",
        "key_prefix": "sk-ant-",
    },
    "nvidia": {
        "name": "NVIDIA NIM",
        "description": "Nemotron, Llama, Mistral via NIM",
        "website": "https://developer.nvidia.com/nim",
        "key_prefix": "nvapi-",
    },
    "groq": {
        "name": "Groq",
        "description": "Fast inference with Llama and Mixtral",
        "website": "https://console.groq.com",
        "key_prefix": "gsk_",
    },
    "mistral": {
        "name": "Mistral AI",
        "description": "Mistral Large, Small, and open models",
        "website": "https://mistral.ai",
        "key_prefix": "",
    },
    "google": {
        "name": "Google AI",
        "description": "Gemini Pro and Gemini Flash",
        "website": "https://ai.google.dev",
        "key_prefix": "",
    },
    "ollama": {
        "name": "Ollama",
        "description": "Local LLMs (Llama, Mistral, CodeLlama)",
        "website": "https://ollama.ai",
        "key_prefix": "",
        "local": True,
    },
}

__all__ = [
    "AgentSettings",
    "AgentSettingsModel",
    "APISettings",
    "APISettingsModel",
    "APP_NAME",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "CONFIG_FILE_LEGACY",
    "FileOperationSettings",
    "FileOperationSettingsModel",
    "get_active_provider",
    "get_api_key",
    "get_configured_providers",
    "get_default_model",
    "get_max_agents",
    "get_provider_credential",
    "get_selected_models",
    "get_settings",
    "is_setup_complete",
    "load_config",
    "MAX_AGENTS_WARNING_THRESHOLD",
    "MemorySettings",
    "OPENROUTER_BASE_URL",
    "ProviderCredentialConfig",
    "ProviderSettings",
    "PROVIDER_INFO",
    "reset_settings",
    "save_config",
    "save_settings",
    "SafetySettings",
    "SafetySettingsModel",
    "set_active_provider",
    "set_api_key",
    "set_default_model",
    "set_max_agents",
    "set_provider_credential",
    "set_selected_models",
    "Settings",
    "SettingsModel",
    "SUPPORTED_PROVIDERS",
    "UISettings",
    "UISettingsModel",
]