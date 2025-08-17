"""Test to verify the QueryEnhancer fix"""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from nova.search.query_enhancer import QueryEnhancer


class TestQueryEnhancerFix:
    """Test QueryEnhancer method call fix"""

    @pytest.mark.asyncio
    async def test_query_enhancer_uses_generate_response(self):
        """Test that QueryEnhancer correctly uses generate_response method"""

        # Create a mock AI client
        mock_ai_client = Mock()
        mock_ai_client.generate_response = AsyncMock()

        # Mock response with valid JSON
        mock_response = json.dumps(
            {
                "original": "test query",
                "enhanced_queries": ["optimized query 1", "optimized query 2"],
                "search_strategy": "test strategy",
            }
        )
        mock_ai_client.generate_response.return_value = mock_response

        # Create QueryEnhancer with mock client
        enhancer = QueryEnhancer(mock_ai_client)

        # Test the enhancement
        result = await enhancer.enhance_query("test query", "some context")

        # Verify generate_response was called (not complete)
        mock_ai_client.generate_response.assert_called_once()

        # Verify the call was made with proper message format
        call_args = mock_ai_client.generate_response.call_args[0][0]
        assert isinstance(call_args, list)
        assert len(call_args) == 1
        assert call_args[0]["role"] == "user"
        assert "test query" in call_args[0]["content"]

        # Verify the result is properly structured
        assert result["original"] == "test query"
        assert len(result["enhanced_queries"]) == 2
        assert result["search_strategy"] == "test strategy"

    @pytest.mark.asyncio
    async def test_query_enhancer_with_real_ai_client_interface(self):
        """Test that QueryEnhancer works with real AI client interface"""

        # Create a mock that simulates real AI client (has generate_response, no complete)
        mock_ai_client = Mock()
        mock_ai_client.generate_response = AsyncMock()

        # Make the mock more strict - don't auto-create 'complete' method
        del mock_ai_client.complete  # Remove if it was auto-created

        # Mock response
        mock_response = json.dumps(
            {
                "original": "test query",
                "enhanced_queries": ["query 1"],
                "search_strategy": "strategy",
            }
        )
        mock_ai_client.generate_response.return_value = mock_response

        # Create QueryEnhancer
        enhancer = QueryEnhancer(mock_ai_client)

        # This should work using generate_response method
        result = await enhancer.enhance_query("test query")

        # Verify generate_response was called (the correct method)
        mock_ai_client.generate_response.assert_called_once()
        assert result["original"] == "test query"

        # Verify the method was called with proper message format
        call_args = mock_ai_client.generate_response.call_args[0][0]
        assert isinstance(call_args, list)
        assert call_args[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_query_enhancer_error_handling(self):
        """Test that QueryEnhancer handles AI client errors properly"""

        # Create a mock AI client that raises an exception
        mock_ai_client = Mock()
        mock_ai_client.generate_response = AsyncMock()
        mock_ai_client.generate_response.side_effect = Exception("AI client error")

        # Create QueryEnhancer
        enhancer = QueryEnhancer(mock_ai_client)

        # Should raise the exception from generate_response
        with pytest.raises(Exception, match="AI client error"):
            await enhancer.enhance_query("test query")

        # Verify generate_response was called
        mock_ai_client.generate_response.assert_called_once()
