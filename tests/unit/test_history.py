"""Unit tests for chat history management"""

from datetime import datetime
from pathlib import Path

import pytest

from nova.core.history import HistoryError, HistoryManager
from nova.models.message import Conversation, MessageRole


class TestHistoryManager:
    """Test the HistoryManager class"""

    def test_init_creates_directory(self, temp_dir):
        """Test that HistoryManager creates history directory"""
        history_dir = temp_dir / "new_history"
        manager = HistoryManager(history_dir)

        assert manager.history_dir == history_dir
        assert history_dir.exists()

    def test_save_conversation(self, history_dir, sample_conversation):
        """Test saving a conversation to markdown"""
        manager = HistoryManager(history_dir)

        saved_path = manager.save_conversation(sample_conversation)

        assert saved_path.exists()
        assert saved_path.suffix == ".md"
        assert saved_path.parent == history_dir

        # Check filename format
        assert "test-conv-123" in saved_path.name

    def test_save_conversation_custom_filename(self, history_dir, sample_conversation):
        """Test saving conversation with custom filename"""
        manager = HistoryManager(history_dir)

        saved_path = manager.save_conversation(sample_conversation, "custom-name")

        assert saved_path.name == "custom-name.md"

    def test_save_conversation_adds_md_extension(
        self, history_dir, sample_conversation
    ):
        """Test that .md extension is added if missing"""
        manager = HistoryManager(history_dir)

        saved_path = manager.save_conversation(sample_conversation, "no-extension")

        assert saved_path.name == "no-extension.md"

    def test_load_conversation(self, history_dir, sample_conversation):
        """Test loading a conversation from markdown"""
        manager = HistoryManager(history_dir)

        # Save first
        saved_path = manager.save_conversation(sample_conversation)

        # Load back
        loaded_conv = manager.load_conversation(saved_path)

        assert loaded_conv.id == sample_conversation.id
        assert loaded_conv.title == sample_conversation.title
        assert len(loaded_conv.messages) == len(sample_conversation.messages)

        # Check first message
        assert loaded_conv.messages[0].role == MessageRole.USER
        assert loaded_conv.messages[0].content == "Hello, how are you?"

    def test_load_conversation_file_not_found(self, history_dir):
        """Test loading non-existent conversation file"""
        manager = HistoryManager(history_dir)
        nonexistent_file = history_dir / "nonexistent.md"

        with pytest.raises(HistoryError, match="History file not found"):
            manager.load_conversation(nonexistent_file)

    def test_load_conversation_from_fixture(self, history_dir):
        """Test loading conversation from fixture file"""
        manager = HistoryManager(history_dir)

        # Copy fixture to history dir
        fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_history.md"
        test_file = history_dir / "fixture_test.md"

        with open(fixture_path) as src, open(test_file, "w") as dst:
            dst.write(src.read())

        loaded_conv = manager.load_conversation(test_file)

        assert loaded_conv.id == "fixture-test-123"
        assert loaded_conv.title == "Test Chat Session"
        assert len(loaded_conv.messages) >= 4  # Should have multiple messages

    def test_list_conversations_empty(self, history_dir):
        """Test listing conversations in empty directory"""
        manager = HistoryManager(history_dir)

        conversations = manager.list_conversations()

        assert conversations == []

    def test_list_conversations_with_files(self, history_dir, sample_conversation):
        """Test listing conversations with saved files"""
        manager = HistoryManager(history_dir)

        # Save a few conversations
        conv1 = sample_conversation
        conv1.id = "conv-1"
        manager.save_conversation(conv1)

        conv2 = Conversation(id="conv-2", title="Second Chat")
        conv2.add_message(MessageRole.USER, "Another conversation")
        manager.save_conversation(conv2)

        conversations = manager.list_conversations()

        assert len(conversations) == 2

        # Each item should be (filepath, title, timestamp)
        for filepath, title, timestamp in conversations:
            assert isinstance(filepath, Path)
            assert isinstance(title, str)
            assert isinstance(timestamp, datetime)
            assert filepath.suffix == ".md"

    def test_conversation_to_markdown(self, history_dir, sample_conversation):
        """Test converting conversation to markdown format"""
        manager = HistoryManager(history_dir)

        markdown = manager._conversation_to_markdown(sample_conversation)

        # Check metadata
        assert "<!-- Nova Chat History -->" in markdown
        assert f"<!-- Conversation ID: {sample_conversation.id} -->" in markdown
        assert f"<!-- Title: {sample_conversation.title} -->" in markdown

        # Check title
        assert f"# {sample_conversation.title}" in markdown

        # Check messages
        assert "## User" in markdown
        assert "## Assistant" in markdown
        assert "Hello, how are you?" in markdown
        assert "I'm doing well, thank you!" in markdown

    def test_markdown_to_conversation(self, history_dir, sample_markdown):
        """Test parsing markdown back to conversation"""
        manager = HistoryManager(history_dir)

        conversation = manager._markdown_to_conversation(sample_markdown, "test-id")

        assert conversation.id == "test-conv-123"  # From metadata
        assert conversation.title == "Test Conversation"
        assert len(conversation.messages) >= 2

        # Check first message
        first_msg = conversation.messages[0]
        assert first_msg.role == MessageRole.USER
        assert "Hello, how are you?" in first_msg.content

    def test_roundtrip_conversion(self, history_dir, sample_conversation):
        """Test that save/load preserves conversation data"""
        manager = HistoryManager(history_dir)

        # Save and load
        saved_path = manager.save_conversation(sample_conversation)
        loaded_conv = manager.load_conversation(saved_path)

        # Compare key properties
        assert loaded_conv.id == sample_conversation.id
        assert loaded_conv.title == sample_conversation.title
        assert len(loaded_conv.messages) == len(sample_conversation.messages)

        # Compare message content
        for original, loaded in zip(
            sample_conversation.messages, loaded_conv.messages, strict=False
        ):
            assert original.role == loaded.role
            assert original.content == loaded.content

    def test_save_conversation_error_handling(self, temp_dir):
        """Test error handling when save fails"""
        # Create manager with read-only directory to force error
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only

        manager = HistoryManager(readonly_dir)
        conversation = Conversation(id="test")

        try:
            with pytest.raises(HistoryError, match="Error saving conversation"):
                manager.save_conversation(conversation)
        finally:
            # Clean up - make writable again
            readonly_dir.chmod(0o755)

    def test_filename_sanitization(self, history_dir):
        """Test that unsafe characters in conversation ID are sanitized"""
        manager = HistoryManager(history_dir)

        conversation = Conversation(id="unsafe/chars\\in:name")
        conversation.add_message(MessageRole.USER, "Test")

        saved_path = manager.save_conversation(conversation)

        # Filename should be sanitized
        assert "/" not in saved_path.name
        assert "\\" not in saved_path.name
        assert ":" not in saved_path.name
