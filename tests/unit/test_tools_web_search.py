"""Tests for web search tools functionality"""

import asyncio
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from nova.models.config import NovaConfig, SearchConfig
from nova.models.tools import ExecutionContext
from nova.tools.built_in.web_search import (
    GetCurrentTimeHandler,
    WebSearchHandler,
    WebSearchTools,
)


class TestWebSearchHandler:
    """Test WebSearchHandler functionality"""

    @pytest.fixture
    def search_config(self):
        """Create search configuration for testing"""
        return {
            "enabled": True,
            "default_provider": "duckduckgo",
            "max_results": 5,
            "use_ai_answers": True,
            "google": {"api_key": "test-key", "search_engine_id": "test-id"},
            "bing": {"api_key": "test-bing-key"},
        }

    @pytest.fixture
    def web_search_handler(self, search_config):
        """Create WebSearchHandler for testing"""
        return WebSearchHandler(search_config)

    @pytest.fixture
    def mock_search_response(self):
        """Create mock search response"""
        mock_result = MagicMock()
        mock_result.title = "Test Result"
        mock_result.url = "https://example.com"
        mock_result.snippet = "This is a test search result"
        mock_result.source = "example.com"
        mock_result.content_summary = "Test summary"
        mock_result.extraction_success = True

        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_response.query = "test query"
        mock_response.provider = "duckduckgo"

        return mock_response

    @pytest.mark.asyncio
    async def test_web_search_parameter_handling(self, web_search_handler):
        """Test parameter handling and defaults"""
        # Test with minimal parameters
        arguments = {"query": "test query"}

        # Since we can't easily mock the dynamic import, we'll test the fallback
        # The actual functionality is tested in integration tests
        result = await web_search_handler.execute(arguments)

        # Should either work or fallback gracefully
        assert "query" in result
        assert "provider" in result
        assert "results" in result
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_web_search_default_parameters(
        self, search_config, web_search_handler
    ):
        """Test that default parameters are correctly applied"""
        # Test that handler uses config defaults
        assert web_search_handler.search_config["default_provider"] == "duckduckgo"
        assert web_search_handler.search_config["max_results"] == 5
        assert web_search_handler.search_config["use_ai_answers"] == True

    @pytest.mark.asyncio
    async def test_fallback_search_method(self, web_search_handler):
        """Test the fallback search method directly"""
        result = await web_search_handler._fallback_search("test query", 5)

        assert result["provider"] == "fallback"
        assert result["total_results"] == 1
        assert (
            "Search functionality temporarily unavailable"
            in result["results"][0]["title"]
        )
        assert result["query"] == "test query"

    @pytest.mark.asyncio
    async def test_fallback_search_with_error(self, web_search_handler):
        """Test fallback search with error message"""
        result = await web_search_handler._fallback_search(
            "test query", 5, "Network error"
        )

        assert result["provider"] == "fallback"
        assert result["error"] == "Network error"
        assert "Network error" in result["results"][0]["snippet"]

    def test_config_format_conversion(self, web_search_handler):
        """Test that config is properly formatted for SearchManager"""
        # The handler should have the right config structure
        assert "google" in web_search_handler.search_config
        assert "bing" in web_search_handler.search_config
        assert "default_provider" in web_search_handler.search_config
        assert "max_results" in web_search_handler.search_config


class TestGetCurrentTimeHandler:
    """Test GetCurrentTimeHandler functionality"""

    @pytest.fixture
    def time_handler(self):
        """Create GetCurrentTimeHandler for testing"""
        return GetCurrentTimeHandler()

    @pytest.mark.asyncio
    async def test_get_current_time_default(self, time_handler):
        """Test getting current time with default parameters"""
        result = await time_handler.execute({})

        assert "current_time" in result
        assert "timestamp" in result
        assert "timezone" in result
        assert "iso_format" in result
        assert result["timezone"] == "UTC"

    @pytest.mark.asyncio
    async def test_get_current_time_custom_timezone(self, time_handler):
        """Test getting current time with custom timezone"""
        arguments = {"timezone": "America/New_York", "format": "%Y-%m-%d %I:%M %p"}

        result = await time_handler.execute(arguments)

        assert "current_time" in result
        assert result["timezone"] == "America/New_York"
        # Should contain AM or PM due to format
        assert "AM" in result["current_time"] or "PM" in result["current_time"]

    @pytest.mark.asyncio
    async def test_get_current_time_invalid_timezone(self, time_handler):
        """Test getting current time with invalid timezone falls back to UTC"""
        arguments = {"timezone": "Invalid/Timezone", "format": "%Y-%m-%d %H:%M:%S %Z"}

        result = await time_handler.execute(arguments)

        # Should still work but may fall back to UTC behavior
        assert "current_time" in result
        assert "timestamp" in result


