"""Tests for the ChatInputHandler class"""

from unittest.mock import patch

from prompt_toolkit.history import InMemoryHistory

from nova.core.input_handler import ChatInputHandler


class TestChatInputHandler:
    """Test cases for ChatInputHandler"""

    def setup_method(self):
        """Setup test fixtures"""
        self.handler = ChatInputHandler()

    def test_init(self):
        """Test ChatInputHandler initialization"""
        assert isinstance(self.handler.message_history, InMemoryHistory)
        assert self.handler.key_bindings is not None

    def test_clear_history(self):
        """Test clearing input history"""
        # Add some history
        self.handler.add_to_history("test message")
        assert len(self.handler.get_history()) == 1

        # Clear history
        self.handler.clear_history()
        assert len(self.handler.get_history()) == 0

    def test_add_to_history(self):
        """Test adding messages to history"""
        # Add valid message
        self.handler.add_to_history("test message")
        history = self.handler.get_history()
        assert len(history) == 1
        assert "test message" in history

        # Add empty message (should be ignored)
        self.handler.add_to_history("")
        self.handler.add_to_history("   ")
        assert len(self.handler.get_history()) == 1

    def test_get_history(self):
        """Test retrieving history"""
        messages = ["first", "second", "third"]
        for msg in messages:
            self.handler.add_to_history(msg)

        history = self.handler.get_history()
        assert len(history) == 3
        assert all(msg in history for msg in messages)

    @patch("nova.core.input_handler.prompt")
    def test_get_input_success(self, mock_prompt):
        """Test successful input retrieval"""
        mock_prompt.return_value = "user input"

        result = self.handler.get_input("Test> ")

        assert result == "user input"
        mock_prompt.assert_called_once()

        # Verify prompt was called with correct parameters
        call_args = mock_prompt.call_args
        assert call_args[0][0] == "Test> "
        assert call_args[1]["history"] == self.handler.message_history
        assert call_args[1]["key_bindings"] == self.handler.key_bindings
        assert call_args[1]["vi_mode"] is False
        assert call_args[1]["multiline"] is False

    @patch("nova.core.input_handler.prompt")
    def test_get_input_empty_input(self, mock_prompt):
        """Test handling empty input"""
        mock_prompt.return_value = "   "

        result = self.handler.get_input()

        assert result == ""
        # Empty input should not be added to history automatically

    @patch("nova.core.input_handler.prompt")
    def test_get_input_keyboard_interrupt(self, mock_prompt):
        """Test handling KeyboardInterrupt (Ctrl+C)"""
        mock_prompt.side_effect = KeyboardInterrupt()

        result = self.handler.get_input()

        assert result is None

    @patch("nova.core.input_handler.prompt")
    def test_get_input_eof_error(self, mock_prompt):
        """Test handling EOFError (Ctrl+D)"""
        mock_prompt.side_effect = EOFError()

        result = self.handler.get_input()

        assert result is None

    @patch("nova.core.input_handler.prompt")
    def test_get_input_adds_to_history(self, mock_prompt):
        """Test that non-empty input is added to history"""
        mock_prompt.return_value = "test input"

        self.handler.get_input()

        history = self.handler.get_history()
        assert len(history) == 1
        assert "test input" in history

    @patch("nova.core.input_handler.prompt")
    def test_get_input_strips_whitespace(self, mock_prompt):
        """Test that input whitespace is stripped"""
        mock_prompt.return_value = "  test input  "

        result = self.handler.get_input()

        assert result == "test input"
        # Verify the original (unstripped) input was added to history
        history = self.handler.get_history()
        assert "  test input  " in history

    def test_default_prompt_text(self):
        """Test default prompt text"""
        with patch("nova.core.input_handler.prompt") as mock_prompt:
            mock_prompt.return_value = "test"

            self.handler.get_input()

            call_args = mock_prompt.call_args
            assert call_args[0][0] == "You: "
