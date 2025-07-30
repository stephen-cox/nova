"""Unit tests for configuration management"""

import os
from pathlib import Path
import pytest
import yaml

from nova.core.config import ConfigManager, ConfigError
from nova.models.config import NovaConfig, AIModelConfig, ChatConfig


class TestConfigManager:
    """Test the ConfigManager class"""
    
    def test_load_default_config(self):
        """Test loading default configuration"""
        manager = ConfigManager()
        config = manager._load_default_config()
        
        assert isinstance(config, NovaConfig)
        assert config.ai_model.provider == "openai"
        assert config.ai_model.model_name == "gpt-3.5-turbo"
        assert config.chat.auto_save is True
    
    def test_load_config_from_file(self, sample_config_yaml):
        """Test loading configuration from YAML file"""
        manager = ConfigManager()
        config = manager.load_config(sample_config_yaml)
        
        assert isinstance(config, NovaConfig)
        assert config.ai_model.provider == "openai"
        assert config.ai_model.model_name == "gpt-3.5-turbo"
        assert config.ai_model.max_tokens == 1000
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
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides(sample_config_dict.copy())
        
        assert config_data["ai_model"]["api_key"] == "env-api-key"
    
    def test_apply_env_overrides_openai_key(self, sample_config_dict, mock_env_vars):
        """Test OpenAI API key environment variable"""
        mock_env_vars(OPENAI_API_KEY="openai-key")
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides(sample_config_dict.copy())
        
        assert config_data["ai_model"]["api_key"] == "openai-key"
    
    def test_apply_env_overrides_anthropic_key(self, sample_config_dict, mock_env_vars):
        """Test Anthropic API key environment variable"""
        # Clear other API key env vars first
        import os
        for key in ['NOVA_API_KEY', 'OPENAI_API_KEY']:
            if key in os.environ:
                del os.environ[key]
        
        mock_env_vars(ANTHROPIC_API_KEY="anthropic-key")
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides(sample_config_dict.copy())
        
        assert config_data["ai_model"]["api_key"] == "anthropic-key"
    
    def test_apply_env_overrides_model(self, sample_config_dict, mock_env_vars):
        """Test model name environment variable override"""
        mock_env_vars(NOVA_MODEL="gpt-4")
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides(sample_config_dict.copy())
        
        assert config_data["ai_model"]["model_name"] == "gpt-4"
    
    def test_apply_env_overrides_provider(self, sample_config_dict, mock_env_vars):
        """Test provider environment variable override"""
        mock_env_vars(NOVA_PROVIDER="anthropic")
        
        manager = ConfigManager()
        config_data = manager._apply_env_overrides(sample_config_dict.copy())
        
        assert config_data["ai_model"]["provider"] == "anthropic"
    
    def test_save_config(self, temp_dir, sample_config):
        """Test saving configuration to file"""
        manager = ConfigManager()
        output_path = temp_dir / "output-config.yaml"
        
        manager.save_config(sample_config, output_path)
        
        assert output_path.exists()
        
        # Verify saved content
        with open(output_path, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        assert saved_data["ai_model"]["provider"] == "openai"
        assert saved_data["ai_model"]["model_name"] == "gpt-3.5-turbo"
        # API key should be replaced with placeholder
        assert "Set via NOVA_API_KEY environment variable" in saved_data["ai_model"]["api_key"]
    
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
        config = NovaConfig(
            ai_model=AIModelConfig(
                provider="openai",
                model_name="gpt-4",
                api_key="test-key"
            ),
            chat=ChatConfig(
                history_dir=Path("/tmp/test"),
                max_history_length=100
            )
        )
        
        assert config.ai_model.provider == "openai"
        assert config.ai_model.model_name == "gpt-4"
        assert config.chat.max_history_length == 100
    
    def test_default_values(self):
        """Test default values are applied correctly"""
        config = NovaConfig()
        
        assert config.ai_model.provider == "openai"
        assert config.ai_model.model_name == "gpt-3.5-turbo"
        assert config.ai_model.max_tokens == 2000
        assert config.ai_model.temperature == 0.7
        assert config.chat.auto_save is True
        assert config.chat.max_history_length == 50
    
    def test_invalid_temperature(self):
        """Test validation of temperature values"""
        with pytest.raises(ValueError):
            NovaConfig(
                ai_model=AIModelConfig(temperature=2.0)  # Should be 0-1
            )
    
    def test_invalid_max_tokens(self):
        """Test validation of max_tokens"""
        with pytest.raises(ValueError):
            NovaConfig(
                ai_model=AIModelConfig(max_tokens=-100)  # Should be positive
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