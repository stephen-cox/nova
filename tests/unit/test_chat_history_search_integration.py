"""Tests for chat history integration with search functionality"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nova.models.message import MessageRole
from nova.search.models import SearchEnhancementMode
from nova.tools.built_in.web_search import web_search


class TestChatHistorySearchIntegration:
    """Test chat history integration with web search"""

    @pytest.mark.asyncio
    async def test_web_search_with_conversation_context(self):
        """Test web search uses conversation context when available"""

        with patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.enhanced_search = AsyncMock(
                return_value={
                    "query": "weather tomorrow",
                    "provider": "duckduckgo",
                    "results": [
                        {
                            "title": "Oxford Weather Forecast",
                            "url": "https://weather.com/oxford",
                            "snippet": "Weather in Oxford tomorrow",
                            "source": "weather.com",
                        }
                    ],
                    "total_results": 1,
                    "search_time_ms": 100,
                    "enhancement_details": {
                        "mode": SearchEnhancementMode.FAST,
                        "processing_time_ms": 50,
                        "context_used": True,
                        "enhanced_queries": [
                            {
                                "query": "weather forecast tomorrow Oxford UK",
                                "priority": 1,
                                "rationale": "Added location from conversation context",
                            }
                        ],
                    },
                }
            )
            mock_manager.close = AsyncMock()
            # Setup async context manager
            mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_manager.__aexit__ = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager

            with patch("nova.core.config.config_manager") as mock_config:
                mock_config_obj = MagicMock()
                mock_config_obj.search.default_enhancement = "fast"
                mock_config_obj.search.default_provider = "duckduckgo"
                mock_config_obj.search.max_results = 5
                mock_config_obj.search.default_timeframe = "any"
                mock_config_obj.search.default_technical_level = "intermediate"
                mock_config_obj.search.use_ai_answers = True  # Enable AI answers
                mock_config_obj.search.enhancement_timeout = 30.0
                mock_config_obj.get_active_ai_config.return_value = MagicMock(
                    provider="openai"
                )
                mock_config_obj.search.model_dump.return_value = {}
                mock_config.load_config.return_value = mock_config_obj

                with patch("nova.core.ai_client.create_ai_client") as mock_ai_client:
                    mock_ai_client.return_value = MagicMock()

                    # Test with meaningful conversation context (>50 characters)
                    conversation_context = """Recent conversation context (2 messages):
