"""Tests for web_search tool usage in chat scenarios"""

from unittest.mock import AsyncMock, patch

import pytest

from nova.models.config import NovaConfig, SearchConfig
from nova.tools.built_in.web_search import web_search


@pytest.fixture
def mock_config():
    """Mock configuration for tests"""
    from nova.models.config import AIProfile

    search_config = SearchConfig(
        enabled=True,
        default_provider="duckduckgo",
        max_results=5,
        use_ai_answers=True,
        default_enhancement="fast",
        enable_conversation_context=True,
        default_technical_level="intermediate",
        default_timeframe="any",
        performance_mode=True,
        enhancement_timeout=30.0,
        request_timeout=10.0,
    )

    ai_profile = AIProfile(
        name="default",
        provider="openai",
        model_name="gpt-4",
        api_key="test-key",
        temperature=0.7,
        max_tokens=2000,
        description="Default test profile",
    )

    config = NovaConfig(
        search=search_config, profiles={"default": ai_profile}, active_profile="default"
    )

    return config


@pytest.fixture
def mock_search_response():
    """Mock search response"""
    return {
        "query": "weather forecast Oxford UK",
        "provider": "duckduckgo",
        "results": [
            {
                "title": "Oxford Weather Forecast - Met Office",
                "url": "https://www.metoffice.gov.uk/weather/forecast/oxford",
                "snippet": "Latest weather forecast for Oxford, UK including temperature, precipitation, and wind conditions.",
                "source": "metoffice.gov.uk",
                "content": "Detailed weather information for Oxford showing tomorrow's forecast with temperatures around 15°C.",
                "extraction_success": True,
            },
            {
                "title": "BBC Weather - Oxford",
                "url": "https://www.bbc.co.uk/weather/oxford",
                "snippet": "Current weather and 5-day forecast for Oxford, UK from BBC Weather.",
                "source": "bbc.co.uk",
                "content": "Oxford weather forecast showing sunny conditions with light winds.",
                "extraction_success": True,
            },
        ],
        "total_results": 2,
        "search_time_ms": 1250,
        "enhancement_details": {
            "mode": "fast",
            "processing_time_ms": 150,
            "context_used": True,
            "enhanced_queries": [
                {
                    "query": "Oxford UK weather forecast tomorrow",
                    "priority": 1,
                    "rationale": "Enhanced with location specificity and time relevance",
                }
            ],
        },
    }


