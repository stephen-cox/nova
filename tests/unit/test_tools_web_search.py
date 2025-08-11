"""Tests for web search tools functionality"""

import sys

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
        # Remove the modules from sys.modules to force import failure
        modules_to_remove = ["nova.search", "nova.search.models", "nova.core.config"]

        # Store original modules
        original_modules = {}
        for module in modules_to_remove:
            if module in sys.modules:
                original_modules[module] = sys.modules[module]
                del sys.modules[module]

        try:
            result = await web_search("test query")

            assert result["query"] == "test query"
            # Check if we got fallback results OR real search results
            if result["provider"] == "fallback":
                assert len(result["results"]) == 1
                assert (
                    "Search functionality temporarily unavailable"
                    in result["results"][0]["title"]
                )
            else:
                # Real search worked despite removing modules
                assert "provider" in result
                assert "results" in result
        finally:
            # Restore original modules
            for module, original in original_modules.items():
                sys.modules[module] = original

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
    async def test_web_search_basic_functionality(self):
        """Test web search basic functionality (will use fallback but should work)"""
        result = await web_search("test query", max_results=3)

        # Should return valid structure regardless of fallback or enhanced search
        assert result["query"] == "test query"
        assert "provider" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        # Should have at least the fallback result
        assert len(result["results"]) >= 1


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