User: I am visiting Oxford tomorrow for a walking tour
Assistant: That sounds wonderful! Oxford is beautiful for walking tours."""

                    await web_search(
                        query="weather tomorrow",
                        conversation_context=conversation_context,
                        enhancement="fast",
                    )

                    # Verify the search was called with context
                    mock_manager.enhanced_search.assert_called_once()
                    call_args = mock_manager.enhanced_search.call_args
                    assert (
                        call_args.kwargs["conversation_context"] == conversation_context
                    )

                    # Verify AI client was created because of meaningful context (>50 chars)
                    mock_ai_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_web_search_no_ai_client_for_minimal_context(self):
        """Test web search doesn't create AI client for minimal context"""

        with patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.enhanced_search = AsyncMock(
                return_value={
                    "query": "test query",
                    "provider": "duckduckgo",
                    "results": [],
                    "total_results": 0,
                    "search_time_ms": 100,
                }
            )
            mock_manager.close = AsyncMock()
            # Setup async context manager
            mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_manager.__aexit__ = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager

            with patch("nova.core.config.config_manager") as mock_config:
                mock_config_obj = MagicMock()
                mock_config_obj.search.default_enhancement = "fast"
                mock_config_obj.search.default_provider = "duckduckgo"
                mock_config_obj.search.max_results = 5
                mock_config_obj.search.default_timeframe = "any"
                mock_config_obj.search.default_technical_level = "intermediate"
                mock_config_obj.search.use_ai_answers = True  # Enable AI answers
                mock_config_obj.search.enhancement_timeout = 30.0
                mock_config_obj.get_active_ai_config.return_value = MagicMock(
                    provider="openai"
                )
                mock_config_obj.search.model_dump.return_value = {}
                mock_config.load_config.return_value = mock_config_obj

                with patch("nova.core.ai_client.create_ai_client") as mock_ai_client:
                    mock_ai_client.return_value = MagicMock()

                    # Test with minimal context (< 50 characters)
                    conversation_context = "Short context"  # Only 13 characters

                    await web_search(
                        query="test query",
                        conversation_context=conversation_context,
                        enhancement="fast",
                    )

                    # Verify AI client was NOT created for minimal context (< 50 chars)
                    mock_ai_client.assert_not_called()

                    # But context was still passed to search manager
                    mock_manager.enhanced_search.assert_called_once()
                    call_args = mock_manager.enhanced_search.call_args
                    assert (
                        call_args.kwargs["conversation_context"] == conversation_context
                    )

    @pytest.mark.asyncio
    async def test_web_search_disabled_enhancement_no_ai_client(self):
        """Test web search doesn't create AI client when enhancement is disabled"""

        with patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.enhanced_search = AsyncMock(
                return_value={
                    "query": "test query",
                    "provider": "duckduckgo",
                    "results": [],
                    "total_results": 0,
                    "search_time_ms": 100,
                }
            )
            mock_manager.close = AsyncMock()
            # Setup async context manager
            mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_manager.__aexit__ = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager

            with patch("nova.core.config.config_manager") as mock_config:
                mock_config_obj = MagicMock()
                mock_config_obj.search.default_enhancement = "disabled"
                mock_config_obj.search.default_provider = "duckduckgo"
                mock_config_obj.search.max_results = 5
                mock_config_obj.search.default_timeframe = "any"
                mock_config_obj.search.default_technical_level = "intermediate"
                mock_config_obj.search.use_ai_answers = True  # Enable AI answers
                mock_config_obj.search.enhancement_timeout = 30.0
                mock_config_obj.get_active_ai_config.return_value = MagicMock(
                    provider="openai"
                )
                mock_config_obj.search.model_dump.return_value = {}
                mock_config.load_config.return_value = mock_config_obj

                with patch("nova.core.ai_client.create_ai_client") as mock_ai_client:
                    mock_ai_client.return_value = MagicMock()

                    # Test with meaningful context but disabled enhancement
                    conversation_context = """Recent conversation context (2 messages):
User: I am visiting Oxford tomorrow for a walking tour
Assistant: That sounds wonderful! Oxford is beautiful for walking tours."""

                    await web_search(
                        query="test query",
                        conversation_context=conversation_context,
                        enhancement="disabled",
                    )

                    # Verify AI client was NOT created when enhancement is disabled
                    mock_ai_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_web_search_ai_client_creation_failure(self):
        """Test web search handles AI client creation failure gracefully"""

        with patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.enhanced_search = AsyncMock(
                return_value={
                    "query": "test query",
                    "provider": "duckduckgo",
                    "results": [],
                    "total_results": 0,
                    "search_time_ms": 100,
                }
            )
            mock_manager.close = AsyncMock()
            # Setup async context manager
            mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_manager.__aexit__ = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager

            with patch("nova.core.config.config_manager") as mock_config:
                mock_config_obj = MagicMock()
                mock_config_obj.search.default_enhancement = "fast"
                mock_config_obj.search.default_provider = "duckduckgo"
                mock_config_obj.search.max_results = 5
                mock_config_obj.search.default_timeframe = "any"
                mock_config_obj.search.default_technical_level = "intermediate"
                mock_config_obj.search.use_ai_answers = True  # Enable AI answers
                mock_config_obj.search.enhancement_timeout = 30.0
                mock_config_obj.get_active_ai_config.return_value = MagicMock(
                    provider="openai"
                )
                mock_config_obj.search.model_dump.return_value = {}
                mock_config.load_config.return_value = mock_config_obj

                with patch("nova.core.ai_client.create_ai_client") as mock_ai_client:
                    # Simulate AI client creation failure
                    mock_ai_client.side_effect = Exception("API key not found")

                    conversation_context = """Recent conversation context (2 messages):
User: I am visiting Oxford tomorrow
Assistant: That sounds wonderful!"""

                    # Should not raise exception, should continue with search
                    result = await web_search(
                        query="test query",
                        conversation_context=conversation_context,
                        enhancement="fast",
                    )

                    # Verify search still completed successfully
                    assert result["query"] == "test query"
                    assert result["provider"] == "duckduckgo"

                    # Verify search manager was called with None as ai_client
                    mock_manager_class.assert_called_once_with(
                        {"search": {}},
                        None,  # ai_client should be None due to creation failure
                    )

    @pytest.mark.asyncio
    async def test_context_threshold_boundary(self):
        """Test the 50-character threshold for meaningful context"""

        with patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.enhanced_search = AsyncMock(
                return_value={
                    "query": "test query",
                    "provider": "duckduckgo",
                    "results": [],
                    "total_results": 0,
                    "search_time_ms": 100,
                }
            )
            mock_manager.close = AsyncMock()
            # Setup async context manager
            mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
            mock_manager.__aexit__ = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager

            with patch("nova.core.config.config_manager") as mock_config:
                mock_config_obj = MagicMock()
                mock_config_obj.search.default_enhancement = "fast"
                mock_config_obj.search.default_provider = "duckduckgo"
                mock_config_obj.search.max_results = 5
                mock_config_obj.search.default_timeframe = "any"
                mock_config_obj.search.default_technical_level = "intermediate"
                mock_config_obj.search.use_ai_answers = True  # Enable AI answers
                mock_config_obj.search.enhancement_timeout = 30.0
                mock_config_obj.get_active_ai_config.return_value = MagicMock(
                    provider="openai"
                )
                mock_config_obj.search.model_dump.return_value = {}
                mock_config.load_config.return_value = mock_config_obj

                with patch("nova.core.ai_client.create_ai_client") as mock_ai_client:
                    mock_ai_client.return_value = MagicMock()

                    # Test with exactly 49 characters (should NOT create AI client)
                    context_49_chars = "User: I am in Oxford\nAssistant: That's nice!"
                    assert len(context_49_chars) == 44  # Actual length

                    # Make it exactly 49 characters
                    context_49_chars = (
                        context_49_chars + "12345"
                    )  # Add 5 chars to make it 49
                    assert len(context_49_chars) == 49

                    await web_search(
                        query="test query",
                        conversation_context=context_49_chars,
                        enhancement="fast",
                    )
                    mock_ai_client.assert_not_called()
                    mock_ai_client.reset_mock()

                    # Test with 51 characters (should create AI client)
                    context_51_chars = (
                        context_49_chars + "51"
                    )  # Add 2 more chars to make it 51
                    assert len(context_51_chars) == 51

                    await web_search(
                        query="test query",
                        conversation_context=context_51_chars,
                        enhancement="fast",
                    )
                    mock_ai_client.assert_called_once()


