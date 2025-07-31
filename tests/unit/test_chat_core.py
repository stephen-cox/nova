"""Unit tests for core chat functionality"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nova.core.ai_client import AIError
from nova.core.chat import ChatManager, ChatSession
from nova.models.config import AIProfile, ChatConfig, NovaConfig
from nova.models.message import Conversation, MessageRole


class TestChatSession:
    """Test ChatSession functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        test_profile = AIProfile(
            name="test",
            provider="openai",
            api_key="test-key",
            model_name="gpt-3.5-turbo",
            max_tokens=2000,
            temperature=0.7,
        )

        self.config = NovaConfig(
            profiles={"test": test_profile},
            active_profile="test",
            chat=ChatConfig(history_dir="~/.nova/test", max_history_length=10),
        )

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_create_new_session(self, mock_memory_manager, mock_history_manager):
        """Test creating a new chat session"""
        session = ChatSession(self.config)

        assert session.config == self.config
        assert session.conversation.id is not None
        assert len(session.conversation.id) == 8  # UUID truncated to 8 chars
        assert session.conversation.title is None
        assert len(session.conversation.messages) == 0

        mock_history_manager.assert_called_once_with(self.config.chat.history_dir)
        mock_memory_manager.assert_called_once_with(self.config.get_active_ai_config())

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_load_existing_session(self, mock_memory_manager, mock_history_manager):
        """Test loading existing chat session"""
        # Mock existing conversation
        existing_conv = Conversation(id="existing123")
        existing_conv.add_message(MessageRole.USER, "Previous message")

        mock_history_instance = mock_history_manager.return_value
        mock_history_instance.list_conversations.return_value = [
            (Path("test_existing123.md"), "Test Title", datetime.now())
        ]
        mock_history_instance.load_conversation.return_value = existing_conv

        session = ChatSession(self.config, conversation_id="existing123")

        assert session.conversation == existing_conv
        assert len(session.conversation.messages) == 1
        mock_history_instance.load_conversation.assert_called_once()

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_load_nonexistent_session_fallback(
        self, mock_memory_manager, mock_history_manager
    ):
        """Test fallback to new session when loading fails"""
        mock_history_instance = mock_history_manager.return_value
        mock_history_instance.list_conversations.return_value = []

        session = ChatSession(self.config, conversation_id="nonexistent")

        # Should create new conversation when existing one not found
        assert len(session.conversation.id) == 8
        assert len(session.conversation.messages) == 0

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_add_user_message(self, mock_memory_manager, mock_history_manager):
        """Test adding user message"""
        session = ChatSession(self.config)

        session.add_user_message("Hello there!")

        assert len(session.conversation.messages) == 1
        assert session.conversation.messages[0].role == MessageRole.USER
        assert session.conversation.messages[0].content == "Hello there!"

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_add_assistant_message(self, mock_memory_manager, mock_history_manager):
        """Test adding assistant message"""
        session = ChatSession(self.config)

        session.add_assistant_message("Hello back!")

        assert len(session.conversation.messages) == 1
        assert session.conversation.messages[0].role == MessageRole.ASSISTANT
        assert session.conversation.messages[0].content == "Hello back!"

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_add_system_message(self, mock_memory_manager, mock_history_manager):
        """Test adding system message"""
        session = ChatSession(self.config)

        session.add_system_message("System info")

        assert len(session.conversation.messages) == 1
        assert session.conversation.messages[0].role == MessageRole.SYSTEM
        assert session.conversation.messages[0].content == "System info"

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_auto_save_enabled(self, mock_memory_manager, mock_history_manager):
        """Test auto-save functionality when enabled"""
        self.config.chat.auto_save = True
        session = ChatSession(self.config)
        mock_history_instance = mock_history_manager.return_value

        session.add_user_message("Test message")

        mock_history_instance.save_conversation.assert_called_once()

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_auto_save_disabled(self, mock_memory_manager, mock_history_manager):
        """Test auto-save functionality when disabled"""
        self.config.chat.auto_save = False
        session = ChatSession(self.config)
        mock_history_instance = mock_history_manager.return_value

        session.add_user_message("Test message")

        mock_history_instance.save_conversation.assert_not_called()

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_save_conversation(self, mock_memory_manager, mock_history_manager):
        """Test manual conversation saving"""
        # Create config with auto-save disabled for this test
        config_no_autosave = self.config.model_copy()
        config_no_autosave.chat.auto_save = False
        session = ChatSession(config_no_autosave)
        # Add a message so the conversation is not empty
        session.add_user_message("Test message")
        mock_history_instance = mock_history_manager.return_value
        mock_history_instance.save_conversation.return_value = Path("saved.md")

        result = session.save_conversation()

        assert result == Path("saved.md")
        mock_history_instance.save_conversation.assert_called_once_with(
            session.conversation, None
        )

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_save_empty_conversation(self, mock_memory_manager, mock_history_manager):
        """Test that empty conversations are not saved"""
        config_no_autosave = self.config.model_copy()
        config_no_autosave.chat.auto_save = False
        session = ChatSession(config_no_autosave)
        mock_history_instance = mock_history_manager.return_value

        result = session.save_conversation()

        assert result is None
        mock_history_instance.save_conversation.assert_not_called()

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_get_context_messages(self, mock_memory_manager, mock_history_manager):
        """Test getting context messages through memory manager"""
        session = ChatSession(self.config)
        session.add_user_message("Hello")
        session.add_assistant_message("Hi there")

        # Mock memory manager optimization
        mock_memory_instance = mock_memory_manager.return_value
        mock_memory_instance.optimize_conversation_context.return_value = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
        }

        context = session.get_context_messages()

        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"
        mock_memory_instance.optimize_conversation_context.assert_called_once_with(
            session.conversation
        )

    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_info")
    def test_print_conversation_history(
        self, mock_print_info, mock_memory_manager, mock_history_manager
    ):
        """Test printing conversation history"""
        session = ChatSession(self.config)
        session.conversation.title = "Test Chat"
        session.add_user_message("Hello")

        with patch("nova.core.chat.print_message") as mock_print_message:
            session.print_conversation_history()

        # Verify info messages were printed
        assert mock_print_info.call_count >= 2
        mock_print_message.assert_called_once()


