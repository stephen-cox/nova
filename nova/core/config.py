"""Configuration management and loading"""

import os
from pathlib import Path
from typing import Optional

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
        self._config: Optional[NovaConfig] = None
    
    def load_config(self, config_path: Optional[Path] = None) -> NovaConfig:
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
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}
            
            # Apply environment variable overrides
            config_data = self._apply_env_overrides(config_data)
            
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
        default_config_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"
        
        if default_config_path.exists():
            return self._load_from_file(default_config_path)
        
        # Fallback to empty config (uses Pydantic defaults)
        config_data = self._apply_env_overrides({})
        return NovaConfig(**config_data)
    
    def _apply_env_overrides(self, config_data: dict) -> dict:
        """Apply environment variable overrides"""
        
        # AI model overrides
        if "ai_model" not in config_data:
            config_data["ai_model"] = {}
        
        ai_model = config_data["ai_model"]
        
        # Check for API key in environment
        api_key = os.getenv("NOVA_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            ai_model["api_key"] = api_key
        
        # Check for base URL overrides
        base_url = os.getenv("NOVA_BASE_URL") or os.getenv("OLLAMA_HOST")
        if base_url:
            ai_model["base_url"] = base_url
        
        # Other environment overrides
        if os.getenv("NOVA_MODEL"):
            ai_model["model_name"] = os.getenv("NOVA_MODEL")
        
        if os.getenv("NOVA_PROVIDER"):
            ai_model["provider"] = os.getenv("NOVA_PROVIDER")
        
        return config_data
    
    def save_config(self, config: NovaConfig, config_path: Path) -> None:
        """Save configuration to file"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict and remove sensitive data
        config_dict = config.model_dump()
        if config_dict.get("ai_model", {}).get("api_key"):
            config_dict["ai_model"]["api_key"] = "# Set via NOVA_API_KEY environment variable"
        
        # Convert Path objects to strings for YAML serialization
        if "chat" in config_dict and "history_dir" in config_dict["chat"]:
            config_dict["chat"]["history_dir"] = str(config_dict["chat"]["history_dir"])
        
        try:
            with open(config_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise ConfigError(f"Error saving configuration to {config_path}: {e}")


# Global config manager instance
config_manager = ConfigManager()