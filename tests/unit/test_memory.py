"""Unit tests for memory management functionality"""

from datetime import datetime
from unittest.mock import patch

import pytest

from nova.core.memory import MemoryManager
from nova.models.config import AIModelConfig
from nova.models.message import Conversation, ConversationSummary, Message, MessageRole


class TestMemoryManager:
    """Test the MemoryManager functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.ai_config = AIModelConfig(
            provider="openai", model_name="gpt-3.5-turbo", api_key="test-key"
        )
        self.memory_manager = MemoryManager(self.ai_config)

        # Create a test conversation
        self.conversation = Conversation(id="test-conv")

        # Add some test messages
        for i in range(5):
            self.conversation.add_message(
                MessageRole.USER, f"User message {i + 1} with some content"
            )
            self.conversation.add_message(
                MessageRole.ASSISTANT,
                f"Assistant response {i + 1} with helpful information",
            )

    def test_should_summarize_conversation_empty(self):
        """Test summarization decision for empty conversation"""
        empty_conv = Conversation(id="empty")
        assert not self.memory_manager.should_summarize_conversation(empty_conv)

    def test_should_summarize_conversation_enough_messages(self):
        """Test summarization decision when there are enough messages"""
        # Add more messages to reach threshold
        for i in range(25):
            self.conversation.add_message(MessageRole.USER, f"Extra message {i}")

        assert self.memory_manager.should_summarize_conversation(self.conversation)

    def test_should_not_summarize_with_recent_summary(self):
        """Test that we don't summarize if there's a recent summary"""
        # Add a summary
        self.conversation.add_summary(
            "Test summary",
            message_count=8,  # Most of the messages
            key_topics=["test"],
        )

        assert not self.memory_manager.should_summarize_conversation(self.conversation)

    @patch("nova.core.memory.generate_sync_response")
    def test_create_conversation_summary(self, mock_generate):
        """Test creating a conversation summary"""
        mock_generate.return_value = "This is a test summary of the conversation"

        summary = self.memory_manager.create_conversation_summary(self.conversation)

        assert isinstance(summary, ConversationSummary)
        assert summary.summary_text == "This is a test summary of the conversation"
        assert summary.message_count > 0
        assert len(summary.key_topics) > 0
        assert summary in self.conversation.summaries

    def test_create_summary_insufficient_messages(self):
        """Test that summary creation fails with too few messages"""
        short_conv = Conversation(id="short")
        short_conv.add_message(MessageRole.USER, "Hi")
        short_conv.add_message(MessageRole.ASSISTANT, "Hello")

        with pytest.raises(ValueError, match="Need at least 3 messages"):
            self.memory_manager.create_conversation_summary(short_conv)

    def test_analyze_message_importance_keywords(self):
        """Test message importance analysis with keywords"""
        # Message with importance keywords
        important_msg = Message(
            role=MessageRole.USER,
            content="This is important, please remember this key information for our task",
        )

        score = self.memory_manager.analyze_message_importance(
            important_msg, self.conversation
        )
        assert score > 1.0  # Base score + keyword boosts

    def test_analyze_message_importance_question(self):
        """Test message importance boost for questions"""
        question_msg = Message(
            role=MessageRole.USER,
            content="What is the best approach to solve this problem?",
        )

        score = self.memory_manager.analyze_message_importance(
            question_msg, self.conversation
        )
        assert score > 1.0  # Base score + question boost

    def test_analyze_message_importance_code(self):
        """Test message importance boost for code content"""
        code_msg = Message(
            role=MessageRole.ASSISTANT,
            content="Here's a function to help: ```python\ndef example():\n    return 'hello'\n```",
        )

        score = self.memory_manager.analyze_message_importance(
            code_msg, self.conversation
        )
        assert score > 1.0  # Base score + code boost

    def test_analyze_message_importance_recent(self):
        """Test message importance boost for recent messages"""
        recent_msg = Message(
            role=MessageRole.USER, content="Recent message", timestamp=datetime.now()
        )

        score = self.memory_manager.analyze_message_importance(
            recent_msg, self.conversation
        )
        assert score > 1.0  # Base score + recency boost

    def test_optimize_conversation_context(self):
        """Test context optimization"""
        result = self.memory_manager.optimize_conversation_context(self.conversation)

        assert "messages" in result
        assert "estimated_tokens" in result
        assert "message_count" in result
        assert "context_efficiency" in result

        assert isinstance(result["messages"], list)
        assert result["estimated_tokens"] > 0
        assert 0 <= result["context_efficiency"] <= 1

    def test_suggest_conversation_tags_empty(self):
        """Test tag suggestions for empty conversation"""
        empty_conv = Conversation(id="empty")
        tags = self.memory_manager.suggest_conversation_tags(empty_conv)
        assert tags == []

    def test_suggest_conversation_tags_technical(self):
        """Test tag suggestions for technical conversation"""
        tech_conv = Conversation(id="tech")
        tech_conv.add_message(MessageRole.USER, "I need help with Python programming")
        tech_conv.add_message(MessageRole.ASSISTANT, "Let's work on your Python code")
        tech_conv.add_message(MessageRole.USER, "I'm building a web API using Flask")

        tags = self.memory_manager.suggest_conversation_tags(tech_conv)
        assert "python" in tags
        assert "web" in tags or "api" in tags

    def test_cleanup_old_summaries(self):
        """Test cleanup of old summaries"""
        # Add multiple summaries
        for i in range(15):
            self.conversation.add_summary(
                f"Summary {i}", message_count=2, key_topics=[f"topic{i}"]
            )

        original_count = len(self.conversation.summaries)
        self.memory_manager.cleanup_old_summaries(self.conversation, max_summaries=5)

        assert len(self.conversation.summaries) == 5
        assert len(self.conversation.summaries) < original_count

        # Check that we kept the most recent ones
        assert "Summary 14" in self.conversation.summaries[-1].summary_text

    def test_get_memory_stats(self):
        """Test memory statistics generation"""
        stats = self.memory_manager.get_memory_stats(self.conversation)

        required_keys = [
            "message_count",
            "total_tokens",
            "duration",
            "summaries_count",
            "high_importance_messages",
            "recent_activity_24h",
            "context_efficiency",
            "estimated_context_tokens",
            "needs_summarization",
            "suggested_tags",
        ]

        for key in required_keys:
            assert key in stats

        assert stats["message_count"] == len(self.conversation.messages)
        assert isinstance(stats["high_importance_messages"], int)
        assert isinstance(stats["context_efficiency"], float)
        assert isinstance(stats["needs_summarization"], bool)
        assert isinstance(stats["suggested_tags"], list)

    def test_extract_key_topics(self):
        """Test key topic extraction from messages"""
        messages = [
            Message(
                role=MessageRole.USER,
                content="Let's discuss machine learning algorithms",
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="Neural networks are powerful for pattern recognition",
            ),
            Message(
                role=MessageRole.USER,
                content="What about deep learning and artificial intelligence?",
            ),
        ]

        topics = self.memory_manager._extract_key_topics(messages)

        assert isinstance(topics, list)
        assert len(topics) <= 10  # Limited to 10 topics

        # Should contain some relevant terms
        content_words = [
            "machine",
            "learning",
            "neural",
            "networks",
            "deep",
            "artificial",
            "intelligence",
        ]
        topic_words = [topic.lower() for topic in topics]

        # At least some overlap expected
        assert any(word in " ".join(topic_words) for word in content_words)


class TestConversationEnhancements:
    """Test the enhanced Conversation model functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.conversation = Conversation(id="test-enhanced")

    def test_add_summary(self):
        """Test adding summaries to conversation"""
        # Add some messages first
        for i in range(5):
            self.conversation.add_message(MessageRole.USER, f"Message {i}")

        summary = self.conversation.add_summary(
            "Test summary", message_count=3, key_topics=["test", "conversation"]
        )

        assert summary in self.conversation.summaries
        assert summary.summary_text == "Test summary"
        assert summary.message_count == 3
        assert "test" in summary.key_topics

    def test_get_context_for_ai_with_summaries(self):
        """Test AI context generation with summaries"""
        # Add messages and summaries
        for i in range(10):
            self.conversation.add_message(MessageRole.USER, f"Message {i}")

        self.conversation.add_summary(
            "Previous conversation about testing",
            message_count=5,
            key_topics=["testing"],
        )

        context = self.conversation.get_context_for_ai(
            token_limit=1000, include_summaries=True
        )

        assert isinstance(context, list)
        # Should include both messages and summary
        has_summary = any(
            "Previous conversation summary" in msg.get("content", "") for msg in context
        )
        assert has_summary

    def test_get_messages_by_importance(self):
        """Test filtering messages by importance"""
        # Add messages with different importance scores
        msg1 = self.conversation.add_message(MessageRole.USER, "Low importance")
        msg2 = self.conversation.add_message(MessageRole.USER, "High importance")
        msg3 = self.conversation.add_message(MessageRole.USER, "Medium importance")

        # Set importance scores
        msg1.importance_score = 0.5
        msg2.importance_score = 2.0
        msg3.importance_score = 1.5

        important_msgs = self.conversation.get_messages_by_importance(min_score=1.0)

        assert len(important_msgs) == 2  # msg2 and msg3
        assert msg1 not in important_msgs
        assert msg2 in important_msgs
        assert msg3 in important_msgs

    def test_tag_management(self):
        """Test conversation tag management"""
        # Add tags
        self.conversation.add_tag("programming")
        self.conversation.add_tag("python")
        self.conversation.add_tag("programming")  # Duplicate

        assert "programming" in self.conversation.tags
        assert "python" in self.conversation.tags
        assert len(self.conversation.tags) == 2  # No duplicates

        # Remove tag
        self.conversation.remove_tag("python")
        assert "python" not in self.conversation.tags
        assert "programming" in self.conversation.tags

    def test_update_message_importance(self):
        """Test updating message importance scores"""
        msg = self.conversation.add_message(MessageRole.USER, "Test message")
        original_score = msg.importance_score

        self.conversation.update_message_importance(0, 2.5)

        assert self.conversation.messages[0].importance_score == 2.5
        assert self.conversation.messages[0].importance_score != original_score

    def test_get_conversation_stats(self):
        """Test conversation statistics"""
        # Add some messages
        for i in range(3):
            msg = self.conversation.add_message(MessageRole.USER, f"Message {i}")
            msg.token_count = 10  # Set token count
            msg.importance_score = 1.5

        self.conversation.add_tag("test")
        self.conversation.add_summary("Test summary", 2, ["topic"])

        stats = self.conversation.get_conversation_stats()

        assert stats["message_count"] == 3
        assert stats["total_tokens"] == 30  # 3 messages * 10 tokens
        assert stats["summaries_count"] == 1
        assert "test" in stats["tags"]
        assert stats["avg_importance"] == 1.5
