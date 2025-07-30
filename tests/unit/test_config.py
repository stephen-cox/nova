"""Unit tests for configuration management"""

import os
from pathlib import Path
import pytest
import yaml

from nova.core.config import ConfigManager, ConfigError
from nova.models.config import NovaConfig, AIModelConfig, ChatConfig, AIProfile


class TestConfigManager:
    """Test the ConfigManager class"""
    
    def test_load_default_config(self):
        """Test loading default configuration"""
        manager = ConfigManager()
        config = manager._load_default_config()
        
        assert isinstance(config, NovaConfig)
        assert config.active_profile == "default"
        assert "default" in config.profiles
        
        # Test the active AI config
        active_config = config.get_active_ai_config()
        assert active_config.provider == "openai"
        assert active_config.model_name == "gpt-3.5-turbo"
        assert config.chat.auto_save is True
    
    def test_load_config_from_file(self, sample_config_yaml):
        """Test loading configuration from YAML file"""
        manager = ConfigManager()
        config = manager.load_config(sample_config_yaml)
        
        assert isinstance(config, NovaConfig)
        assert config.active_profile == "test"
        assert "test" in config.profiles
        
        # Test the active AI config from the loaded profile
        active_config = config.get_active_ai_config()
        assert active_config.provider == "openai"
        assert active_config.model_name == "gpt-3.5-turbo"
        assert active_config.max_tokens == 1000
        assert config.chat.max_history_length == 25
    
    def test_load_config_file_not_found(self, temp_dir):
        """Test loading configuration when file doesn't exist"""
        manager = ConfigManager()
        nonexistent_file = temp_dir / "nonexistent.yaml"
        
        with pytest.raises(ConfigError, match="Configuration file not found"):
            manager.load_config(nonexistent_file)
    
    def test_load_config_invalid_yaml(self, temp_dir, invalid_yaml_content):
        """Test loading configuration with invalid YAML"""
        manager = ConfigManager()
        config_file = temp_dir / "invalid.yaml"
        
        with open(config_file, 'w') as f:
            f.write(invalid_yaml_content)
        
        with pytest.raises(ConfigError, match="Invalid YAML"):
            manager.load_config(config_file)
    
    def test_apply_env_overrides_api_key(self, sample_config_dict, mock_env_vars):
        """Test environment variable overrides for API key"""
        mock_env_vars(NOVA_API_KEY="env-api-key")
        
        # Remove existing API key from profile to test override
        sample_config_dict["profiles"]["test"]["api_key"] = None
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides(sample_config_dict.copy())
        
        # API key should be applied to the profile
        assert config_data["profiles"]["test"]["api_key"] == "env-api-key"
    
    def test_apply_env_overrides_openai_key(self, sample_config_dict, mock_env_vars):
        """Test OpenAI API key environment variable"""
        mock_env_vars(OPENAI_API_KEY="openai-key")
        
        # Remove existing API key from profile to test override
        sample_config_dict["profiles"]["test"]["api_key"] = None
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides(sample_config_dict.copy())
        
        assert config_data["profiles"]["test"]["api_key"] == "openai-key"
    
    def test_apply_env_overrides_anthropic_key(self, sample_config_dict, mock_env_vars):
        """Test Anthropic API key environment variable"""
        # Clear other API key env vars first
        import os
        for key in ['NOVA_API_KEY', 'OPENAI_API_KEY']:
            if key in os.environ:
                del os.environ[key]
        
        mock_env_vars(ANTHROPIC_API_KEY="anthropic-key")
        
        # Remove existing API key from profile to test override
        sample_config_dict["profiles"]["test"]["api_key"] = None
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides(sample_config_dict.copy())
        
        assert config_data["profiles"]["test"]["api_key"] == "anthropic-key"
    
    def test_apply_env_overrides_model(self, sample_config_dict, mock_env_vars):
        """Test model name environment variable override"""
        mock_env_vars(NOVA_MODEL="gpt-4")
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides(sample_config_dict.copy())
        
        assert config_data["profiles"]["test"]["model_name"] == "gpt-4"
    
    def test_apply_env_overrides_provider(self, sample_config_dict, mock_env_vars):
        """Test provider environment variable override"""
        mock_env_vars(NOVA_PROVIDER="anthropic")
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides(sample_config_dict.copy())
        
        assert config_data["profiles"]["test"]["provider"] == "anthropic"
    
    def test_save_config(self, temp_dir, sample_config):
        """Test saving configuration to file"""
        manager = ConfigManager()
        output_path = temp_dir / "output-config.yaml"
        
        manager.save_config(sample_config, output_path)
        
        assert output_path.exists()
        
        # Verify saved content
        with open(output_path, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        assert saved_data["profiles"]["test"]["provider"] == "openai"
        assert saved_data["profiles"]["test"]["model_name"] == "gpt-3.5-turbo"
        # API key should be replaced with placeholder
        assert "Set via environment variables" in saved_data["profiles"]["test"]["api_key"]
    
    def test_save_config_creates_directory(self, temp_dir, sample_config):
        """Test that save_config creates parent directories"""
        manager = ConfigManager()
        nested_path = temp_dir / "nested" / "dir" / "config.yaml"
        
        manager.save_config(sample_config, nested_path)
        
        assert nested_path.exists()
        assert nested_path.parent.exists()


class TestNovaConfig:
    """Test the NovaConfig Pydantic model"""
    
    def test_valid_config_creation(self):
        """Test creating a valid configuration"""
        test_profile = AIProfile(
            name="test",
            provider="openai",
            model_name="gpt-4",
            api_key="test-key"
        )
        
        config = NovaConfig(
            profiles={"test": test_profile},
            active_profile="test",
            chat=ChatConfig(
                history_dir=Path("/tmp/test"),
                max_history_length=100
            )
        )
        
        active_config = config.get_active_ai_config()
        assert active_config.provider == "openai"
        assert active_config.model_name == "gpt-4"
        assert config.chat.max_history_length == 100
    
    def test_default_values(self):
        """Test default values are applied correctly"""
        config = NovaConfig()
        
        # Should have default active profile
        assert config.active_profile == "default"
        assert config.chat.auto_save is True
        assert config.chat.max_history_length == 50
        
        # With no profiles, should get minimal defaults from get_active_ai_config
        active_config = config.get_active_ai_config()
        assert active_config.provider == "openai"  # AIModelConfig default
        assert active_config.model_name == "gpt-3.5-turbo"  # AIModelConfig default
    
    def test_invalid_temperature(self):
        """Test validation of temperature values"""
        with pytest.raises(ValueError):
            AIProfile(
                name="test",
                provider="openai",
                model_name="gpt-4",
                temperature=2.0  # Should be 0-1
            )
    
    def test_invalid_max_tokens(self):
        """Test validation of max_tokens"""
        with pytest.raises(ValueError):
            AIProfile(
                name="test",
                provider="openai",
                model_name="gpt-4",
                max_tokens=-100  # Should be positive
            )


class TestAIModelConfig:
    """Test the AIModelConfig Pydantic model"""
    
    def test_valid_providers(self):
        """Test valid AI providers"""
        for provider in ["openai", "anthropic"]:
            config = AIModelConfig(provider=provider)
            assert config.provider == provider
    
    def test_temperature_validation(self):
        """Test temperature must be between 0 and 1"""
        # Valid temperatures
        AIModelConfig(temperature=0.0)
        AIModelConfig(temperature=0.5)
        AIModelConfig(temperature=1.0)
        
        # Invalid temperatures should raise validation error
        with pytest.raises(ValueError):
            AIModelConfig(temperature=-0.1)
        
        with pytest.raises(ValueError):
            AIModelConfig(temperature=1.1)


class TestChatConfig:
    """Test the ChatConfig Pydantic model"""
    
    def test_path_expansion(self):
        """Test that paths are properly expanded"""
        config = ChatConfig(history_dir=Path("~/test"))
        # Path should be stored as-is, expansion happens during use
        assert "~" in str(config.history_dir)
    
    def test_max_history_validation(self):
        """Test max_history_length validation"""
        # Valid values
        ChatConfig(max_history_length=1)
        ChatConfig(max_history_length=100)
        
        # Invalid values
        with pytest.raises(ValueError):
            ChatConfig(max_history_length=0)
        
        with pytest.raises(ValueError):
            ChatConfig(max_history_length=-1)


class TestAIProfiles:
    """Test the AI Profile functionality"""
    
    def test_profile_creation(self):
        """Test creating an AI profile"""
        profile = AIProfile(
            name="test-profile",
            provider="openai",
            model_name="gpt-4",
            max_tokens=3000,
            temperature=0.8
        )
        
        assert profile.name == "test-profile"
        assert profile.provider == "openai"
        assert profile.model_name == "gpt-4"
        assert profile.max_tokens == 3000
        assert profile.temperature == 0.8
    
    def test_profile_validation(self):
        """Test profile validation"""
        # Valid providers
        AIProfile(name="test", provider="openai", model_name="gpt-4")
        AIProfile(name="test", provider="anthropic", model_name="claude-3")
        AIProfile(name="test", provider="ollama", model_name="llama2")
        
        # Invalid provider
        with pytest.raises(ValueError, match="Provider must be one of"):
            AIProfile(name="test", provider="invalid", model_name="model")
    
    def test_nova_config_with_profiles(self):
        """Test NovaConfig with profiles"""
        profile1 = AIProfile(
            name="gpt4",
            provider="openai", 
            model_name="gpt-4"
        )
        profile2 = AIProfile(
            name="claude",
            provider="anthropic",
            model_name="claude-3-sonnet"
        )
        
        config = NovaConfig(
            profiles={"gpt4": profile1, "claude": profile2},
            active_profile="gpt4"
        )
        
        assert len(config.profiles) == 2
        assert config.active_profile == "gpt4"
        assert "gpt4" in config.profiles
        assert "claude" in config.profiles
    
    def test_get_active_ai_config_with_profile(self):
        """Test getting active AI config when using a profile"""
        profile = AIProfile(
            name="test-profile",
            provider="anthropic",
            model_name="claude-3-haiku",
            max_tokens=1500,
            temperature=0.6
        )
        
        config = NovaConfig(
            profiles={"test": profile},
            active_profile="test"
        )
        
        active_config = config.get_active_ai_config()
        assert active_config.provider == "anthropic"
        assert active_config.model_name == "claude-3-haiku"
        assert active_config.max_tokens == 1500
        assert active_config.temperature == 0.6
    
    def test_get_active_ai_config_without_explicit_profile(self):
        """Test getting active AI config when using default profile"""
        # Create config with default profile
        default_profile = AIProfile(
            name="default",
            provider="openai",
            model_name="gpt-3.5-turbo",
            max_tokens=2000,
            temperature=0.7
        )
        
        config = NovaConfig(
            profiles={"default": default_profile},
            active_profile="default"
        )
        
        active_config = config.get_active_ai_config()
        assert active_config.provider == "openai"
        assert active_config.model_name == "gpt-3.5-turbo"
    
    def test_get_active_ai_config_invalid_profile(self):
        """Test getting active AI config with invalid profile"""
        # Create config with only a default profile
        default_profile = AIProfile(
            name="default",
            provider="anthropic",
            model_name="claude-3-sonnet",
            max_tokens=3000,
            temperature=0.8
        )
        
        config = NovaConfig(
            profiles={"default": default_profile},
            active_profile="nonexistent"
        )
        
        # Should fall back to default profile
        active_config = config.get_active_ai_config()
        assert active_config.provider == "anthropic"
        assert active_config.model_name == "claude-3-sonnet"
    
    def test_config_manager_adds_default_profiles(self):
        """Test that ConfigManager adds default profiles"""
        manager = ConfigManager()
        config = manager._load_default_config()
        
        # Should have default profiles
        assert len(config.profiles) > 0
        assert "default" in config.profiles
        assert "gpt4" in config.profiles
        assert "claude" in config.profiles
        assert "claude-opus" in config.profiles
        assert "llama" in config.profiles
        
        # Verify default profile
        default_profile = config.profiles["default"]
        assert default_profile.provider == "openai"
        assert default_profile.model_name == "gpt-3.5-turbo"
        
        # Verify other profile properties
        gpt4_profile = config.profiles["gpt4"]
        assert gpt4_profile.provider == "openai"
        assert gpt4_profile.model_name == "gpt-4"
        
        claude_profile = config.profiles["claude"]
        assert claude_profile.provider == "anthropic"
        assert claude_profile.model_name == "claude-sonnet-4-20250514"
        
        claude_opus_profile = config.profiles["claude-opus"]
        assert claude_opus_profile.provider == "anthropic"
        assert claude_opus_profile.model_name == "claude-opus-4-20250514"
        
        llama_profile = config.profiles["llama"]
        assert llama_profile.provider == "ollama"
        assert llama_profile.model_name == "llama3.1"
        
        # Verify default active profile
        assert config.active_profile == "default"
    
    def test_env_override_profile_selection(self, monkeypatch):
        """Test that NOVA_PROFILE environment variable works"""
        monkeypatch.setenv("NOVA_PROFILE", "claude")
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides({})
        
        assert config_data["active_profile"] == "claude"