class TestWebSearchChatIntegration:
    """Test web_search tool in chat-like scenarios"""

    @pytest.mark.asyncio
    async def test_weather_query_chat_scenario(self, mock_config, mock_search_response):
        """Test weather query like in a chat conversation"""
        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=mock_config
            ),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai,
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock AI client
            mock_ai_client = AsyncMock()
            mock_ai_client.close = AsyncMock()
            mock_create_ai.return_value = mock_ai_client

            # Mock search manager context manager
            mock_manager_instance = AsyncMock()
            mock_manager_instance.enhanced_search = AsyncMock(
                return_value=mock_search_response
            )
            mock_search_manager.return_value.__aenter__ = AsyncMock(
                return_value=mock_manager_instance
            )
            mock_search_manager.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute web search as it would be called in chat
            result = await web_search(
                query="What will the weather be like tomorrow?",
                max_results=3,
                timeframe="recent",
            )

            # Verify results
            assert result is not None
            assert result["query"] == "weather forecast Oxford UK"
            assert len(result["results"]) == 2
            assert (
                result["results"][0]["title"] == "Oxford Weather Forecast - Met Office"
            )
            assert "enhancement" in result

            # Verify AI client was properly closed
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_technical_query_chat_scenario(self, mock_config):
        """Test technical query with enhanced search"""
        mock_tech_response = {
            "query": "Python async programming best practices",
            "provider": "duckduckgo",
            "results": [
                {
                    "title": "Python Async Programming Guide",
                    "url": "https://docs.python.org/3/library/asyncio.html",
                    "snippet": "Official documentation for Python asyncio programming.",
                    "source": "python.org",
                    "content": "Comprehensive guide to asynchronous programming in Python using asyncio.",
                    "extraction_success": True,
                }
            ],
            "total_results": 1,
            "search_time_ms": 980,
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=mock_config
            ),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai,
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock AI client
            mock_ai_client = AsyncMock()
            mock_ai_client.close = AsyncMock()
            mock_create_ai.return_value = mock_ai_client

            # Mock search manager
            mock_manager_instance = AsyncMock()
            mock_manager_instance.enhanced_search = AsyncMock(
                return_value=mock_tech_response
            )
            mock_search_manager.return_value.__aenter__ = AsyncMock(
                return_value=mock_manager_instance
            )
            mock_search_manager.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute search
            result = await web_search(
                query="How do I use async/await in Python?",
                enhancement="fast",
                technical_level="expert",
                max_results=5,
            )

            # Verify results
            assert result["query"] == "Python async programming best practices"
            assert len(result["results"]) == 1
            assert "python.org" in result["results"][0]["source"]

            # Verify AI client cleanup
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_context_usage(self, mock_config, mock_search_response):
        """Test web search with conversation context like in real chat"""
        conversation_context = """
        User: I'm planning a trip to Oxford next week.
        Assistant: That sounds great! Oxford is a beautiful city with lots to see.
        User: What will the weather be like tomorrow?
        """

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=mock_config
            ),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai,
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock AI client
            mock_ai_client = AsyncMock()
            mock_ai_client.close = AsyncMock()
            mock_create_ai.return_value = mock_ai_client

            # Mock search manager
            mock_manager_instance = AsyncMock()
            mock_manager_instance.enhanced_search = AsyncMock(
                return_value=mock_search_response
            )
            mock_search_manager.return_value.__aenter__ = AsyncMock(
                return_value=mock_manager_instance
            )
            mock_search_manager.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute search with conversation context
            result = await web_search(
                query="weather tomorrow",
                conversation_context=conversation_context,
                enhancement="auto",
                timeframe="recent",
            )

            # Verify context was used
            mock_manager_instance.enhanced_search.assert_called_once()
            call_args = mock_manager_instance.enhanced_search.call_args
            assert call_args[1]["conversation_context"] == conversation_context

            # Verify AI client cleanup
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_without_ai_client(self, mock_config, mock_search_response):
        """Test search when AI client creation fails (fallback scenario)"""
        # Modify config to disable AI answers
        mock_config.search.use_ai_answers = False

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=mock_config
            ),
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock search manager
            mock_manager_instance = AsyncMock()
            mock_manager_instance.enhanced_search = AsyncMock(
                return_value=mock_search_response
            )
            mock_search_manager.return_value.__aenter__ = AsyncMock(
                return_value=mock_manager_instance
            )
            mock_search_manager.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute search without AI client
            result = await web_search(
                query="latest news about technology", enhancement="disabled"
            )

            # Verify search still works
            assert result is not None
            assert len(result["results"]) == 2

            # Verify search manager was called with no AI client
            mock_search_manager.assert_called_with(
                {"search": mock_config.search.model_dump()}, None
            )

    @pytest.mark.asyncio
    async def test_multiple_search_calls_in_session(
        self, mock_config, mock_search_response
    ):
        """Test multiple search calls in same chat session"""
        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=mock_config
            ),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai,
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock AI client
            mock_ai_client = AsyncMock()
            mock_ai_client.close = AsyncMock()
            mock_create_ai.return_value = mock_ai_client

            # Mock search manager
            mock_manager_instance = AsyncMock()
            mock_manager_instance.enhanced_search = AsyncMock(
                return_value=mock_search_response
            )
            mock_search_manager.return_value.__aenter__ = AsyncMock(
                return_value=mock_manager_instance
            )
            mock_search_manager.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute multiple searches
            queries = [
                "weather forecast Oxford",
                "best restaurants in Oxford",
                "Oxford University admission",
            ]

            results = []
            for query in queries:
                result = await web_search(query=query, max_results=3)
                results.append(result)

            # Verify all searches completed
            assert len(results) == 3
            for result in results:
                assert result is not None
                assert "results" in result

            # Verify AI client was created and closed for each search
            assert mock_create_ai.call_count == 3
            assert mock_ai_client.close.call_count == 3

    @pytest.mark.asyncio
    async def test_search_error_handling_in_chat(self, mock_config):
        """Test error handling when search fails in chat context"""
        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=mock_config
            ),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai,
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock AI client
            mock_ai_client = AsyncMock()
            mock_ai_client.close = AsyncMock()
            mock_create_ai.return_value = mock_ai_client

            # Mock search manager to raise exception
            mock_search_manager.return_value.__aenter__.side_effect = Exception(
                "Network error"
            )

            # Execute search that should fail gracefully
            result = await web_search(query="test query")

            # Verify fallback response
            assert result is not None
            assert result["provider"] == "fallback"
            assert "error" in result
            assert "Network error" in result["error"]

            # Verify AI client was still closed even on error
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_uses_config_provider(self, mock_config, mock_search_response):
        """Test that search uses provider from config"""
        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=mock_config
            ),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai,
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock AI client
            mock_ai_client = AsyncMock()
            mock_ai_client.close = AsyncMock()
            mock_create_ai.return_value = mock_ai_client

            # Mock search manager
            mock_manager_instance = AsyncMock()
            mock_manager_instance.enhanced_search = AsyncMock(
                return_value=mock_search_response
            )
            mock_search_manager.return_value.__aenter__ = AsyncMock(
                return_value=mock_manager_instance
            )
            mock_search_manager.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute search - should use config provider
            result = await web_search(query="search query", max_results=3)

            # Verify search completed with config provider
            assert result is not None
            mock_manager_instance.enhanced_search.assert_called_once()
            call_args = mock_manager_instance.enhanced_search.call_args
            assert call_args[1]["provider"] == "duckduckgo"  # From mock_config

            # Verify cleanup
            mock_ai_client.close.assert_called_once()
