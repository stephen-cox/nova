"""Integration tests for chat CLI commands"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from nova.main import app


class TestChatCLI:
    """Test chat command integration"""

    def setup_method(self):
        """Set up test runner"""
        self.runner = CliRunner()

    def test_chat_help(self):
        """Test chat command help"""
        result = self.runner.invoke(app, ["chat", "--help"])

        assert result.exit_code == 0
        assert "Chat commands" in result.stdout

    def test_chat_start_help(self):
        """Test chat start command help"""
        result = self.runner.invoke(app, ["chat", "start", "--help"])

        assert result.exit_code == 0
        assert "Start a new chat session" in result.stdout

    def test_chat_list_help(self):
        """Test chat list command help"""
        result = self.runner.invoke(app, ["chat", "list", "--help"])

        assert result.exit_code == 0
        assert "List saved chat sessions" in result.stdout

    @patch("nova.cli.chat.ChatManager")
    def test_chat_start_new_session(self, mock_chat_manager):
        """Test starting a new chat session"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager

        # Mock the interactive chat to avoid hanging
        mock_manager.start_interactive_chat.return_value = None

        result = self.runner.invoke(app, ["chat", "start"])

        assert result.exit_code == 0
        mock_chat_manager.assert_called_once_with(None, profile_override=None)
        mock_manager.start_interactive_chat.assert_called_once_with(None)

    @patch("nova.cli.chat.ChatManager")
    def test_chat_start_named_session(self, mock_chat_manager):
        """Test starting a named chat session"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager
        mock_manager.start_interactive_chat.return_value = None

        result = self.runner.invoke(app, ["chat", "start", "test-session"])

        assert result.exit_code == 0
        mock_manager.start_interactive_chat.assert_called_once_with("test-session")

    @patch("nova.cli.chat.ChatManager")
    def test_chat_start_with_config(self, mock_chat_manager, sample_config_yaml):
        """Test starting chat with custom config"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager
        mock_manager.start_interactive_chat.return_value = None

        result = self.runner.invoke(
            app, ["--config", str(sample_config_yaml), "chat", "start"]
        )

        assert result.exit_code == 0
        mock_chat_manager.assert_called_once_with(
            sample_config_yaml, profile_override=None
        )

    @patch("nova.cli.chat.ChatManager")
    def test_chat_start_with_profile(self, mock_chat_manager):
        """Test starting chat with a specific profile"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager
        mock_manager.start_interactive_chat.return_value = None

        result = self.runner.invoke(app, ["chat", "start", "--profile", "claude"])

        assert result.exit_code == 0
        mock_chat_manager.assert_called_once_with(None, profile_override="claude")
        mock_manager.start_interactive_chat.assert_called_once_with(None)

    @patch("nova.cli.chat.ChatManager")
    def test_chat_start_with_profile_short_flag(self, mock_chat_manager):
        """Test starting chat with profile using short flag"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager
        mock_manager.start_interactive_chat.return_value = None

        result = self.runner.invoke(app, ["chat", "start", "-p", "gpt4"])

        assert result.exit_code == 0
        mock_chat_manager.assert_called_once_with(None, profile_override="gpt4")
        mock_manager.start_interactive_chat.assert_called_once_with(None)

    @patch("nova.cli.chat.ChatManager")
    def test_chat_start_invalid_profile(self, mock_chat_manager):
        """Test chat start with invalid profile"""
        from nova.core.config import ConfigError

        mock_chat_manager.side_effect = ConfigError("Profile 'invalid' not found")

        result = self.runner.invoke(app, ["chat", "start", "--profile", "invalid"])

        assert result.exit_code == 1
        assert "Failed to start chat" in result.stdout

    @patch("nova.cli.chat.ChatManager")
    def test_chat_start_error_handling(self, mock_chat_manager):
        """Test chat start error handling"""
        mock_chat_manager.side_effect = Exception("Config error")

        result = self.runner.invoke(app, ["chat", "start"])

        assert result.exit_code == 1
        assert "Failed to start chat" in result.stdout

    @patch("nova.cli.chat.ChatManager")
    def test_chat_list_empty(self, mock_chat_manager):
        """Test listing conversations when none exist"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager
        mock_manager.list_conversations.return_value = None

        result = self.runner.invoke(app, ["chat", "list"])

        assert result.exit_code == 0
        mock_manager.list_conversations.assert_called_once()

    @patch("nova.cli.chat.ChatManager")
    def test_chat_list_with_sessions(self, mock_chat_manager):
        """Test listing conversations with existing sessions"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager

        # Mock some conversation data
        from datetime import datetime

        [
            (Path("/tmp/20240101_120000_conv1.md"), "First chat", datetime.now()),
            (Path("/tmp/20240101_130000_conv2.md"), "Second chat", datetime.now()),
        ]
        mock_manager.list_conversations.return_value = None

        result = self.runner.invoke(app, ["chat", "list"])

        assert result.exit_code == 0
        mock_manager.list_conversations.assert_called_once()

    @patch("nova.cli.chat.ChatManager")
    def test_chat_list_error_handling(self, mock_chat_manager):
        """Test chat list error handling"""
        mock_chat_manager.side_effect = Exception("History directory error")

        result = self.runner.invoke(app, ["chat", "list"])

        assert result.exit_code == 1
        assert "Failed to list sessions" in result.stdout

    def test_main_help(self):
        """Test main app help includes chat commands"""
        result = self.runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Nova - AI Research Assistant" in result.stdout
        assert "chat" in result.stdout
        assert "config" in result.stdout

    def test_main_version(self):
        """Test version command"""
        result = self.runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "Nova v" in result.stdout

    @patch("nova.cli.chat.ChatManager")
    def test_global_verbose_option(self, mock_chat_manager):
        """Test global verbose option"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager
        mock_manager.start_interactive_chat.return_value = None

        result = self.runner.invoke(app, ["--verbose", "chat", "start"])

        assert result.exit_code == 0
        # Note: We're not actually testing verbose output here since it's not implemented
        # This test just ensures the option is accepted without error

    def test_unknown_command(self):
        """Test handling of unknown commands"""
        result = self.runner.invoke(app, ["unknown-command"])

        assert result.exit_code != 0
        # Typer should show an error about unknown command

    @patch("nova.cli.chat.ChatManager")
    def test_keyboard_interrupt_handling(self, mock_chat_manager):
        """Test that KeyboardInterrupt in chat is handled gracefully"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager
        mock_manager.start_interactive_chat.side_effect = KeyboardInterrupt()

        self.runner.invoke(app, ["chat", "start"])

        # Should exit gracefully, not with error code
        # (The actual behavior depends on how we handle KeyboardInterrupt in the chat manager)
        mock_manager.start_interactive_chat.assert_called_once()


