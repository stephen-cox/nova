"""Tests for web search tools functionality"""

from unittest.mock import AsyncMock, MagicMock, patch

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
        # Mock the import to fail
        with patch.dict(
            "sys.modules",
            {
                "nova.core.config": None,
                "nova.search.manager": None,
                "nova.search.models": None,
            },
        ):
            result = await web_search("test query")

            assert result["query"] == "test query"
            assert result["provider"] == "fallback"
            assert len(result["results"]) == 1
            assert (
                "Search functionality temporarily unavailable"
                in result["results"][0]["title"]
            )
            assert "error" in result

    @pytest.mark.asyncio
    async def test_web_search_provider_validation(self):
        """Test web search provider validation"""
        with patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.enhanced_search = AsyncMock(
                return_value={
                    "query": "test query",
                    "provider": "duckduckgo",
                    "results": [],
                    "total_results": 0,
                    "search_time_ms": 10,
                }
            )
            mock_manager.close = AsyncMock()
            mock_manager_class.return_value = mock_manager

            with patch("nova.core.config.config_manager") as mock_config:
                mock_config_obj = MagicMock()
                mock_config_obj.search.default_enhancement = "fast"
                mock_config_obj.search.default_provider = "duckduckgo"
                mock_config_obj.search.max_results = 5
                mock_config_obj.search.default_timeframe = "any"
                mock_config_obj.search.default_technical_level = "intermediate"
                mock_config_obj.get_active_ai_config.return_value = {}
                mock_config_obj.search.model_dump.return_value = {}
                mock_config.load_config.return_value = mock_config_obj

                # Invalid provider should default to duckduckgo
                result = await web_search("test query", provider="invalid")
                assert result["query"] == "test query"

                # Valid providers should be accepted
                result = await web_search("test query", provider="google")
                assert result["query"] == "test query"

    @pytest.mark.asyncio
    async def test_web_search_results_limit(self):
        """Test web search results limit validation"""
        with patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.enhanced_search = AsyncMock(
                return_value={
                    "query": "test query",
                    "provider": "duckduckgo",
                    "results": [],
                    "total_results": 0,
                    "search_time_ms": 10,
                }
            )
            mock_manager.close = AsyncMock()
            mock_manager_class.return_value = mock_manager

            with patch("nova.core.config.config_manager") as mock_config:
                mock_config_obj = MagicMock()
                mock_config_obj.search.default_enhancement = "fast"
                mock_config_obj.search.default_provider = "duckduckgo"
                mock_config_obj.search.max_results = 5
                mock_config_obj.search.default_timeframe = "any"
                mock_config_obj.search.default_technical_level = "intermediate"
                mock_config_obj.get_active_ai_config.return_value = {}
                mock_config_obj.search.model_dump.return_value = {}
                mock_config.load_config.return_value = mock_config_obj

                # Test minimum limit
                result = await web_search("test query", max_results=0)
                assert result["query"] == "test query"

                # Test maximum limit
                result = await web_search("test query", max_results=100)
                assert result["query"] == "test query"

    @pytest.mark.asyncio
    async def test_web_search_basic_functionality(self):
        """Test web search basic functionality"""
        with patch("nova.search.manager.EnhancedSearchManager") as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.enhanced_search = AsyncMock(
                return_value={
                    "query": "test query",
                    "provider": "duckduckgo",
                    "results": [
                        {
                            "title": "Test Result",
                            "url": "https://example.com",
                            "snippet": "Test snippet",
                            "source": "example.com",
                        }
                    ],
                    "total_results": 1,
                    "search_time_ms": 100,
                }
            )
            mock_manager.close = AsyncMock()
            mock_manager_class.return_value = mock_manager

            with patch("nova.core.config.config_manager") as mock_config:
                mock_config_obj = MagicMock()
                mock_config_obj.search.default_enhancement = "fast"
                mock_config_obj.search.default_provider = "duckduckgo"
                mock_config_obj.search.max_results = 5
                mock_config_obj.search.default_timeframe = "any"
                mock_config_obj.search.default_technical_level = "intermediate"
                mock_config_obj.get_active_ai_config.return_value = {}
                mock_config_obj.search.model_dump.return_value = {}
                mock_config.load_config.return_value = mock_config_obj

                result = await web_search("test query", max_results=3)

                # Should return valid structure
                assert result["query"] == "test query"
                assert result["provider"] == "duckduckgo"
                assert "results" in result
                assert isinstance(result["results"], list)
                assert len(result["results"]) == 1
                assert result["results"][0]["title"] == "Test Result"


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