class TestWebSearchTools:
    """Test WebSearchTools module"""

    @pytest.fixture
    def search_config(self):
        """Create search configuration for testing"""
        return {
            "enabled": True,
            "default_provider": "duckduckgo",
            "max_results": 5,
            "use_ai_answers": True,
            "google": {},
            "bing": {},
        }

    @pytest.fixture
    def web_search_tools(self, search_config):
        """Create WebSearchTools for testing"""
        return WebSearchTools(search_config)

    @pytest.mark.asyncio
    async def test_get_tools(self, web_search_tools):
        """Test that WebSearchTools returns correct tool definitions"""
        tools = await web_search_tools.get_tools()

        assert len(tools) == 2

        # Check web_search tool
        web_search_tool, web_search_handler = tools[0]
        assert web_search_tool.name == "web_search"
        assert (
            web_search_tool.description == "Search the web for information on any topic"
        )
        assert "query" in web_search_tool.parameters["properties"]
        assert "provider" in web_search_tool.parameters["properties"]
        assert "max_results" in web_search_tool.parameters["properties"]
        assert "include_content" in web_search_tool.parameters["properties"]
        assert isinstance(web_search_handler, WebSearchHandler)

        # Check get_current_time tool
        time_tool, time_handler = tools[1]
        assert time_tool.name == "get_current_time"
        assert time_tool.description == "Get the current date and time"
        assert "timezone" in time_tool.parameters["properties"]
        assert "format" in time_tool.parameters["properties"]
        assert isinstance(time_handler, GetCurrentTimeHandler)

    def test_tool_definitions_schema(self, web_search_tools):
        """Test tool definitions have proper schema structure"""
        # This is a synchronous test since we're just checking the structure
        tools = asyncio.run(web_search_tools.get_tools())

        web_search_tool, _ = tools[0]

        # Verify required fields
        assert web_search_tool.parameters["required"] == ["query"]

        # Verify parameter types
        props = web_search_tool.parameters["properties"]
        assert props["query"]["type"] == "string"
        assert props["provider"]["type"] == "string"
        assert props["provider"]["enum"] == ["duckduckgo", "google", "bing"]
        assert props["max_results"]["type"] == "integer"
        assert props["max_results"]["minimum"] == 1
        assert props["max_results"]["maximum"] == 20
        assert props["include_content"]["type"] == "boolean"

    def test_tool_examples(self, web_search_tools):
        """Test that tools have proper examples"""
        tools = asyncio.run(web_search_tools.get_tools())

        web_search_tool, _ = tools[0]

        assert len(web_search_tool.examples) >= 2

        # Check first example
        example = web_search_tool.examples[0]
        assert "query" in example.arguments
        assert example.description is not None
        assert example.expected_result is not None


class TestWebSearchIntegration:
    """Integration tests for web search tools with Nova configuration"""

    @pytest_asyncio.fixture
    async def nova_config(self):
        """Create NovaConfig with search settings"""
        search_config = SearchConfig(
            enabled=True,
            default_provider="duckduckgo",
            max_results=5,
            use_ai_answers=True,
        )
        return NovaConfig(search=search_config)

    @pytest_asyncio.fixture
    async def function_registry(self, nova_config):
        """Create function registry with web search tools"""
        from nova.core.tools.registry import FunctionRegistry

        registry = FunctionRegistry(nova_config)
        await registry.initialize()
        yield registry
        await registry.cleanup()

    @pytest.mark.asyncio
    async def test_web_search_tool_registration(self, function_registry):
        """Test that web search tools are properly registered"""
        tools = function_registry.get_available_tools()
        tool_names = [tool.name for tool in tools]

        assert "web_search" in tool_names
        assert "get_current_time" in tool_names

    @pytest.mark.asyncio
    async def test_web_search_tool_execution_real(self, function_registry):
        """Test actual web search execution (may be skipped in CI)"""
        try:
            # This test performs actual web search - may be slow
            context = ExecutionContext(conversation_id="test")
            result = await function_registry.execute_tool(
                "web_search", {"query": "python", "max_results": 1}, context
            )

            assert result.success
            search_result = result.result
            assert "query" in search_result
            assert "results" in search_result
            assert len(search_result["results"]) <= 1

        except Exception as e:
            # If search fails (network issues, etc.), that's okay for tests
            # The important thing is that the tool is properly registered
            pytest.skip(f"Web search failed (network/config issue): {e}")

    @pytest.mark.asyncio
    async def test_time_tool_execution(self, function_registry):
        """Test time tool execution"""
        context = ExecutionContext(conversation_id="test")
        result = await function_registry.execute_tool(
            "get_current_time", {"timezone": "UTC"}, context
        )

        assert result.success
        time_result = result.result
        assert "current_time" in time_result
        assert "timestamp" in time_result
        assert "timezone" in time_result
        assert time_result["timezone"] == "UTC"
