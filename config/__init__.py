"""Configuration module for MultiCode settings management."""

# Application constants (defined before imports by design)
APP_NAME = "MultiCode"  # noqa: E402
CONFIG_DIR = __import__('pathlib').Path.home() / ".multicode"  # noqa: E402
CONFIG_FILE = CONFIG_DIR / "settings.json"  # noqa: E402
CONFIG_FILE_LEGACY = CONFIG_DIR / "config.json"  # noqa: E402
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"  # noqa: E402
MAX_AGENTS_WARNING_THRESHOLD = 10  # noqa: E402

from .settings import (  # noqa: E402
    AgentSettings,
    AgentSettingsModel,
    APISettings,
    APISettingsModel,
    FileOperationSettings,
    FileOperationSettingsModel,
    MemorySettings,
    SafetySettings,
    SafetySettingsModel,
    Settings,
    SettingsModel,
    UISettings,
    UISettingsModel,
    get_api_key,
    get_default_model,
    get_max_agents,
    # Legacy compatibility functions
    get_selected_models,
    get_settings,
    is_setup_complete,
    load_config,
    reset_settings,
    save_config,
    save_settings,
    set_api_key,
    set_default_model,
    set_max_agents,
    set_selected_models,
)

__all__ = [
    # Constants
    "APP_NAME",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "CONFIG_FILE_LEGACY",
    "OPENROUTER_BASE_URL",
    "MAX_AGENTS_WARNING_THRESHOLD",
    # Settings classes
    "Settings",
    "SettingsModel",
    "AgentSettings",
    "AgentSettingsModel",
    "FileOperationSettings",
    "FileOperationSettingsModel",
    "APISettings",
    "APISettingsModel",
    "MemorySettings",
    "SafetySettings",
    "SafetySettingsModel",
    "UISettings",
    "UISettingsModel",
    # Functions
    "get_settings",
    "save_settings",
    "reset_settings",
    "get_api_key",
    "set_api_key",
    "get_max_agents",
    "set_max_agents",
    "get_default_model",
    "set_default_model",
    "load_config",
    "save_config",
    "get_selected_models",
    "set_selected_models",
    "is_setup_complete",
]