class TestConversationContextExtraction:
    """Test conversation context extraction from chat history"""

    def test_get_search_context_basic(self):
        """Test basic conversation context extraction"""
        from nova.core.chat import ChatManager

        with patch("nova.core.config.config_manager.load_config") as mock_config:
            # Mock configuration to enable context
            mock_config_obj = MagicMock()
            mock_config_obj.search.enable_conversation_context = True
            mock_config_obj.search.context_messages_count = 3
            mock_config.return_value = mock_config_obj

            manager = ChatManager()

            # Create a mock session with conversation
            session = MagicMock()
            conversation = MagicMock()

            # Create test messages
            messages = [
                MagicMock(role=MessageRole.USER, content="Hello! I'm in Oxford today."),
                MagicMock(
                    role=MessageRole.ASSISTANT,
                    content="That's wonderful! Oxford is a beautiful city.",
                ),
                MagicMock(
                    role=MessageRole.USER,
                    content="Yes, I'm planning to visit the colleges.",
                ),
            ]
            conversation.messages = messages
            session.conversation = conversation

            # Test context extraction
            context = manager._get_search_context(session)

            assert context is not None
            assert len(context) > 0
            assert "Oxford" in context
            assert "Recent conversation context" in context
            assert "User:" in context
            assert "Assistant:" in context

    def test_get_search_context_disabled(self):
        """Test context extraction when disabled in config"""
        from nova.core.chat import ChatManager

        with patch("nova.core.config.config_manager.load_config") as mock_config:
            # Mock configuration to disable context
            mock_config_obj = MagicMock()
            mock_config_obj.search.enable_conversation_context = False
            mock_config.return_value = mock_config_obj

            manager = ChatManager()
            session = MagicMock()

            context = manager._get_search_context(session)

            assert context == ""

    def test_get_search_context_no_messages(self):
        """Test context extraction with no messages"""
        from nova.core.chat import ChatManager

        with patch("nova.core.config.config_manager.load_config") as mock_config:
            mock_config_obj = MagicMock()
            mock_config_obj.search.enable_conversation_context = True
            mock_config_obj.search.context_messages_count = 3
            mock_config.return_value = mock_config_obj

            manager = ChatManager()
            session = MagicMock()
            conversation = MagicMock()
            conversation.messages = []
            session.conversation = conversation

            context = manager._get_search_context(session)

            assert context == ""

    def test_get_search_context_filters_commands(self):
        """Test context extraction filters out slash commands"""
        from nova.core.chat import ChatManager

        with patch("nova.core.config.config_manager.load_config") as mock_config:
            mock_config_obj = MagicMock()
            mock_config_obj.search.enable_conversation_context = True
            mock_config_obj.search.context_messages_count = 5
            mock_config.return_value = mock_config_obj

            manager = ChatManager()
            session = MagicMock()
            conversation = MagicMock()

            # Mix of regular messages and commands
            messages = [
                MagicMock(role=MessageRole.USER, content="I'm visiting Oxford"),
                MagicMock(role=MessageRole.USER, content="/help"),  # Should be filtered
                MagicMock(
                    role=MessageRole.USER, content="/search weather"
                ),  # Should be filtered
                MagicMock(role=MessageRole.ASSISTANT, content="Oxford is beautiful!"),
                MagicMock(
                    role=MessageRole.USER, content="Yes, can't wait to see the colleges"
                ),
            ]
            conversation.messages = messages
            session.conversation = conversation

            context = manager._get_search_context(session)

            assert "/help" not in context
            assert "/search" not in context
            assert "Oxford" in context
            assert "colleges" in context

    def test_get_search_context_truncation(self):
        """Test context extraction truncates long messages"""
        from nova.core.chat import ChatManager

        with patch("nova.core.config.config_manager.load_config") as mock_config:
            mock_config_obj = MagicMock()
            mock_config_obj.search.enable_conversation_context = True
            mock_config_obj.search.context_messages_count = 1
            mock_config.return_value = mock_config_obj

            manager = ChatManager()
            session = MagicMock()
            conversation = MagicMock()

            # Very long message that should be truncated
            long_content = (
                "I'm visiting Oxford tomorrow. " + "This is a very long message. " * 20
            )
            assert (
                len(long_content) > 150
            )  # Ensure it's longer than the truncation limit

            messages = [
                MagicMock(role=MessageRole.USER, content=long_content),
            ]
            conversation.messages = messages
            session.conversation = conversation

            context = manager._get_search_context(session)

            # Should be truncated but still contain key information
            assert len(context) < len(long_content)
            assert "Oxford" in context
            assert ("..." in context) or (context.endswith("."))  # Should end properly

    def test_get_search_context_message_limit(self):
        """Test context extraction respects message count limit"""
        from nova.core.chat import ChatManager

        with patch("nova.core.config.config_manager.load_config") as mock_config:
            mock_config_obj = MagicMock()
            mock_config_obj.search.enable_conversation_context = True
            mock_config_obj.search.context_messages_count = 2  # Limit to 2 messages
            mock_config.return_value = mock_config_obj

            manager = ChatManager()
            session = MagicMock()
            conversation = MagicMock()

            # Create 5 messages, but only last 2 should be included
            messages = [
                MagicMock(role=MessageRole.USER, content="First message"),
                MagicMock(role=MessageRole.USER, content="Second message"),
                MagicMock(role=MessageRole.USER, content="Third message"),
                MagicMock(role=MessageRole.USER, content="Fourth message with Oxford"),
                MagicMock(role=MessageRole.USER, content="Fifth message with colleges"),
            ]
            conversation.messages = messages
            session.conversation = conversation

            context = manager._get_search_context(session)

            # Should only contain the last 2 messages
            assert "First message" not in context
            assert "Second message" not in context
            assert "Third message" not in context
            assert "Oxford" in context
            assert "colleges" in context
