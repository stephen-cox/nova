"""Unit tests for Pydantic models"""

from datetime import datetime
from pathlib import Path

from nova.models.config import AIModelConfig, AIProfile, ChatConfig, NovaConfig
from nova.models.message import Conversation, Message, MessageRole


class TestMessage:
    """Test the Message model"""

    def test_create_message(self):
        """Test creating a basic message"""
        message = Message(role=MessageRole.USER, content="Hello, world!")

        assert message.role == MessageRole.USER
        assert message.content == "Hello, world!"
        assert isinstance(message.timestamp, datetime)
        assert message.metadata is None

    def test_message_with_metadata(self):
        """Test creating a message with metadata"""
        metadata = {"source": "test", "confidence": 0.95}
        message = Message(
            role=MessageRole.ASSISTANT, content="Test response", metadata=metadata
        )

        assert message.metadata == metadata

    def test_message_roles(self):
        """Test all message role types"""
        for role in [MessageRole.USER, MessageRole.ASSISTANT, MessageRole.SYSTEM]:
            message = Message(role=role, content="test")
            assert message.role == role

    def test_message_timestamp_auto(self):
        """Test that timestamp is automatically set"""
        before = datetime.now()
        message = Message(role=MessageRole.USER, content="test")
        after = datetime.now()

        assert before <= message.timestamp <= after


class TestConversation:
    """Test the Conversation model"""

    def test_create_empty_conversation(self):
        """Test creating an empty conversation"""
        conv = Conversation(id="test-123")

        assert conv.id == "test-123"
        assert conv.title is None
        assert len(conv.messages) == 0
        assert isinstance(conv.created_at, datetime)
        assert isinstance(conv.updated_at, datetime)

    def test_create_conversation_with_title(self):
        """Test creating a conversation with title"""
        conv = Conversation(id="test-123", title="Test Chat")

        assert conv.title == "Test Chat"

    def test_add_message(self):
        """Test adding messages to conversation"""
        conv = Conversation(id="test-123")

        message = conv.add_message(MessageRole.USER, "Hello!")

        assert len(conv.messages) == 1
        assert message.role == MessageRole.USER
        assert message.content == "Hello!"
        assert conv.messages[0] == message

    def test_add_message_with_metadata(self):
        """Test adding message with metadata"""
        conv = Conversation(id="test-123")
        metadata = {"test": True}

        message = conv.add_message(MessageRole.ASSISTANT, "Response", metadata=metadata)

        assert message.metadata == metadata

    def test_add_multiple_messages(self):
        """Test adding multiple messages"""
        conv = Conversation(id="test-123")

        conv.add_message(MessageRole.USER, "Hello!")
        conv.add_message(MessageRole.ASSISTANT, "Hi there!")
        conv.add_message(MessageRole.USER, "How are you?")

        assert len(conv.messages) == 3
        assert conv.messages[0].role == MessageRole.USER
        assert conv.messages[1].role == MessageRole.ASSISTANT
        assert conv.messages[2].role == MessageRole.USER

    def test_get_recent_messages_all(self):
        """Test getting all recent messages"""
        conv = Conversation(id="test-123")

        conv.add_message(MessageRole.USER, "Message 1")
        conv.add_message(MessageRole.ASSISTANT, "Message 2")
        conv.add_message(MessageRole.USER, "Message 3")

        recent = conv.get_recent_messages(10)
        assert len(recent) == 3
        assert recent[0].content == "Message 1"
        assert recent[2].content == "Message 3"

    def test_get_recent_messages_limited(self):
        """Test getting limited recent messages"""
        conv = Conversation(id="test-123")

        for i in range(5):
            conv.add_message(MessageRole.USER, f"Message {i + 1}")

        recent = conv.get_recent_messages(3)
        assert len(recent) == 3
        assert recent[0].content == "Message 3"  # Last 3 messages
        assert recent[1].content == "Message 4"
        assert recent[2].content == "Message 5"

    def test_get_recent_messages_zero_limit(self):
        """Test getting messages with zero limit returns all"""
        conv = Conversation(id="test-123")

        conv.add_message(MessageRole.USER, "Message 1")
        conv.add_message(MessageRole.USER, "Message 2")

        recent = conv.get_recent_messages(0)
        assert len(recent) == 2

    def test_updated_at_changes(self):
        """Test that updated_at changes when messages are added"""
        conv = Conversation(id="test-123")
        original_updated = conv.updated_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.001)

        conv.add_message(MessageRole.USER, "New message")

        assert conv.updated_at > original_updated


class TestMessageRole:
    """Test the MessageRole enum"""

    def test_role_values(self):
        """Test that role enum has correct string values"""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"

    def test_role_string_conversion(self):
        """Test converting role to string"""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"


class TestConfigModels:
    """Test configuration model validation"""

    def test_ai_model_config_defaults(self):
        """Test AIModelConfig default values"""
        config = AIModelConfig()

        assert config.provider == "openai"
        assert config.model_name == "gpt-3.5-turbo"
        assert config.api_key is None
        assert config.base_url is None
        assert config.max_tokens == 2000
        assert config.temperature == 0.7

    def test_ai_model_config_validation(self):
        """Test AIModelConfig field validation"""
        # Valid config
        config = AIModelConfig(
            provider="anthropic",
            model_name="claude-3",
            temperature=0.5,
            max_tokens=1000,
        )
        assert config.provider == "anthropic"
        assert config.temperature == 0.5

    def test_chat_config_defaults(self):
        """Test ChatConfig default values"""
        config = ChatConfig()

        assert config.history_dir == Path("~/.nova/history")
        assert config.max_history_length == 50
        assert config.auto_save is True

    def test_chat_config_custom(self):
        """Test ChatConfig with custom values"""
        config = ChatConfig(
            history_dir=Path("/custom/path"), max_history_length=100, auto_save=False
        )

        assert config.history_dir == Path("/custom/path")
        assert config.max_history_length == 100
        assert config.auto_save is False

    def test_nova_config_composition(self):
        """Test that NovaConfig properly composes sub-configs"""
        test_profile = AIProfile(
            name="test", provider="anthropic", model_name="claude-3-sonnet"
        )

        config = NovaConfig(
            profiles={"test": test_profile},
            active_profile="test",
            chat=ChatConfig(max_history_length=25),
        )

        active_ai_config = config.get_active_ai_config()
        assert active_ai_config.provider == "anthropic"
        assert config.chat.max_history_length == 25
        # Defaults should still be applied
        assert active_ai_config.model_name == "claude-3-sonnet"
        assert config.chat.auto_save is True

    def test_nova_config_defaults(self):
        """Test NovaConfig creates default sub-configs"""
        config = NovaConfig()

        # Should have default profile fallback behavior
        active_ai_config = config.get_active_ai_config()
        assert isinstance(config.chat, ChatConfig)
        assert active_ai_config.provider == "openai"
        assert config.chat.auto_save is True