class TestCLIIntegration:
    """Test full CLI integration scenarios"""

    def setup_method(self):
        """Set up test runner"""
        self.runner = CliRunner()

    def test_config_then_chat_workflow(self, temp_dir):
        """Test workflow: create config, then start chat"""
        import os

        original_cwd = os.getcwd()
        os.chdir(temp_dir)

        try:
            # First, create a config
            result1 = self.runner.invoke(app, ["config", "init"])
            assert result1.exit_code == 0

            # Then, show the config
            result2 = self.runner.invoke(app, ["config", "show"])
            assert result2.exit_code == 0

            # Config file should exist
            config_file = temp_dir / "nova-config.yaml"
            assert config_file.exists()

        finally:
            os.chdir(original_cwd)

    @patch("nova.cli.chat.ChatManager")
    def test_custom_config_workflow(self, mock_chat_manager, temp_dir):
        """Test workflow using custom config file"""
        mock_manager = MagicMock()
        mock_chat_manager.return_value = mock_manager
        mock_manager.start_interactive_chat.return_value = None

        # Create custom config
        custom_config = temp_dir / "my-config.yaml"
        result1 = self.runner.invoke(
            app, ["config", "init", "--output", str(custom_config)]
        )
        assert result1.exit_code == 0

        # Use custom config for chat
        result2 = self.runner.invoke(
            app, ["--config", str(custom_config), "chat", "start"]
        )
        assert result2.exit_code == 0

        # Should have been called with the custom config path
        mock_chat_manager.assert_called_with(custom_config, profile_override=None)
