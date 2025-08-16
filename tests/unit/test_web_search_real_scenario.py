"""Tests for real web_search tool scenarios that were failing"""

from unittest.mock import AsyncMock, patch

import pytest

from nova.models.config import AIProfile, NovaConfig, SearchConfig
from nova.tools.built_in.web_search import web_search


@pytest.fixture
def real_config():
    """Configuration that mimics real usage"""
    search_config = SearchConfig(
        enabled=True,
        default_provider="google",
        max_results=3,
        use_ai_answers=True,
        default_enhancement="fast",
        enable_conversation_context=True,
        default_technical_level="intermediate",
        default_timeframe="recent",
        performance_mode=True,
        enhancement_timeout=30.0,
        request_timeout=10.0,
    )

    ai_profile = AIProfile(
        name="default",
        provider="anthropic",
        model_name="claude-3-5-sonnet-20241022",
        api_key="test-anthropic-key",
        temperature=0.7,
        max_tokens=2000,
        description="Default Anthropic profile",
    )

    config = NovaConfig(
        search=search_config, profiles={"default": ai_profile}, active_profile="default"
    )

    return config


class TestWebSearchRealScenarios:
    """Test web_search tool in real failure scenarios"""

    @pytest.mark.asyncio
    async def test_weather_query_real_scenario(self, real_config):
        """Test the exact weather query that was failing"""
        mock_search_response = {
            "query": "Oxford UK weather forecast for tomorrow",
            "provider": "google",
            "results": [
                {
                    "title": "Tomorrow's Weather in Oxford, UK | Weather Underground",
                    "url": "https://www.wunderground.com/weather/gb/oxford/tomorrow",
                    "snippet": "Tomorrow's detailed weather forecast for Oxford, UK including temperature, humidity, and precipitation.",
                    "source": "wunderground.com",
                    "content": "Tomorrow in Oxford: Partly cloudy with temperatures reaching 16°C. Light winds from the southwest.",
                    "extraction_success": True,
                },
                {
                    "title": "Oxford Weather Forecast | BBC Weather",
                    "url": "https://www.bbc.co.uk/weather/2640729",
                    "snippet": "Latest weather conditions and forecasts for Oxford, UK from the BBC.",
                    "source": "bbc.co.uk",
                    "content": "Oxford weather tomorrow: Sunny spells with occasional cloud cover. High of 17°C.",
                    "extraction_success": True,
                },
                {
                    "title": "Oxford Weather | Met Office",
                    "url": "https://www.metoffice.gov.uk/weather/forecast/gcp4q17s0",
                    "snippet": "Official UK weather forecast for Oxford from the Met Office.",
                    "source": "metoffice.gov.uk",
                    "content": "Tomorrow's forecast for Oxford shows mild conditions with light rain possible in the afternoon.",
                    "extraction_success": True,
                },
            ],
            "total_results": 3,
            "search_time_ms": 1850,
            "enhancement_details": {
                "mode": "fast",
                "processing_time_ms": 180,
                "context_used": False,
                "enhanced_queries": [
                    {
                        "query": "Oxford UK weather forecast tomorrow",
                        "priority": 1,
                        "rationale": "Enhanced query with location specificity and time relevance",
                    }
                ],
            },
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=real_config
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

            # Execute the exact query that was failing
            result = await web_search(
                query="Oxford UK weather forecast for tomorrow",
                max_results="3",  # Note: string input as it comes from chat
                timeframe="recent",
            )

            # Verify results
            assert result is not None
            assert result["query"] == "Oxford UK weather forecast for tomorrow"
            assert result["provider"] == "google"
            assert len(result["results"]) == 3
            assert "enhancement" in result

            # Verify AI client was properly closed
            mock_ai_client.close.assert_called_once()

            # Verify search manager was called with correct parameters
            mock_manager_instance.enhanced_search.assert_called_once()
            call_args = mock_manager_instance.enhanced_search.call_args
            assert call_args[1]["query"] == "Oxford UK weather forecast for tomorrow"
            assert call_args[1]["provider"] == "google"
            assert call_args[1]["max_results"] == 3  # Should be converted to int
            # Check memory_constraints object contains timeframe
            memory_constraints = call_args[1]["memory_constraints"]
            assert memory_constraints.timeframe == "recent"

    @pytest.mark.asyncio
    async def test_ai_client_creation_failure(self, real_config):
        """Test scenario where AI client creation fails"""
        mock_search_response = {
            "query": "test query",
            "provider": "duckduckgo",
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "snippet": "Test snippet",
                    "source": "example.com",
                    "extraction_success": False,
                }
            ],
            "total_results": 1,
            "search_time_ms": 500,
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=real_config
            ),
            patch(
                "nova.core.ai_client.create_ai_client",
                side_effect=Exception("AI client creation failed"),
            ),
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock search manager (should work without AI client)
            mock_manager_instance = AsyncMock()
            mock_manager_instance.enhanced_search = AsyncMock(
                return_value=mock_search_response
            )
            mock_search_manager.return_value.__aenter__ = AsyncMock(
                return_value=mock_manager_instance
            )
            mock_search_manager.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute search when AI client fails to create
            result = await web_search(query="test query")

            # Verify search still works without AI enhancement
            assert result is not None
            assert result["query"] == "test query"
            assert len(result["results"]) == 1

            # Verify search manager was called with None AI client
            mock_search_manager.assert_called_with(
                {"search": real_config.search.model_dump()}, None
            )

    @pytest.mark.asyncio
    async def test_string_parameter_conversion(self, real_config):
        """Test that string parameters from chat are properly converted"""
        mock_search_response = {
            "query": "programming tutorial",
            "provider": "duckduckgo",
            "results": [],
            "total_results": 0,
            "search_time_ms": 100,
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=real_config
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

            # Execute search with string parameters (as they come from chat)
            result = await web_search(
                query="programming tutorial",
                max_results="5",  # String input
                enhancement="fast",  # String input
                timeframe="recent",  # String input
                technical_level="beginner",  # String input
            )

            # Verify search completed
            assert result is not None

            # Verify parameters were properly converted
            mock_manager_instance.enhanced_search.assert_called_once()
            call_args = mock_manager_instance.enhanced_search.call_args
            assert call_args[1]["max_results"] == 5  # Should be converted to int

            # Verify AI client cleanup
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_manager_timeout_with_cleanup(self, real_config):
        """Test that AI client is cleaned up even when search times out"""
        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=real_config
            ),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai,
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock AI client
            mock_ai_client = AsyncMock()
            mock_ai_client.close = AsyncMock()
            mock_create_ai.return_value = mock_ai_client

            # Mock search manager to raise timeout
            mock_search_manager.return_value.__aenter__.side_effect = Exception(
                "Search timeout"
            )

            # Execute search that should timeout
            result = await web_search(query="test query")

            # Verify fallback response is returned
            assert result is not None
            assert result["provider"] == "fallback"
            assert "error" in result
            assert "Search timeout" in result["error"]

            # Verify AI client was still closed despite the error
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_context_processing(self, real_config):
        """Test conversation context handling in real scenarios"""
        conversation_context = """
        User: I'm visiting the UK next week for work.
        Assistant: That's exciting! Which city will you be visiting?
        User: Oxford. What will the weather be like tomorrow?
        """

        mock_search_response = {
            "query": "Oxford UK weather forecast tomorrow",
            "provider": "google",
            "results": [],
            "total_results": 0,
            "search_time_ms": 200,
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=real_config
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
                query="weather tomorrow", conversation_context=conversation_context
            )

            # Verify search completed
            assert result is not None

            # Verify conversation context was passed correctly
            mock_manager_instance.enhanced_search.assert_called_once()
            call_args = mock_manager_instance.enhanced_search.call_args
            assert call_args[1]["conversation_context"] == conversation_context

            # Verify AI client cleanup
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_max_results_handling(self, real_config):
        """Test handling of invalid max_results parameter"""
        mock_search_response = {
            "query": "test query",
            "provider": "duckduckgo",
            "results": [],
            "total_results": 0,
            "search_time_ms": 100,
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=real_config
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

            # Execute search with invalid max_results
            result = await web_search(
                query="test query",
                max_results="invalid",  # Should be handled gracefully
            )

            # Verify search completed with fallback max_results
            assert result is not None

            # Verify max_results was set to default from config
            mock_manager_instance.enhanced_search.assert_called_once()
            call_args = mock_manager_instance.enhanced_search.call_args
            assert call_args[1]["max_results"] == real_config.search.max_results

            # Verify AI client cleanup
            mock_ai_client.close.assert_called_once()
