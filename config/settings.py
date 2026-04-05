"""
Centralized Settings Management for MultiCode.

Provides a unified configuration interface with:
- Pydantic validation for all settings
- Environment variable overrides
- Automatic type coercion
- Helpful error messages
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Validation
# =============================================================================

class AgentSettingsModel(BaseModel):
    """Validated agent settings."""
    max_agents: int = Field(default=3, ge=1, le=10)
    min_agents: int = Field(default=1, ge=1)
    allow_dynamic_spawning: bool = True
    default_roles: list[str] = Field(default_factory=lambda: ["planner", "engineer", "reviewer"])
    max_debate_turns: int = Field(default=15, ge=1, le=50)
    require_unanimous_consensus: bool = True
    agent_timeout_seconds: int = Field(default=120, ge=30, le=600)

    @field_validator('max_agents', mode='before')
    @classmethod
    def validate_max_agents(cls, v):
        if v > 5:
            logger.warning(f"High agent count ({v}) may cause high API costs")
        return v

    @field_validator('max_debate_turns', mode='before')
    @classmethod
    def validate_debate_turns(cls, v):
        if v > 30:
            logger.warning(f"High debate turns ({v}) may cause long wait times")
        return v


class FileOperationSettingsModel(BaseModel):
    """Validated file operation settings."""
    allow_read: bool = True
    allow_write: bool = True
    allow_create: bool = True
    allow_delete: bool = False
    allow_move: bool = True
    allow_copy: bool = True
    allow_execute: bool = False
    max_file_size_mb: int = Field(default=10, ge=1, le=100)
    allowed_extensions: list[str] = Field(default_factory=lambda: [
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".json", ".yaml", ".yml", ".toml",
        ".md", ".txt", ".rst",
        ".html", ".css", ".scss",
        ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
        ".rs", ".go", ".java", ".cpp", ".c", ".h",
        ".rb", ".php", ".swift", ".kt",
    ])
    require_confirmation_for_write: bool = True
    require_confirmation_for_delete: bool = True


class APISettingsModel(BaseModel):
    """Validated API settings."""
    api_key: str | None = None
    base_url: str = "https://openrouter.ai/api/v1"
    timeout_seconds: int = Field(default=120, ge=30, le=600)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: float = Field(default=2.0, ge=0.1, le=30.0)
    default_model: str | None = None
    max_tokens_per_request: int = Field(default=4000, ge=500, le=32000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    
    @field_validator('default_model', mode='before')
    @classmethod
    def validate_model(cls, v):
        if v and not v.strip():
            return None
        return v


class SafetySettingsModel(BaseModel):
    """Validated safety settings."""
    enable_shell_safety: bool = True
    enable_file_safety: bool = True
    require_permission_for_sudo: bool = True
    require_permission_for_network: bool = True
    require_permission_for_file_delete: bool = True
    blocked_commands: list[str] = Field(default_factory=lambda: [
        "rm -rf /",
        "dd if=/dev/zero",
        "mkfs",
        ":(){:|:&};:",
        "format c:",
        "del /f /q /s",
    ])
    max_command_timeout_seconds: int = Field(default=60, ge=10, le=300)
    log_all_commands: bool = True


class UISettingsModel(BaseModel):
    """Validated UI settings."""
    theme: str = Field(default="default", pattern="^(default|dark|light)$")
    show_agent_thoughts: bool = True
    show_token_usage: bool = True
    show_timing: bool = True
    compact_mode: bool = False
    max_output_lines: int = Field(default=100, ge=10, le=1000)
    syntax_highlighting: bool = True
    banner_style: str = Field(default="default")


class SettingsModel(BaseModel):
    """Main validated settings model."""
    agent: AgentSettingsModel = Field(default_factory=AgentSettingsModel)
    file_operations: FileOperationSettingsModel = Field(default_factory=FileOperationSettingsModel)
    api: APISettingsModel = Field(default_factory=APISettingsModel)
    safety: SafetySettingsModel = Field(default_factory=SafetySettingsModel)
    ui: UISettingsModel = Field(default_factory=UISettingsModel)
    version: str = "1.0.0"
    
    def validate_all(self) -> list[str]:
        """
        Validate all settings and return list of warnings.
        
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Check agent settings
        if self.agent.max_agents > 5:
            warnings.append(f"⚠️  High agent count ({self.agent.max_agents}) may increase API costs")
        
        # Check API settings
        if not self.api.api_key:
            warnings.append("⚠️  API key not configured")
        
        if self.api.timeout_seconds < 60:
            warnings.append(f"⚠️  Low timeout ({self.api.timeout_seconds}s) may cause request failures")
        
        # Check safety settings
        if not self.safety.enable_shell_safety:
            warnings.append("⚠️  Shell safety is disabled - dangerous commands may execute")
        
        return warnings

    model_config = ConfigDict(validate_assignment=True)


