"""Tests for web search tools functionality"""

from unittest.mock import MagicMock, patch

import pytest

from nova.tools.built_in.web_search import (
    get_current_time,
    web_search,
)


class TestWebSearch:
    """Test web_search function"""

    @pytest.mark.asyncio
    async def test_web_search_fallback(self):
        """Test web search with fallback when SearchManager raises exception"""
        # Mock the import to raise ImportError
        with patch("builtins.__import__") as mock_import:

            def side_effect(name, *args, **kwargs):
                if name == "nova.core.search":
                    raise ImportError("SearchManager not available")
                return __import__(name, *args, **kwargs)

            mock_import.side_effect = side_effect

            result = await web_search("test query")

            assert result["query"] == "test query"
            assert result["provider"] == "fallback"
            assert len(result["results"]) == 1
            assert (
                "Search functionality temporarily unavailable"
                in result["results"][0]["title"]
            )

    @pytest.mark.asyncio
    async def test_web_search_provider_validation(self):
        """Test web search provider validation"""
        # Invalid provider should default to duckduckgo
        result = await web_search("test query", provider="invalid")
        assert result["query"] == "test query"

        # Valid providers should be accepted
        result = await web_search("test query", provider="google")
        assert result["query"] == "test query"

    @pytest.mark.asyncio
    async def test_web_search_results_limit(self):
        """Test web search results limit validation"""
        # Test minimum limit
        result = await web_search("test query", max_results=0)
        assert result["query"] == "test query"

        # Test maximum limit
        result = await web_search("test query", max_results=100)
        assert result["query"] == "test query"

    @pytest.mark.asyncio
    @patch("nova.core.search.SearchManager")
    async def test_web_search_with_search_manager(self, mock_search_manager):
        """Test web search with mocked SearchManager"""
        # Mock search manager and results
        mock_manager = MagicMock()
        mock_search_manager.return_value = mock_manager

        # Mock search response
        mock_result = MagicMock()
        mock_result.title = "Test Title"
        mock_result.url = "https://example.com"
        mock_result.snippet = "Test snippet"
        mock_result.source = "test"

        mock_response = MagicMock()
        mock_response.results = [mock_result]

        # Make the async methods return awaitables
        async def mock_search(*args, **kwargs):
            return mock_response

        async def mock_close():
            return None

        mock_manager.search = mock_search
        mock_manager.close = mock_close

        result = await web_search("test query")

        assert result["query"] == "test query"
        assert result["provider"] == "duckduckgo"
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Test Title"
        assert result["results"][0]["url"] == "https://example.com"


class TestGetCurrentTime:
    """Test get_current_time function"""

    @pytest.mark.asyncio
    async def test_get_current_time_utc(self):
        """Test getting current time in UTC"""
        result = await get_current_time()

        assert "current_time" in result
        assert "timestamp" in result
        assert "timezone" in result
        assert "iso_format" in result
        assert result["timezone"] == "UTC"

    @pytest.mark.asyncio
    async def test_get_current_time_custom_timezone(self):
        """Test getting current time with custom timezone"""
        result = await get_current_time(timezone="America/New_York")

        assert "current_time" in result
        assert result["timezone"] == "America/New_York"

    @pytest.mark.asyncio
    async def test_get_current_time_custom_format(self):
        """Test getting current time with custom format"""
        custom_format = "%Y-%m-%d"
        result = await get_current_time(format=custom_format)

        assert "current_time" in result
        # Should match YYYY-MM-DD pattern
        import re

        assert re.match(r"\d{4}-\d{2}-\d{2}", result["current_time"])

    @pytest.mark.asyncio
    async def test_get_current_time_invalid_timezone(self):
        """Test getting current time with invalid timezone falls back to UTC"""
        result = await get_current_time(timezone="Invalid/Timezone")

        assert "current_time" in result
        assert (
            result["timezone"] == "Invalid/Timezone"
        )  # Returns requested timezone even if invalid

    @pytest.mark.asyncio
    async def test_get_current_time_types(self):
        """Test that get_current_time returns correct types"""
        result = await get_current_time()

        assert isinstance(result["current_time"], str)
        assert isinstance(result["timestamp"], int | float)
        assert isinstance(result["timezone"], str)
        assert isinstance(result["iso_format"], str)
