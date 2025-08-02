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
        assert "## Nova" in markdown
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

    def test_generate_content_based_title_programming(self, history_dir):
        """Test title generation for programming-related content"""
        manager = HistoryManager(history_dir)

        test_cases = [
            (
                "Can you help me implement a user authentication system?",
                "Implement a user authentication system",
            ),
            ("I need to fix this bug in my code", "Fix this bug in my code"),
            ("Please optimize my database queries", "Optimize my database queries"),
            (
                "How to create a REST API with Python?",
                "How to create a REST API with Python",
            ),
            (
                "What is object-oriented programming?",
                "What is object-oriented programming",
            ),
        ]

        for content, expected_start in test_cases:
            conversation = Conversation(id="test", title=None)
            conversation.add_message(MessageRole.USER, content)

            title = manager._generate_content_based_title(conversation)
            assert (
                title.startswith(expected_start)
                or expected_start.lower() in title.lower()
            )

    def test_generate_content_based_title_questions(self, history_dir):
        """Test title generation for question-based content"""
        manager = HistoryManager(history_dir)

        test_cases = [
            ("Why does my application crash on startup?", "Why"),
            ("When should I use async/await in Python?", "When to"),
            ("Where can I find documentation for this API?", "Where to"),
            ("Explain the difference between SQL and NoSQL", "Explain"),
        ]

        for content, expected_word in test_cases:
            conversation = Conversation(id="test", title=None)
            conversation.add_message(MessageRole.USER, content)

            title = manager._generate_content_based_title(conversation)
            assert expected_word.lower() in title.lower()

    def test_generate_content_based_title_fallback(self, history_dir):
        """Test title generation fallback for generic content"""
        manager = HistoryManager(history_dir)

        conversation = Conversation(id="test", title=None)
        conversation.add_message(
            MessageRole.USER, "Hi there, I hope you're having a great day!"
        )

        title = manager._generate_content_based_title(conversation)
        assert "Hi there" in title and "great day" in title

    def test_generate_content_based_title_no_messages(self, history_dir):
        """Test title generation when no messages exist"""
        manager = HistoryManager(history_dir)

        conversation = Conversation(id="test", title=None)

        title = manager._generate_content_based_title(conversation)
        assert title.startswith("Chat 2025")  # Should use timestamp format

    def test_generate_content_based_title_no_user_messages(self, history_dir):
        """Test title generation when no user messages exist"""
        manager = HistoryManager(history_dir)

        conversation = Conversation(id="test", title=None)
        conversation.add_message(MessageRole.ASSISTANT, "Hello! How can I help you?")

        title = manager._generate_content_based_title(conversation)
        assert title.startswith("Chat 2025")  # Should use timestamp format

    def test_generate_content_based_title_length_limit(self, history_dir):
        """Test that titles are limited to reasonable length"""
        manager = HistoryManager(history_dir)

        long_content = "Please help me implement a very comprehensive user authentication and authorization system with role-based access control, multi-factor authentication, password reset functionality, email verification, session management, and secure token handling for a large-scale enterprise application"

        conversation = Conversation(id="test", title=None)
        conversation.add_message(MessageRole.USER, long_content)

        title = manager._generate_content_based_title(conversation)
        assert len(title) <= 60
        assert title.endswith("...") if len(title) == 60 else True

    def test_save_conversation_auto_generates_title(self, history_dir):
        """Test that saving a conversation without title auto-generates one"""
        manager = HistoryManager(history_dir)

        conversation = Conversation(id="test", title=None)
        conversation.add_message(
            MessageRole.USER, "How to implement authentication in Flask?"
        )

        # Title should be None initially
        assert conversation.title is None

        # Save should generate a title
        manager.save_conversation(conversation)

        # Title should now be generated
        assert conversation.title is not None
        assert "authentication" in conversation.title.lower()
        assert "flask" in conversation.title.lower()

    def test_save_conversation_preserves_existing_title(self, history_dir):
        """Test that saving preserves existing title"""
        manager = HistoryManager(history_dir)

        conversation = Conversation(id="test", title="My Custom Title")
        conversation.add_message(MessageRole.USER, "This should not change the title")

        manager.save_conversation(conversation)

        # Title should remain unchanged
        assert conversation.title == "My Custom Title"

    def test_get_most_recent_conversation_empty(self, history_dir):
        """Test getting most recent conversation when no conversations exist"""
        manager = HistoryManager(history_dir)

        result = manager.get_most_recent_conversation()

        assert result is None

    def test_get_most_recent_conversation_single(self, history_dir):
        """Test getting most recent conversation with single conversation"""
        manager = HistoryManager(history_dir)

        conversation = Conversation(id="test-conv", title="Test Conversation")
        conversation.add_message(MessageRole.USER, "Hello")
        saved_path = manager.save_conversation(conversation)

        result = manager.get_most_recent_conversation()

        assert result is not None
        filepath, title, timestamp = result
        assert filepath == saved_path
        assert title == "Test Conversation"
        assert isinstance(timestamp, datetime)

    def test_get_most_recent_conversation_multiple(self, history_dir):
        """Test getting most recent conversation with multiple conversations"""
        import time

        manager = HistoryManager(history_dir)

        # Create first conversation
        conv1 = Conversation(id="conv-1", title="First Conversation")
        conv1.add_message(MessageRole.USER, "First message")
        manager.save_conversation(conv1)

        # Wait to ensure different timestamps (need at least 1 second for filename timestamp precision)
        time.sleep(1.1)

        # Create second conversation (more recent)
        conv2 = Conversation(id="conv-2", title="Second Conversation")
        conv2.add_message(MessageRole.USER, "Second message")
        saved_path2 = manager.save_conversation(conv2)

        result = manager.get_most_recent_conversation()

        assert result is not None
        filepath, title, timestamp = result
        assert filepath == saved_path2
        assert title == "Second Conversation"

    def test_markdown_headings_preserved_in_loaded_conversation(self, history_dir):
        """Test that markdown headings in messages are preserved when loading conversations"""
        manager = HistoryManager(history_dir)

        # Create conversation with markdown headings in assistant response
        conversation = Conversation(id="test-headings", title="Markdown Test")
        conversation.add_message(
            MessageRole.USER,
            "can you show some markdown headings and horizontal rules?",
        )

        assistant_content = """Here's an example of Markdown headings and horizontal rules:

# Heading 1

This is a basic heading.

## Subheading 1

This is a subheading. It's smaller than the main heading.

### Subheading 2

This is another subheading.

#### Subheading 3

And finally, here's an even smaller subheading.

---

This line is a horizontal rule. It separates the headings from the rest of the text."""

        conversation.add_message(MessageRole.ASSISTANT, assistant_content)

        # Save and load the conversation
        saved_path = manager.save_conversation(conversation)
        loaded_conv = manager.load_conversation(saved_path)

        # Verify the assistant message content is preserved with headings
        assert len(loaded_conv.messages) == 2
        loaded_assistant_message = loaded_conv.messages[1]
        assert loaded_assistant_message.role == MessageRole.ASSISTANT

        # Check that markdown headings are preserved
        assert "# Heading 1" in loaded_assistant_message.content
        assert "## Subheading 1" in loaded_assistant_message.content
        assert "### Subheading 2" in loaded_assistant_message.content
        assert "#### Subheading 3" in loaded_assistant_message.content
        assert "---" in loaded_assistant_message.content

        # Verify the full content structure is preserved
        assert "This is a basic heading." in loaded_assistant_message.content
        assert "horizontal rule" in loaded_assistant_message.content