# Configuration file location
CONFIG_DIR = Path.home() / ".multicode"
CONFIG_FILE = CONFIG_DIR / "settings.json"
ENV_FILE = Path.cwd() / ".env"


@dataclass
class AgentSettings:
    """Agent-related settings."""
    max_agents: int = 3
    min_agents: int = 1
    allow_dynamic_spawning: bool = True
    default_roles: list[str] = field(default_factory=lambda: ["planner", "engineer", "reviewer"])
    max_debate_turns: int = 15
    require_unanimous_consensus: bool = True
    agent_timeout_seconds: int = 120
    recommended_max: int = 5  # Warning threshold (not a hard limit)


@dataclass
class FileOperationSettings:
    """File operation permissions and settings."""
    allow_read: bool = True
    allow_write: bool = True
    allow_create: bool = True
    allow_delete: bool = False  # Dangerous - disabled by default
    allow_move: bool = True
    allow_copy: bool = True
    allow_execute: bool = False  # Dangerous - disabled by default
    max_file_size_mb: int = 10
    allowed_extensions: list[str] = field(default_factory=lambda: [
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".json", ".yaml", ".yml", ".toml",
        ".md", ".txt", ".rst",
        ".html", ".css", ".scss",
        ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
        ".rs", ".go", ".java", ".cpp", ".c", ".h",
        ".rb", ".php", ".swift", ".kt",
    ])
    blocked_paths: list[str] = field(default_factory=lambda: [
        "/etc", "/usr", "/bin", "/sbin",
        "/System", "/Applications",
        "C:\\Windows", "C:\\Program Files",
        "C:\\Users\\*\\AppData",
    ])
    require_confirmation_for_write: bool = True
    require_confirmation_for_delete: bool = True
    auto_backup: bool = True
    max_backups: int = 5


@dataclass
class APISettings:
    """OpenRouter API settings."""
    api_key: str | None = None
    base_url: str = "https://openrouter.ai/api/v1"
    timeout_seconds: int = 120
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    default_model: str | None = None
    fallback_models: list[str] = field(default_factory=lambda: [
        "google/gemma-2-9b-it:free",
        "meta-llama/llama-3-8b-instruct:free",
    ])
    max_tokens_per_request: int = 4000
    temperature: float = 0.7
    stream_responses: bool = True


@dataclass
class MemorySettings:
    """Memory and token management settings."""
    max_tokens: int = 8000
    compression_threshold: float = 0.8
    compression_model: str = "google/gemma-2-9b-it:free"
    enable_summarization: bool = True
    max_history_entries: int = 100
    token_estimation_method: str = "auto"  # "auto", "tiktoken", "character"


@dataclass
class SafetySettings:
    """Safety and security settings."""
    enable_shell_safety: bool = True
    enable_file_safety: bool = True
    require_permission_for_sudo: bool = True
    require_permission_for_network: bool = True
    require_permission_for_file_delete: bool = True
    require_permission_for_process_kill: bool = True
    blocked_commands: list[str] = field(default_factory=lambda: [
        "rm -rf /",
        "dd if=/dev/zero",
        "mkfs",
        ":(){:|:&};:",
        "format c:",
        "del /f /q /s",
    ])
    max_command_timeout_seconds: int = 60
    log_all_commands: bool = True
    shell_preference: str = "auto"  # auto, powershell, cmd, bash


