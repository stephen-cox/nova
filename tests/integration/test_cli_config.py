"""Integration tests for config CLI commands"""

import pytest
from pathlib import Path
from typer.testing import CliRunner

from nova.main import app


class TestConfigCLI:
    """Test config command integration"""
    
    def setup_method(self):
        """Set up test runner"""
        self.runner = CliRunner()
    
    def test_config_show_default(self):
        """Test showing default configuration"""
        result = self.runner.invoke(app, ["config", "show"])
        
        assert result.exit_code == 0
        assert "Current Configuration:" in result.stdout
        assert "AI Provider" in result.stdout
        assert "openai" in result.stdout
        assert "gpt-3.5-turbo" in result.stdout
    
    def test_config_show_with_file(self, sample_config_yaml):
        """Test showing configuration from specific file"""
        result = self.runner.invoke(app, ["config", "show", "--file", str(sample_config_yaml)])
        
        assert result.exit_code == 0
        assert "Current Configuration:" in result.stdout
        assert "openai" in result.stdout
    
    def test_config_show_nonexistent_file(self, temp_dir):
        """Test showing config with non-existent file"""
        nonexistent = temp_dir / "nonexistent.yaml"
        result = self.runner.invoke(app, ["config", "show", "--file", str(nonexistent)])
        
        assert result.exit_code == 1
        assert "Configuration file not found" in result.stdout
    
    def test_config_init_default(self, temp_dir):
        """Test initializing config file"""
        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            result = self.runner.invoke(app, ["config", "init"])
            
            assert result.exit_code == 0
            assert "Configuration file created" in result.stdout
            
            # Check file was created
            config_file = temp_dir / "nova-config.yaml"
            assert config_file.exists()
            
            # Check content
            content = config_file.read_text()
            assert "ai_model:" in content
            assert "provider: openai" in content
            
        finally:
            os.chdir(original_cwd)
    
    def test_config_init_custom_path(self, temp_dir):
        """Test initializing config file at custom path"""
        custom_path = temp_dir / "custom-config.yaml"
        
        result = self.runner.invoke(app, ["config", "init", "--output", str(custom_path)])
        
        assert result.exit_code == 0
        assert f"Configuration file created: {custom_path}" in result.stdout
        assert custom_path.exists()
    
    def test_config_help(self):
        """Test config command help"""
        result = self.runner.invoke(app, ["config", "--help"])
        
        assert result.exit_code == 0
        assert "Configuration commands" in result.stdout
    
    def test_config_show_help(self):
        """Test config show command help"""
        result = self.runner.invoke(app, ["config", "show", "--help"])
        
        assert result.exit_code == 0
        assert "Show current configuration" in result.stdout
        assert "--file" in result.stdout
    
    def test_config_init_help(self):
        """Test config init command help"""
        result = self.runner.invoke(app, ["config", "init", "--help"])
        
        assert result.exit_code == 0
        assert "Initialize a new configuration file" in result.stdout
        assert "--output" in result.stdout
    
    def test_global_config_option(self, sample_config_yaml):
        """Test using global --config option"""
        result = self.runner.invoke(app, ["--config", str(sample_config_yaml), "config", "show"])
        
        assert result.exit_code == 0
        assert "Current Configuration:" in result.stdout
    
    def test_config_show_api_key_hidden(self, temp_dir, sample_config_dict):
        """Test that API key is hidden in output"""
        import yaml
        
        # Create config with API key
        config_with_key = sample_config_dict.copy()
        config_with_key["ai_model"]["api_key"] = "secret-key-123"
        
        config_file = temp_dir / "with-key.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_with_key, f)
        
        result = self.runner.invoke(app, ["config", "show", "--file", str(config_file)])
        
        assert result.exit_code == 0
        assert "***" in result.stdout  # API key should be masked
        assert "secret-key-123" not in result.stdout  # Original key should not appear
    
    def test_config_show_no_api_key(self, monkeypatch):
        """Test showing config when no API key is set"""
        # Clear all API key environment variables
        for key in ['NOVA_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY']:
            monkeypatch.delenv(key, raising=False)
        
        result = self.runner.invoke(app, ["config", "show"])
        
        assert result.exit_code == 0
        assert "Not set" in result.stdout  # Should indicate API key not set