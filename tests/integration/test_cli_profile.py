"""Integration tests for CLI profile management commands"""

import pytest
from pathlib import Path
from typer.testing import CliRunner

from nova.main import app


class TestProfileCLI:
    """Test profile management CLI commands"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
    
    def test_config_profiles_list(self, temp_dir, sample_config_yaml):
        """Test listing available profiles"""
        result = self.runner.invoke(app, ["config", "profiles", "--file", str(sample_config_yaml)])
        
        assert result.exit_code == 0
        assert "Available AI Profiles:" in result.stdout
        assert "test" in result.stdout  # from sample config
        assert "openai" in result.stdout
        assert "gpt-3.5-turbo" in result.stdout
    
    def test_config_profiles_list_no_config(self, temp_dir):
        """Test listing profiles with default config"""
        # Change to temp directory so no local config is found
        import os
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            result = self.runner.invoke(app, ["config", "profiles"])
            
            assert result.exit_code == 0
            assert "Available AI Profiles:" in result.stdout
            assert "default" in result.stdout
            assert "gpt4" in result.stdout
            assert "claude" in result.stdout
            assert "llama" in result.stdout
        finally:
            os.chdir(original_cwd)
    
    def test_config_profiles_with_defaults(self, temp_dir):
        """Test listing profiles when config has empty profiles but defaults are added"""
        import yaml
        
        # Create config with no profiles (system will add defaults)
        empty_config = {
            "chat": {"history_dir": "~/.nova/test"},
            "profiles": {},
            "active_profile": None
        }
        
        config_file = temp_dir / "empty.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(empty_config, f)
        
        result = self.runner.invoke(app, ["config", "profiles", "--file", str(config_file)])
        
        assert result.exit_code == 0
        assert "Available AI Profiles:" in result.stdout
        # System adds default profiles when none exist
        assert "default" in result.stdout
        assert "gpt4" in result.stdout
    
    def test_config_profile_activate(self, temp_dir, sample_config_dict):
        """Test activating a profile"""
        import yaml
        
        # Create config file with multiple profiles
        config_with_profiles = sample_config_dict.copy()
        config_with_profiles["profiles"]["gpt4"] = {
            "name": "gpt4",
            "provider": "openai",
            "model_name": "gpt-4",
            "max_tokens": 4000,
            "temperature": 0.7
        }
        
        config_file = temp_dir / "multi-profile.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_with_profiles, f)
        
        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            result = self.runner.invoke(app, ["config", "profile", "gpt4", "--file", str(config_file)])
            
            assert result.exit_code == 0
            assert "Activated profile 'gpt4'" in result.stdout
            assert "openai/gpt-4" in result.stdout
            
            # Verify the config file was updated
            with open(config_file, 'r') as f:
                updated_config = yaml.safe_load(f)
            assert updated_config["active_profile"] == "gpt4"
        
        finally:
            os.chdir(original_cwd)
    
    def test_config_profile_not_found(self, temp_dir, sample_config_yaml):
        """Test activating a non-existent profile"""
        result = self.runner.invoke(app, ["config", "profile", "nonexistent", "--file", str(sample_config_yaml)])
        
        assert result.exit_code == 1
        assert "Profile 'nonexistent' not found" in result.stdout
        assert "Available profiles:" in result.stdout
        assert "test" in result.stdout
    
    def test_config_profile_invalid_config_file(self, temp_dir):
        """Test profile command with invalid config file"""
        nonexistent_file = temp_dir / "nonexistent.yaml"
        
        result = self.runner.invoke(app, ["config", "profile", "test", "--file", str(nonexistent_file)])
        
        assert result.exit_code == 1
        assert "Configuration error:" in result.stdout
    
    def test_config_profiles_invalid_config_file(self, temp_dir):
        """Test profiles list command with invalid config file"""
        nonexistent_file = temp_dir / "nonexistent.yaml"
        
        result = self.runner.invoke(app, ["config", "profiles", "--file", str(nonexistent_file)])
        
        assert result.exit_code == 1
        assert "Configuration error:" in result.stdout
    
    def test_config_profile_create_config_file(self, temp_dir):
        """Test profile activation creates config file if not specified"""
        # Change to temp directory so no local config exists
        import os
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # This should use default config and save to nova-config.yaml
            result = self.runner.invoke(app, ["config", "profile", "claude"])
            
            assert result.exit_code == 0
            assert "Activated profile 'claude'" in result.stdout
            
            # Check that nova-config.yaml was created
            config_file = temp_dir / "nova-config.yaml"
            assert config_file.exists()
            
            # Verify content
            import yaml
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            assert config_data["active_profile"] == "claude"
        
        finally:
            os.chdir(original_cwd)