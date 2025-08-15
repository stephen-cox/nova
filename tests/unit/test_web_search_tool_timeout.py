"""Tests for web_search tool timeout handling"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nova.tools.built_in.web_search import web_search


class TestWebSearchToolTimeout:
    """Test web_search tool timeout behavior"""

    @pytest.mark.asyncio
    async def test_web_search_enhancement_timeout(self):
        """Test web_search when query enhancement times out"""

        with (
            patch("nova.core.config.config_manager") as mock_config_manager,
            patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class,
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai_client,
        ):
            # Setup config
            mock_config = MagicMock()
            mock_config.search.default_enhancement = "fast"
            mock_config.search.default_provider = "duckduckgo"
            mock_config.search.max_results = 5
            mock_config.search.default_timeframe = "any"
            mock_config.search.default_technical_level = "intermediate"
            mock_config.search.use_ai_answers = True
            mock_config.search.enhancement_timeout = 30.0  # Add numeric timeout
            mock_config.get_active_ai_config.return_value = {}
            mock_config_manager.load_config.return_value = mock_config

            # Setup AI client
            mock_ai_client = MagicMock()
            mock_create_ai_client.return_value = mock_ai_client

            # Setup search manager that times out
            mock_manager = AsyncMock()
            mock_manager_class.return_value.__aenter__.return_value = mock_manager
            mock_manager_class.return_value.__aexit__.return_value = None

            # Make enhanced_search timeout after 45+ seconds (enhancement_timeout + buffer)
            async def timeout_search(*args, **kwargs):
                await asyncio.sleep(
                    50
                )  # Longer than the tool's 45s timeout (30s enhancement + 15s buffer)
                return {"results": []}

            mock_manager.enhanced_search.side_effect = timeout_search

            # This should now handle the timeout gracefully instead of raising TimeoutError
            result = await web_search("test query")

            # Should return error result instead of timing out
            assert "error" in result
            assert "timed out" in result["error"].lower()
            assert result["results"] == []

    @pytest.mark.asyncio
    async def test_web_search_handles_internal_timeout_gracefully(self):
        """Test web_search handles internal timeouts and provides fallback"""

        with (
            patch("nova.core.config.config_manager") as mock_config_manager,
            patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class,
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai_client,
        ):
            # Setup config
            mock_config = MagicMock()
            mock_config.search.default_enhancement = "fast"
            mock_config.search.default_provider = "duckduckgo"
            mock_config.search.max_results = 5
            mock_config.search.default_timeframe = "any"
            mock_config.search.default_technical_level = "intermediate"
            mock_config.search.use_ai_answers = True
            mock_config.search.enhancement_timeout = 30.0  # Add numeric timeout
            mock_config.get_active_ai_config.return_value = {}
            mock_config_manager.load_config.return_value = mock_config

            # Setup AI client
            mock_ai_client = MagicMock()
            mock_create_ai_client.return_value = mock_ai_client

            # Setup search manager
            mock_manager = AsyncMock()
            mock_fallback_manager = AsyncMock()

            # First manager times out, second provides fallback
            mock_manager_class.side_effect = [
                mock_manager,  # First manager for main search
                mock_fallback_manager,  # Second manager for fallback
            ]
            mock_manager.__aenter__.return_value = mock_manager
            mock_manager.__aexit__.return_value = None
            mock_fallback_manager.__aenter__.return_value = mock_fallback_manager
            mock_fallback_manager.__aexit__.return_value = None

            # First search times out
            mock_manager.enhanced_search.side_effect = TimeoutError()

            # Fallback search succeeds
            mock_fallback_manager.enhanced_search.return_value = {
                "query": "test query",
                "results": [
                    {
                        "title": "Fallback Result",
                        "url": "https://example.com",
                        "snippet": "Fallback snippet",
                        "source": "example.com",
                    }
                ],
                "total_results": 1,
                "search_time_ms": 1000,
                "provider": "duckduckgo",
            }

            # This should handle the timeout gracefully and return fallback results
            result = await web_search("test query")

            assert "results" in result
            assert len(result["results"]) == 1
            assert result["results"][0]["title"] == "Fallback Result"

    @pytest.mark.asyncio
    async def test_web_search_fallback_also_fails(self):
        """Test web_search when both main search and fallback fail"""

        with (
            patch("nova.core.config.config_manager") as mock_config_manager,
            patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class,
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai_client,
        ):
            # Setup config
            mock_config = MagicMock()
            mock_config.search.default_enhancement = "fast"
            mock_config.search.default_provider = "duckduckgo"
            mock_config.search.max_results = 5
            mock_config.search.default_timeframe = "any"
            mock_config.search.default_technical_level = "intermediate"
            mock_config.search.use_ai_answers = True
            mock_config.search.enhancement_timeout = 30.0  # Add numeric timeout
            mock_config.get_active_ai_config.return_value = {}
            mock_config_manager.load_config.return_value = mock_config

            # Setup AI client
            mock_ai_client = MagicMock()
            mock_create_ai_client.return_value = mock_ai_client

            # Setup search managers that both fail
            mock_manager = AsyncMock()
            mock_fallback_manager = AsyncMock()

            mock_manager_class.side_effect = [
                mock_manager,  # First manager for main search
                mock_fallback_manager,  # Second manager for fallback
            ]
            mock_manager.__aenter__.return_value = mock_manager
            mock_manager.__aexit__.return_value = None
            mock_fallback_manager.__aenter__.return_value = mock_fallback_manager
            mock_fallback_manager.__aexit__.return_value = None

            # Both searches time out
            mock_manager.enhanced_search.side_effect = TimeoutError()
            mock_fallback_manager.enhanced_search.side_effect = Exception(
                "Fallback failed"
            )

            # Should return error response instead of raising exception
            result = await web_search("test query")

            assert "error" in result
            assert "timed out" in result["error"]
            assert result["results"] == []

    @pytest.mark.asyncio
    async def test_web_search_fast_mode_no_timeout(self):
        """Test web_search works quickly in fast mode without timeouts"""

        with (
            patch("nova.core.config.config_manager") as mock_config_manager,
            patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class,
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai_client,
        ):
            # Setup config
            mock_config = MagicMock()
            mock_config.search.default_enhancement = "fast"
            mock_config.search.default_provider = "duckduckgo"
            mock_config.search.max_results = 5
            mock_config.search.default_timeframe = "any"
            mock_config.search.default_technical_level = "intermediate"
            mock_config.search.use_ai_answers = True
            mock_config.search.enhancement_timeout = 30.0  # Add numeric timeout
            mock_config.get_active_ai_config.return_value = {}
            mock_config_manager.load_config.return_value = mock_config

            # Setup AI client
            mock_ai_client = MagicMock()
            mock_create_ai_client.return_value = mock_ai_client

            # Setup search manager that responds quickly
            mock_manager = AsyncMock()
            mock_manager_class.return_value.__aenter__.return_value = mock_manager
            mock_manager_class.return_value.__aexit__.return_value = None

            mock_manager.enhanced_search.return_value = {
                "query": "test query",
                "results": [
                    {
                        "title": "Fast Result",
                        "url": "https://example.com",
                        "snippet": "Fast snippet",
                        "source": "example.com",
                    }
                ],
                "total_results": 1,
                "search_time_ms": 500,
                "provider": "duckduckgo",
            }

            # Should complete quickly without timeout
            start_time = asyncio.get_event_loop().time()
            result = await web_search("test query", enhancement="fast")
            end_time = asyncio.get_event_loop().time()

            # Should complete in well under 30 seconds
            assert (end_time - start_time) < 5.0
            assert "results" in result
            assert len(result["results"]) == 1
            assert result["results"][0]["title"] == "Fast Result"

    @pytest.mark.asyncio
    async def test_web_search_disabled_enhancement_fast(self):
        """Test web_search with disabled enhancement runs very fast"""

        with (
            patch("nova.core.config.config_manager") as mock_config_manager,
            patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class,
        ):
            # Setup config
            mock_config = MagicMock()
            mock_config.search.default_enhancement = "disabled"
            mock_config.search.default_provider = "duckduckgo"
            mock_config.search.max_results = 5
            mock_config.search.default_timeframe = "any"
            mock_config.search.default_technical_level = "intermediate"
            mock_config.search.use_ai_answers = True
            mock_config.get_active_ai_config.return_value = {}
            mock_config_manager.load_config.return_value = mock_config

            # Setup search manager
            mock_manager = AsyncMock()
            mock_manager_class.return_value.__aenter__.return_value = mock_manager
            mock_manager_class.return_value.__aexit__.return_value = None

            mock_manager.enhanced_search.return_value = {
                "query": "test query",
                "results": [
                    {
                        "title": "Direct Result",
                        "url": "https://example.com",
                        "snippet": "Direct snippet",
                        "source": "example.com",
                    }
                ],
                "total_results": 1,
                "search_time_ms": 200,
                "provider": "duckduckgo",
            }

            # Should complete very quickly with no enhancement
            start_time = asyncio.get_event_loop().time()
            result = await web_search("test query", enhancement="disabled")
            end_time = asyncio.get_event_loop().time()

            # Should complete in well under 1 second
            assert (end_time - start_time) < 1.0
            assert "results" in result
            assert len(result["results"]) == 1