@dataclass
class UISettings:
    """User interface settings."""
    theme: str = "default"  # "default", "dark", "light"
    show_agent_thoughts: bool = True
    show_token_usage: bool = True
    show_timing: bool = True
    compact_mode: bool = False
    max_output_lines: int = 100
    syntax_highlighting: bool = True
    show_diff_for_changes: bool = True
    banner_style: str = "default"  # Banner art theme


@dataclass
class RoutingSettings:
    """Task routing configuration for workflow selection."""
    enable_smart_routing: bool = True  # Auto-detect simple vs complex tasks
    force_mode: str = "auto"  # "auto", "simple", "complex", "audit"
    # When force_mode is "simple", all tasks use direct response
    # When force_mode is "complex", all tasks use multi-agent
    # When force_mode is "audit", multi-agent with full logging


@dataclass
class Settings:
    """
    Main settings class containing all configuration.
    
    This is the single source of truth for all MultiCode settings.
    Settings are loaded from ~/.multicode/settings.json and can be
    overridden via environment variables.
    """
    agent: AgentSettings = field(default_factory=AgentSettings)
    file_operations: FileOperationSettings = field(default_factory=FileOperationSettings)
    api: APISettings = field(default_factory=APISettings)
    memory: MemorySettings = field(default_factory=MemorySettings)
    safety: SafetySettings = field(default_factory=SafetySettings)
    ui: UISettings = field(default_factory=UISettings)
    routing: RoutingSettings = field(default_factory=RoutingSettings)
    
    # Metadata
    version: str = "1.0.0"
    config_path: Path = field(default_factory=lambda: CONFIG_FILE)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert settings to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "agent": asdict(self.agent),
            "file_operations": asdict(self.file_operations),
            "api": asdict(self.api),
            "memory": asdict(self.memory),
            "safety": asdict(self.safety),
            "ui": asdict(self.ui),
            "routing": asdict(self.routing),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        """Create Settings from dictionary."""
        settings = cls()
        
        if "version" in data:
            settings.version = data["version"]
        
        if "agent" in data:
            settings.agent = AgentSettings(**data["agent"])
        
        if "file_operations" in data:
            settings.file_operations = FileOperationSettings(**data["file_operations"])
        
        if "api" in data:
            settings.api = APISettings(**data["api"])
        
        if "memory" in data:
            settings.memory = MemorySettings(**data["memory"])
        
        if "safety" in data:
            settings.safety = SafetySettings(**data["safety"])
        
        if "ui" in data:
            settings.ui = UISettings(**data["ui"])

        if "routing" in data:
            settings.routing = RoutingSettings(**data["routing"])

        return settings
    
    def save(self, path: Path | None = None) -> bool:
        """
        Save settings to JSON file.
        
        Args:
            path: Optional path override
            
        Returns:
            True if saved successfully
        """
        save_path = path or self.config_path
        
        try:
            # Ensure directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to file
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False
    
    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        """
        Load settings from JSON file.
        
        Args:
            path: Optional path override
            
        Returns:
            Settings instance (with defaults if file not found)
        """
        load_path = path or CONFIG_FILE
        
        # Try new settings file first
        if load_path.exists():
            try:
                with open(load_path, encoding='utf-8') as f:
                    data = json.load(f)

                settings = cls.from_dict(data)
                settings.config_path = load_path

                # Apply environment variable overrides
                settings._apply_env_overrides()

                logger.info(f"Settings loaded from {load_path}")
                return settings

            except Exception as e:
                logger.error(f"Failed to load settings: {e}, trying legacy config")
        
        # Try legacy config.json for backward compatibility
        legacy_path = CONFIG_DIR / "config.json"
        if legacy_path.exists():
            try:
                with open(legacy_path, encoding='utf-8') as f:
                    data = json.load(f)
                
                # Convert legacy format to new format
                settings = cls()
                if "api_key" in data:
                    settings.api.api_key = data["api_key"]
                if "selected_models" in data and data["selected_models"]:
                    settings.api.default_model = data["selected_models"][0]
                if "max_agents" in data:
                    settings.agent.max_agents = data["max_agents"]
                
                settings.config_path = legacy_path
                logger.info(f"Legacy config loaded from {legacy_path}")
                return settings

            except Exception as e:
                logger.error(f"Failed to load legacy config: {e}")
        
        # No config found, use defaults
        logger.debug("No config found, using defaults")
        return cls()
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to settings."""
        # API Key from environment
        if os.getenv("OPENROUTER_API_KEY"):
            self.api.api_key = os.getenv("OPENROUTER_API_KEY")
        
        # Max agents from environment
        if os.getenv("MULTICODE_MAX_AGENTS"):
            try:
                self.agent.max_agents = int(os.getenv("MULTICODE_MAX_AGENTS", "3"))
            except ValueError:
                pass
        
        # Default model from environment
        if os.getenv("MULTICODE_MODEL"):
            self.api.default_model = os.getenv("MULTICODE_MODEL")
        
        # Timeout from environment
        if os.getenv("MULTICODE_TIMEOUT"):
            try:
                self.api.timeout_seconds = int(os.getenv("MULTICODE_TIMEOUT", "120"))
            except ValueError:
                pass
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self.agent = AgentSettings()
        self.file_operations = FileOperationSettings()
        self.api = APISettings()
        self.memory = MemorySettings()
        self.safety = SafetySettings()
        self.ui = UISettings()
        self.routing = RoutingSettings()
    
    def get_setting(self, path: str) -> Any:
        """
        Get a setting value by dot-notation path.
        
        Args:
            path: Dot-notation path (e.g., "agent.max_agents")
            
        Returns:
            Setting value or None if not found
        """
        parts = path.split(".")
        value: Any = self
        
        for part in parts:
            if isinstance(value, Settings):
                value = getattr(value, part, None)
            elif isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
        
        return value
    
    def set_setting(self, path: str, value: Any) -> bool:
        """
        Set a setting value by dot-notation path.
        
        Args:
            path: Dot-notation path (e.g., "agent.max_agents")
            value: Value to set
            
        Returns:
            True if set successfully
        """
        parts = path.split(".")
        
        # Navigate to parent
        current: Any = self
        for part in parts[:-1]:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return False
        
        # Set the value
        final_part = parts[-1]
        if hasattr(current, final_part):
            setattr(current, final_part, value)
            return True
        
        return False
    
    def validate(self) -> list[str]:
        """
        Validate settings using Pydantic and return list of warnings/errors.
        
        Returns:
            List of validation messages
        """
        messages = []
        
        try:
            # Convert to Pydantic model for validation
            pydantic_settings = SettingsModel(
                agent=AgentSettingsModel(
                    max_agents=self.agent.max_agents,
                    min_agents=self.agent.min_agents,
                    allow_dynamic_spawning=self.agent.allow_dynamic_spawning,
                    default_roles=self.agent.default_roles,
                    max_debate_turns=self.agent.max_debate_turns,
                    require_unanimous_consensus=self.agent.require_unanimous_consensus,
                    agent_timeout_seconds=self.agent.agent_timeout_seconds,
                ),
                file_operations=FileOperationSettingsModel(
                    allow_read=self.file_operations.allow_read,
                    allow_write=self.file_operations.allow_write,
                    allow_create=self.file_operations.allow_create,
                    allow_delete=self.file_operations.allow_delete,
                    max_file_size_mb=self.file_operations.max_file_size_mb,
                    require_confirmation_for_write=self.file_operations.require_confirmation_for_write,
                    require_confirmation_for_delete=self.file_operations.require_confirmation_for_delete,
                ),
                api=APISettingsModel(
                    api_key=self.api.api_key,
                    timeout_seconds=self.api.timeout_seconds,
                    max_retries=self.api.max_retries,
                    default_model=self.api.default_model,
                    max_tokens_per_request=self.api.max_tokens_per_request,
                    temperature=self.api.temperature,
                ),
                safety=SafetySettingsModel(
                    enable_shell_safety=self.safety.enable_shell_safety,
                    enable_file_safety=self.safety.enable_file_safety,
                    require_permission_for_sudo=self.safety.require_permission_for_sudo,
                    max_command_timeout_seconds=self.safety.max_command_timeout_seconds,
                ),
                ui=UISettingsModel(
                    theme=self.ui.theme,
                    show_agent_thoughts=self.ui.show_agent_thoughts,
                    show_token_usage=self.ui.show_token_usage,
                    show_timing=self.ui.show_timing,
                    max_output_lines=self.ui.max_output_lines,
                ),
            )
            
            # Get Pydantic validation warnings
            messages.extend(pydantic_settings.validate_all())
            
        except ValidationError as e:
            # Pydantic validation failed
            for error in e.errors():
                messages.append(f"ERROR: {error['loc'][0]}.{error['loc'][1]}: {error['msg']}")
        
        # Additional custom validations
        if self.agent.max_agents < 1:
            messages.append("ERROR: max_agents must be at least 1")
        
        if self.memory.max_tokens < 1000:
            messages.append("ERROR: max_tokens must be at least 1000")
        
        return messages


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def save_settings(settings: Settings | None = None) -> bool:
    """Save the global settings."""
    settings = settings or get_settings()
    return settings.save()


def reset_settings() -> Settings:
    """Reset settings to defaults and save."""
    global _settings
    _settings = Settings()
    _settings.save()
    return _settings


# Convenience functions for common settings
def get_api_key() -> str | None:
    """Get the OpenRouter API key."""
    return get_settings().api.api_key


def set_api_key(key: str) -> bool:
    """Set the OpenRouter API key."""
    settings = get_settings()
    settings.api.api_key = key
    return settings.save()


def get_max_agents() -> int:
    """Get the maximum number of agents."""
    return get_settings().agent.max_agents


def set_max_agents(count: int) -> bool:
    """Set the maximum number of agents."""
    settings = get_settings()
    settings.agent.max_agents = count
    return settings.save()


def get_default_model() -> str | None:
    """Get the default model ID."""
    return get_settings().api.default_model


def set_default_model(model: str) -> bool:
    """Set the default model ID."""
    settings = get_settings()
    settings.api.default_model = model
    return settings.save()


# Legacy compatibility functions
def load_config() -> dict:
    """Load configuration from file (legacy compatibility)."""
    settings = get_settings()
    return {
        "api_key": settings.api.api_key,
        "selected_models": [settings.api.default_model] if settings.api.default_model else [],
        "max_agents": settings.agent.max_agents,
        "workspace_dir": None,
    }


def save_config(config: dict) -> bool:
    """Save configuration to file (legacy compatibility)."""
    settings = get_settings()
    
    if "api_key" in config:
        settings.api.api_key = config["api_key"]
    if "selected_models" in config and config["selected_models"]:
        settings.api.default_model = config["selected_models"][0]
    if "max_agents" in config:
        settings.agent.max_agents = config["max_agents"]
    
    return settings.save()


def get_selected_models() -> list[str]:
    """Get the list of selected model IDs (legacy compatibility)."""
    settings = get_settings()
    if settings.api.default_model:
        return [settings.api.default_model]
    return settings.api.fallback_models


def set_selected_models(model_ids: list[str]) -> bool:
    """Save the selected model IDs (legacy compatibility)."""
    settings = get_settings()
    if model_ids:
        settings.api.default_model = model_ids[0]
    return settings.save()


def is_setup_complete() -> bool:
    """Check if the initial setup (API key) is complete (legacy compatibility)."""
    return get_api_key() is not None