class TestChatManager:
    """Test ChatManager functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        test_profile = AIProfile(
            name="test",
            provider="openai",
            api_key="test-key",
            model_name="gpt-3.5-turbo",
            max_tokens=2000,
            temperature=0.7,
        )

        self.config = NovaConfig(
            profiles={"test": test_profile},
            active_profile="test",
            chat=ChatConfig(history_dir="~/.nova/test"),
        )

    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_init_with_valid_config(
        self, mock_memory_manager, mock_history_manager, mock_config_manager
    ):
        """Test ChatManager initialization with valid config"""
        mock_config_manager.load_config.return_value = self.config

        manager = ChatManager(Path("test_config.yaml"))

        assert manager.config == self.config
        mock_config_manager.load_config.assert_called_once_with(
            Path("test_config.yaml")
        )
        mock_history_manager.assert_called_once_with(self.config.chat.history_dir)
        mock_memory_manager.assert_called_once_with(self.config.get_active_ai_config())

    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_error")
    @patch("nova.core.chat.print_info")
    def test_init_with_config_error(
        self,
        mock_print_info,
        mock_print_error,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
    ):
        """Test ChatManager initialization with config error"""
        mock_config_manager.load_config.side_effect = Exception("Config error")
        mock_config_manager._load_default_config.return_value = self.config

        manager = ChatManager(Path("bad_config.yaml"))

        assert manager.config == self.config
        mock_print_error.assert_called_once_with("Configuration error: Config error")
        mock_print_info.assert_called_once_with("Using default configuration")
        mock_config_manager._load_default_config.assert_called_once()

    @patch("nova.core.chat.ChatManager._generate_ai_response")
    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_success")
    @patch("nova.core.chat.print_info")
    @patch("nova.core.chat.print_message")
    @patch("builtins.input")
    def test_interactive_chat_basic_flow(
        self,
        mock_input,
        mock_print_message,
        mock_print_info,
        mock_print_success,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
        mock_generate_ai,
    ):
        """Test basic interactive chat flow"""
        # Setup mocks
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_session.conversation.id = "test123"
        mock_chat_session.return_value = mock_session
        mock_generate_ai.return_value = "AI response"
        mock_input.side_effect = ["Hello", "/exit"]

        manager = ChatManager()
        manager.start_interactive_chat()

        # Verify basic flow
        mock_session.add_user_message.assert_called_once_with("Hello")
        mock_session.add_assistant_message.assert_called_once_with("AI response")
        mock_generate_ai.assert_called_once()
        mock_session.save_conversation.assert_called()

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("builtins.input")
    def test_interactive_chat_keyboard_interrupt(
        self,
        mock_input,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test handling keyboard interrupt in chat"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_chat_session.return_value = mock_session
        mock_input.side_effect = KeyboardInterrupt()

        manager = ChatManager()

        # Should not raise exception
        manager.start_interactive_chat()

        # Should still save conversation
        mock_session.save_conversation.assert_called()

    @patch("nova.core.chat.ChatManager._handle_command")
    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("builtins.input")
    def test_interactive_chat_command_handling(
        self,
        mock_input,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
        mock_handle_command,
    ):
        """Test command handling in interactive chat"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_chat_session.return_value = mock_session
        mock_input.side_effect = ["/help", "/exit"]

        manager = ChatManager()
        manager.start_interactive_chat()

        mock_handle_command.assert_called_once_with("/help", mock_session)

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_info")
    def test_handle_help_command(
        self,
        mock_print_info,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test /help command handling"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()

        manager = ChatManager()
        manager._handle_command("/help", mock_session)

        # Should print help information
        assert mock_print_info.call_count >= 1
        # Check that help text is printed
        help_calls = [call[0][0] for call in mock_print_info.call_args_list]
        assert any("Available commands:" in call for call in help_calls)

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_handle_history_command(
        self,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test /history command handling"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()

        manager = ChatManager()
        manager._handle_command("/history", mock_session)

        mock_session.print_conversation_history.assert_called_once()

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_success")
    def test_handle_save_command(
        self,
        mock_print_success,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test /save command handling"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_session.save_conversation.return_value = Path("saved.md")

        manager = ChatManager()
        manager._handle_command("/save", mock_session)

        mock_session.save_conversation.assert_called_once()
        mock_print_success.assert_called_once_with("Saved to: saved.md")

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_info")
    def test_handle_save_command_empty_conversation(
        self,
        mock_print_info,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test /save command handling for empty conversation"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_session.save_conversation.return_value = None  # Empty conversation

        manager = ChatManager()
        manager._handle_command("/save", mock_session)

        mock_session.save_conversation.assert_called_once()
        mock_print_info.assert_called_once_with(
            "No messages to save - conversation is empty"
        )

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_success")
    def test_handle_clear_command(
        self,
        mock_print_success,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test /clear command handling"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_session.conversation.messages = ["msg1", "msg2"]

        manager = ChatManager()
        manager._handle_command("/clear", mock_session)

        assert mock_session.conversation.messages == []
        mock_print_success.assert_called_once_with("Conversation history cleared")

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_success")
    def test_handle_title_command(
        self,
        mock_print_success,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test /title command handling"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()

        manager = ChatManager()
        manager._handle_command("/title My Test Chat", mock_session)

        assert mock_session.conversation.title == "My Test Chat"
        mock_print_success.assert_called_once_with("Title set to: My Test Chat")

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_success")
    def test_handle_tag_command(
        self,
        mock_print_success,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test /tag command handling"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()

        manager = ChatManager()
        manager._handle_command("/tag python", mock_session)

        mock_session.conversation.add_tag.assert_called_once_with("python")
        mock_print_success.assert_called_once_with("Added tag: python")

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_error")
    def test_handle_unknown_command(
        self,
        mock_print_error,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test handling unknown command"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()

        manager = ChatManager()
        manager._handle_command("/unknown", mock_session)

        mock_print_error.assert_called_once_with("Unknown command: /unknown")

    @patch("nova.core.chat.generate_sync_response")
    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_generate_ai_response_basic(
        self,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
        mock_generate,
    ):
        """Test basic AI response generation"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_session.get_context_messages.return_value = [
            {"role": "user", "content": "Hello"}
        ]
        mock_session.conversation.summaries = []
        mock_session.conversation.tags = []
        mock_generate.return_value = "AI response here"

        manager = ChatManager()
        response = manager._generate_ai_response(mock_session)

        assert response == "AI response here"
        mock_generate.assert_called_once()

        # Verify system message was added for OpenAI
        call_args = mock_generate.call_args
        messages = call_args[1]["messages"]
        assert len(messages) >= 2  # System message + user message
        assert messages[0]["role"] == "system"
        assert "Nova" in messages[0]["content"]

    @patch("nova.core.chat.generate_sync_response")
    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_generate_ai_response_with_context(
        self,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
        mock_generate,
    ):
        """Test AI response generation with summaries and tags"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_session.get_context_messages.return_value = [
            {"role": "user", "content": "Hello"}
        ]
        mock_session.conversation.summaries = [MagicMock()]  # Has summaries
        mock_session.conversation.tags = ["python", "programming"]
        mock_generate.return_value = "Context-aware response"

        manager = ChatManager()
        response = manager._generate_ai_response(mock_session)

        assert response == "Context-aware response"

        # Verify enhanced system message
        call_args = mock_generate.call_args
        messages = call_args[1]["messages"]
        system_content = messages[0]["content"]
        assert "conversation summaries" in system_content
        assert "python, programming" in system_content

    @patch("nova.core.chat.generate_sync_response")
    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    def test_generate_ai_response_error_handling(
        self,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
        mock_generate,
    ):
        """Test AI response generation error handling"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_session.get_context_messages.return_value = []
        mock_generate.side_effect = Exception("API Error")

        manager = ChatManager()

        with pytest.raises(AIError, match="Failed to generate response"):
            manager._generate_ai_response(mock_session)

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_info")
    def test_list_conversations(
        self,
        mock_print_info,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test listing conversations"""
        mock_config_manager.load_config.return_value = self.config
        mock_history_instance = mock_history_manager.return_value
        mock_history_instance.list_conversations.return_value = [
            (Path("chat1.md"), "Chat 1", datetime.now()),
            (Path("chat2.md"), "Chat 2", datetime.now()),
        ]

        manager = ChatManager()
        manager.list_conversations()

        # Should print conversation list
        assert mock_print_info.call_count >= 2
        info_calls = [call[0][0] for call in mock_print_info.call_args_list]
        assert any("Found 2 conversations" in call for call in info_calls)

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_info")
    def test_list_conversations_empty(
        self,
        mock_print_info,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test listing conversations when none exist"""
        mock_config_manager.load_config.return_value = self.config
        mock_history_instance = mock_history_manager.return_value
        mock_history_instance.list_conversations.return_value = []

        manager = ChatManager()
        manager.list_conversations()

        mock_print_info.assert_called_once_with("No saved conversations found")

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_error")
    @patch("nova.core.chat.print_info")
    def test_resume_last_conversation_no_history(
        self,
        mock_print_info,
        mock_print_error,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test resuming conversation when no history exists"""
        mock_config_manager.load_config.return_value = self.config
        mock_history_instance = mock_history_manager.return_value
        mock_history_instance.get_most_recent_conversation.return_value = None

        manager = ChatManager()
        manager.resume_last_conversation()

        mock_print_error.assert_called_once_with(
            "No saved conversations found to resume"
        )
        mock_print_info.assert_called_once_with(
            "Start a new chat with 'nova chat start'"
        )

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("nova.core.chat.print_success")
    @patch("nova.core.chat.print_info")
    def test_resume_last_conversation_with_history(
        self,
        mock_print_info,
        mock_print_success,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test resuming conversation when history exists"""
        from datetime import datetime
        from pathlib import Path

        mock_config_manager.load_config.return_value = self.config
        mock_history_instance = mock_history_manager.return_value

        # Mock most recent conversation
        test_path = Path("/fake/path/20250731_120000_test-session.md")
        test_title = "Test Chat Session"
        test_timestamp = datetime(2025, 7, 31, 12, 0, 0)
        mock_history_instance.get_most_recent_conversation.return_value = (
            test_path,
            test_title,
            test_timestamp,
        )

        manager = ChatManager()

        # Mock the start_interactive_chat method to avoid actually starting chat
        with patch.object(manager, "start_interactive_chat") as mock_start_chat:
            manager.resume_last_conversation()

        mock_print_success.assert_called_once_with("Resuming most recent conversation")
        mock_print_info.assert_any_call("Session: test-session")
        mock_print_info.assert_any_call("Title: Test Chat Session")
        mock_print_info.assert_any_call("Last updated: 2025-07-31 12:00")
        mock_start_chat.assert_called_once_with("test-session")

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("builtins.input")
    @patch("builtins.print")
    def test_interactive_chat_slash_exit_commands(
        self,
        mock_print,
        mock_input,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test that /exit and /quit commands work"""
        # Test /exit command
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_chat_session.return_value = mock_session
        mock_input.side_effect = ["/exit"]

        manager = ChatManager()
        manager.start_interactive_chat()

        # Should print goodbye and exit
        mock_print.assert_called_with("Goodbye!")

        # Test /quit command
        mock_print.reset_mock()
        mock_input.side_effect = ["/quit"]

        manager.start_interactive_chat()
        mock_print.assert_called_with("Goodbye!")

    @patch("nova.core.chat.ChatSession")
    @patch("nova.core.chat.config_manager")
    @patch("nova.core.chat.HistoryManager")
    @patch("nova.core.chat.MemoryManager")
    @patch("builtins.input")
    @patch("nova.core.chat.ChatManager._generate_ai_response")
    def test_non_slash_exit_treated_as_user_input(
        self,
        mock_generate_ai,
        mock_input,
        mock_memory_manager,
        mock_history_manager,
        mock_config_manager,
        mock_chat_session,
    ):
        """Test that non-slash 'exit' and 'quit' are treated as regular user input"""
        mock_config_manager.load_config.return_value = self.config
        mock_session = MagicMock()
        mock_session.conversation.id = "test123"
        mock_chat_session.return_value = mock_session
        mock_generate_ai.return_value = "AI response"
        mock_input.side_effect = ["exit", "/exit"]

        manager = ChatManager()
        manager.start_interactive_chat()

        # 'exit' without slash should be treated as user input
        mock_session.add_user_message.assert_called_with("exit")
        mock_generate_ai.assert_called_once()
        mock_session.add_assistant_message.assert_called_once_with("AI response")
