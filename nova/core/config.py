"""Configuration management and loading"""

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from nova.models.config import NovaConfig


class ConfigError(Exception):
    """Configuration-related errors"""

    pass


class ConfigManager:
    """Manages configuration loading and validation"""

    DEFAULT_CONFIG_PATHS = [
        Path("nova-config.yaml"),
        Path("~/.nova/config.yaml"),
        Path("~/.config/nova/config.yaml"),
    ]

    def __init__(self):
        self._config: NovaConfig | None = None

    def load_config(self, config_path: Path | None = None) -> NovaConfig:
        """Load configuration from file or defaults"""

        # If specific path provided, use it
        if config_path:
            if not config_path.exists():
                raise ConfigError(f"Configuration file not found: {config_path}")
            return self._load_from_file(config_path)

        # Try default paths
        for path in self.DEFAULT_CONFIG_PATHS:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                return self._load_from_file(expanded_path)

        # Fall back to default config
        return self._load_default_config()

    def _load_from_file(self, config_path: Path) -> NovaConfig:
        """Load configuration from YAML file"""
        try:
            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}

            # Apply environment variable overrides
            config_data = self._apply_env_overrides(config_data)

            # Add default profiles if none exist
            config_data = self._add_default_profiles(config_data)

            return NovaConfig(**config_data)

        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {config_path}: {e}")
        except ValidationError as e:
            raise ConfigError(f"Invalid configuration in {config_path}: {e}")
        except Exception as e:
            raise ConfigError(f"Error loading configuration from {config_path}: {e}")

    def _load_default_config(self) -> NovaConfig:
        """Load default configuration"""
        # Load from packaged default config
        default_config_path = (
            Path(__file__).parent.parent.parent / "config" / "default.yaml"
        )

        if default_config_path.exists():
            return self._load_from_file(default_config_path)

        # Fallback to config with default profiles
        config_data = self._apply_env_overrides({})
        config_data = self._add_default_profiles(config_data)
        return NovaConfig(**config_data)

    def _apply_env_overrides(self, config_data: dict) -> dict:
        """Apply environment variable overrides"""

        # Profile selection override
        if os.getenv("NOVA_PROFILE"):
            config_data["active_profile"] = os.getenv("NOVA_PROFILE")

        # Apply API key overrides to all profiles
        api_key = (
            os.getenv("NOVA_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
        )
        base_url = os.getenv("NOVA_BASE_URL") or os.getenv("OLLAMA_HOST")

        if "profiles" in config_data:
            for _profile_name, profile_data in config_data["profiles"].items():
                # Apply API key if not already set in profile
                if api_key and not profile_data.get("api_key"):
                    profile_data["api_key"] = api_key

                # Apply base URL override if not already set
                if base_url and not profile_data.get("base_url"):
                    profile_data["base_url"] = base_url

                # Apply model/provider overrides if specified
                if os.getenv("NOVA_MODEL"):
                    profile_data["model_name"] = os.getenv("NOVA_MODEL")

                if os.getenv("NOVA_PROVIDER"):
                    profile_data["provider"] = os.getenv("NOVA_PROVIDER")

        return config_data

    def _add_default_profiles(self, config_data: dict) -> dict:
        """Add default AI profiles if none exist"""
        if "profiles" not in config_data:
            config_data["profiles"] = {}

        # Default profiles for common configurations
        default_profiles = {
            "default": {
                "name": "default",
                "provider": "openai",
                "model_name": "gpt-3.5-turbo",
                "max_tokens": 2000,
                "temperature": 0.7,
            },
            "gpt4": {
                "name": "gpt4",
                "provider": "openai",
                "model_name": "gpt-4",
                "max_tokens": 4000,
                "temperature": 0.7,
            },
            "claude": {
                "name": "claude",
                "provider": "anthropic",
                "model_name": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "temperature": 0.7,
            },
            "claude-opus": {
                "name": "claude-opus",
                "provider": "anthropic",
                "model_name": "claude-opus-4-20250514",
                "max_tokens": 4000,
                "temperature": 0.7,
            },
            "llama": {
                "name": "llama",
                "provider": "ollama",
                "model_name": "llama3.1",
                "base_url": "http://localhost:11434",
                "max_tokens": 2000,
                "temperature": 0.7,
            },
        }

        # Only add profiles that don't already exist
        for profile_name, profile_data in default_profiles.items():
            if profile_name not in config_data["profiles"]:
                config_data["profiles"][profile_name] = profile_data

        # Set default active profile if not specified
        if "active_profile" not in config_data or config_data["active_profile"] is None:
            config_data["active_profile"] = "default"

        return config_data

    def save_config(self, config: NovaConfig, config_path: Path) -> None:
        """Save configuration to file"""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict and remove sensitive data from profiles
        config_dict = config.model_dump()

        # Remove API keys from profiles for security
        if "profiles" in config_dict:
            for _profile_name, profile_data in config_dict["profiles"].items():
                if profile_data.get("api_key"):
                    profile_data["api_key"] = (
                        "# Set via environment variables (NOVA_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY)"
                    )

        # Convert Path objects to strings for YAML serialization
        if "chat" in config_dict and "history_dir" in config_dict["chat"]:
            config_dict["chat"]["history_dir"] = str(config_dict["chat"]["history_dir"])

        if "prompts" in config_dict and "library_path" in config_dict["prompts"]:
            config_dict["prompts"]["library_path"] = str(
                config_dict["prompts"]["library_path"]
            )

        try:
            with open(config_path, "w") as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise ConfigError(f"Error saving configuration to {config_path}: {e}")


# Global config manager instance
config_manager = ConfigManager()
