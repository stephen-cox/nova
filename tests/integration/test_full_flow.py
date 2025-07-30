"""End-to-end integration tests for complete workflows"""

import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
import tempfile
import os

from nova.main import app
from nova.core.config import config_manager
from nova.core.history import HistoryManager
from nova.models.message import Conversation, MessageRole


class TestFullWorkflows:
    """Test complete user workflows end-to-end"""
    
    def setup_method(self):
        """Set up test runner"""
        self.runner = CliRunner()
    
    def test_complete_first_time_user_flow(self, temp_dir):
        """Test complete workflow for first-time user"""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Step 1: User runs nova --help to see what's available
            result = self.runner.invoke(app, ["--help"])
            assert result.exit_code == 0
            assert "Nova - AI Research Assistant" in result.stdout
            
            # Step 2: User initializes config
            result = self.runner.invoke(app, ["config", "init"])
            assert result.exit_code == 0
            assert "Configuration file created" in result.stdout
            
            # Step 3: User checks their config
            result = self.runner.invoke(app, ["config", "show"])
            assert result.exit_code == 0
            assert "Current Configuration:" in result.stdout
            assert "openai" in result.stdout
            
            # Step 4: User checks chat help
            result = self.runner.invoke(app, ["chat", "--help"])
            assert result.exit_code == 0
            
            # Config file should exist
            config_file = temp_dir / "nova-config.yaml"
            assert config_file.exists()
            
        finally:
            os.chdir(original_cwd)
    
    def test_configuration_customization_flow(self, temp_dir):
        """Test workflow for customizing configuration"""
        # Create custom config directory
        config_dir = temp_dir / "custom_config"
        config_dir.mkdir()
        custom_config = config_dir / "nova.yaml"
        
        # Step 1: Create config at custom location
        result = self.runner.invoke(app, [
            "config", "init", "--output", str(custom_config)
        ])
        assert result.exit_code == 0
        
        # Step 2: Verify custom config works
        result = self.runner.invoke(app, [
            "--config", str(custom_config), "config", "show"
        ])
        assert result.exit_code == 0
        assert "Current Configuration:" in result.stdout
        
        # Step 3: Modify config file manually (simulate user editing)
        import yaml
        with open(custom_config, 'r') as f:
            config_data = yaml.safe_load(f)
        
        config_data['profiles']['default']['model_name'] = 'gpt-4'
        config_data['chat']['max_history_length'] = 100
        
        with open(custom_config, 'w') as f:
            yaml.dump(config_data, f)
        
        # Step 4: Verify changes are reflected
        result = self.runner.invoke(app, [
            "--config", str(custom_config), "config", "show"
        ])
        assert result.exit_code == 0
        assert "gpt-4" in result.stdout
        assert "100" in result.stdout
    
    @patch.dict(os.environ, {'NOVA_API_KEY': 'test-key-123'})
    def test_environment_override_flow(self):
        """Test workflow using environment variables"""
        # Step 1: Show config with environment override
        result = self.runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "***" in result.stdout  # API key should be masked but present
    
    @patch.dict(os.environ, {
        'NOVA_API_KEY': 'test-key-123',
        'NOVA_MODEL': 'gpt-4',
        'NOVA_PROVIDER': 'openai'
    })
    def test_multiple_env_overrides_flow(self):
        """Test workflow with multiple environment overrides"""
        result = self.runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "gpt-4" in result.stdout
        assert "openai" in result.stdout
        assert "***" in result.stdout  # API key masked
    
    def test_history_management_flow(self, temp_dir):
        """Test complete history management workflow"""
        history_dir = temp_dir / "test_history"
        history_dir.mkdir()
        
        # Create a test conversation file
        manager = HistoryManager(history_dir)
        test_conv = Conversation(id="test-123", title="Test Workflow")
        test_conv.add_message(MessageRole.USER, "Hello!")
        test_conv.add_message(MessageRole.ASSISTANT, "Hi there!")
        
        saved_path = manager.save_conversation(test_conv)
        assert saved_path.exists()
        
        # Test that we can list conversations (this would show in chat list)
        conversations = manager.list_conversations()
        assert len(conversations) == 1
        # Title extraction may include markdown formatting
        title = conversations[0][1]
        assert "Test Workflow" in title  # title should contain our text
    
    @patch('nova.cli.chat.ChatManager')
    def test_chat_session_management_flow(self, mock_chat_manager, temp_dir):
        """Test complete chat session management workflow"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager
        
        # Mock conversation list
        from datetime import datetime
        conversations = [
            (Path("20240101_120000_session1.md"), "First Session", datetime.now()),
            (Path("20240101_130000_session2.md"), "Second Session", datetime.now()),
        ]
        mock_manager.list_conversations.return_value = None
        mock_manager.start_interactive_chat.return_value = None
        
        # Step 1: List existing sessions
        result = self.runner.invoke(app, ["chat", "list"])
        assert result.exit_code == 0
        
        # Step 2: Start new session
        result = self.runner.invoke(app, ["chat", "start"])
        assert result.exit_code == 0
        
        # Step 3: Start named session
        result = self.runner.invoke(app, ["chat", "start", "my-session"])
        assert result.exit_code == 0
        
        # Verify calls
        assert mock_manager.start_interactive_chat.call_count == 2
        mock_manager.start_interactive_chat.assert_any_call(None)
        mock_manager.start_interactive_chat.assert_any_call("my-session")
    
    def test_error_recovery_flow(self, temp_dir):
        """Test error handling and recovery workflows"""
        # Step 1: Try to use non-existent config file
        bad_config = temp_dir / "nonexistent.yaml"
        result = self.runner.invoke(app, [
            "--config", str(bad_config), "config", "show"
        ])
        assert result.exit_code == 2  # Typer returns 2 for file not found errors
        # The error message will be from Typer about the file not existing
        
        # Step 2: Create valid config and retry
        result = self.runner.invoke(app, [
            "config", "init", "--output", str(bad_config)
        ])
        assert result.exit_code == 0
        
        # Step 3: Now it should work
        result = self.runner.invoke(app, [
            "--config", str(bad_config), "config", "show"
        ])
        assert result.exit_code == 0
        assert "Current Configuration:" in result.stdout
    
    def test_version_and_help_flow(self):
        """Test information commands workflow"""
        # Step 1: Check version
        result = self.runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Nova v" in result.stdout
        
        # Step 2: Check main help
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Nova - AI Research Assistant" in result.stdout
        
        # Step 3: Check subcommand help
        result = self.runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        
        result = self.runner.invoke(app, ["chat", "--help"])
        assert result.exit_code == 0
    
    def test_config_validation_flow(self, temp_dir):
        """Test configuration validation workflow"""
        # Create config with invalid data
        invalid_config = temp_dir / "invalid.yaml"
        with open(invalid_config, 'w') as f:
            f.write("""
ai_model:
  provider: "openai"
  model_name: "gpt-3.5-turbo"
  max_tokens: "not_a_number"  # Invalid: should be int
  temperature: 2.0  # Invalid: should be 0-1
""")
        
        # Should handle validation errors gracefully
        result = self.runner.invoke(app, [
            "--config", str(invalid_config), "config", "show"
        ])
        assert result.exit_code == 1
        # Should show validation error message
    
    @patch('nova.cli.chat.ChatManager')
    def test_concurrent_operations_flow(self, mock_chat_manager, temp_dir):
        """Test that operations don't interfere with each other"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager
        mock_manager.start_interactive_chat.return_value = None
        mock_manager.list_conversations.return_value = None
        
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Multiple operations in sequence
            results = []
            
            # Config operations
            results.append(self.runner.invoke(app, ["config", "init"]))
            results.append(self.runner.invoke(app, ["config", "show"]))
            
            # Chat operations
            results.append(self.runner.invoke(app, ["chat", "list"]))
            
            # All should succeed
            for result in results:
                assert result.exit_code == 0
                
        finally:
            os.chdir(original_cwd)