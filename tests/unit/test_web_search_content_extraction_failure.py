"""Tests for web_search tool content extraction failures"""

from unittest.mock import AsyncMock, patch

import pytest

from nova.models.config import AIProfile, NovaConfig, SearchConfig
from nova.tools.built_in.web_search import web_search


@pytest.fixture
def test_config():
    """Test configuration"""
    search_config = SearchConfig(
        enabled=True,
        default_provider="duckduckgo",
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
        api_key="test-key",
        temperature=0.7,
        max_tokens=2000,
        description="Test profile",
    )

    config = NovaConfig(
        search=search_config, profiles={"default": ai_profile}, active_profile="default"
    )

    return config


class TestWebSearchContentExtractionFailure:
    """Test web_search tool content extraction failure scenarios"""

    @pytest.mark.asyncio
    async def test_readability_xml_error_handling(self, test_config):
        """Test handling of readability XML compatibility errors"""
        # Mock a search response that would cause readability to fail
        mock_search_response = {
            "query": "test search",
            "provider": "duckduckgo",
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://duckduckgo.com/",
                    "snippet": "Test snippet",
                    "source": "duckduckgo.com",
                    "full_content": None,  # Content extraction will fail
                    "content_summary": None,
                    "extraction_success": False,
                }
            ],
            "total_results": 1,
            "search_time_ms": 500,
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=test_config
            ),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai,
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock AI client
            mock_ai_client = AsyncMock()
            mock_ai_client.close = AsyncMock()
            mock_create_ai.return_value = mock_ai_client

            # Mock search manager to return result with extraction failure
            mock_manager_instance = AsyncMock()
            mock_manager_instance.enhanced_search = AsyncMock(
                return_value=mock_search_response
            )
            mock_search_manager.return_value.__aenter__ = AsyncMock(
                return_value=mock_manager_instance
            )
            mock_search_manager.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute search
            result = await web_search(query="test search")

            # Verify search completes despite extraction failure
            assert result is not None
            assert result["query"] == "test search"
            assert len(result["results"]) == 1

            # Verify extraction failure is marked
            assert result["results"][0]["extraction_success"] == False
            assert result["results"][0].get("content") is None

            # Verify AI client cleanup
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_content_extraction_with_invalid_html(self, test_config):
        """Test content extraction when HTML contains invalid characters"""
        # This tests the specific scenario where readability fails with XML compatibility errors

        mock_search_response = {
            "query": "search with problematic content",
            "provider": "duckduckgo",
            "results": [
                {
                    "title": "Problematic Content Site",
                    "url": "https://example.com/problematic",
                    "snippet": "Site with invalid HTML characters",
                    "source": "example.com",
                    "full_content": None,  # Would be None due to extraction failure
                    "content_summary": None,
                    "extraction_success": False,
                }
            ],
            "total_results": 1,
            "search_time_ms": 800,
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=test_config
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

            # Execute search
            result = await web_search(query="search with problematic content")

            # Verify search handles extraction failure gracefully
            assert result is not None
            assert result["query"] == "search with problematic content"
            assert len(result["results"]) == 1

            # The result should still be returned, just without extracted content
            assert result["results"][0]["title"] == "Problematic Content Site"
            assert (
                result["results"][0]["snippet"] == "Site with invalid HTML characters"
            )
            assert result["results"][0]["extraction_success"] == False

            # Verify AI client cleanup
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_manager_handles_extraction_errors(self, test_config):
        """Test that search manager properly handles content extraction errors"""

        # Mock a scenario where some results extract successfully, others fail
        mock_search_response = {
            "query": "mixed extraction results",
            "provider": "duckduckgo",
            "results": [
                {
                    "title": "Good Content Site",
                    "url": "https://example.com/good",
                    "snippet": "Site with clean HTML",
                    "source": "example.com",
                    "full_content": "This is clean extracted content without invalid characters.",
                    "content_summary": "Summary of clean content",
                    "extraction_success": True,
                },
                {
                    "title": "Problematic Content Site",
                    "url": "https://duckduckgo.com/",
                    "snippet": "Site with invalid HTML characters",
                    "source": "duckduckgo.com",
                    "full_content": None,
                    "content_summary": None,
                    "extraction_success": False,
                },
            ],
            "total_results": 2,
            "search_time_ms": 1200,
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=test_config
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

            # Execute search
            result = await web_search(query="mixed extraction results")

            # Verify search handles mixed results
            assert result is not None
            assert len(result["results"]) == 2

            # First result should have successful extraction
            assert result["results"][0]["extraction_success"] == True
            assert result["results"][0].get("content") is not None
            assert result["results"][0].get("content_summary") is not None

            # Second result should have failed extraction
            assert result["results"][1]["extraction_success"] == False
            assert result["results"][1].get("content") is None
            assert result["results"][1].get("content_summary") is None

            # Verify AI client cleanup
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_continues_after_extraction_failures(self, test_config):
        """Test that search operations continue normally after content extraction failures"""

        mock_search_response = {
            "query": "normal search after extraction failure",
            "provider": "duckduckgo",
            "results": [
                {
                    "title": "Regular Search Result",
                    "url": "https://example.com/normal",
                    "snippet": "Normal search result without extraction issues",
                    "source": "example.com",
                    "extraction_success": False,  # Even if extraction fails, search works
                }
            ],
            "total_results": 1,
            "search_time_ms": 300,
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=test_config
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

            # Execute search
            result = await web_search(query="normal search after extraction failure")

            # Verify search completes successfully despite extraction issues
            assert result is not None
            assert result["query"] == "normal search after extraction failure"
            assert result["provider"] == "duckduckgo"
            assert len(result["results"]) == 1
            assert result["total_results"] == 1

            # Basic search functionality should work regardless of extraction
            assert result["results"][0]["title"] == "Regular Search Result"
            assert (
                result["results"][0]["snippet"]
                == "Normal search result without extraction issues"
            )

            # Verify AI client cleanup
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_when_all_content_extraction_fails(self, test_config):
        """Test fallback behavior when all content extraction attempts fail"""

        # Mock a scenario where EnhancedSearchManager itself encounters extraction errors
        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=test_config
            ),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai,
            patch("nova.search.manager.EnhancedSearchManager") as mock_search_manager,
        ):
            # Mock AI client
            mock_ai_client = AsyncMock()
            mock_ai_client.close = AsyncMock()
            mock_create_ai.return_value = mock_ai_client

            # Mock search manager to raise an extraction-related error
            mock_search_manager.return_value.__aenter__.side_effect = ValueError(
                "All strings must be XML compatible: Unicode or ASCII, no NULL bytes or control characters"
            )

            # Execute search
            result = await web_search(query="search that triggers extraction error")

            # Verify fallback response is returned
            assert result is not None
            assert result["provider"] == "fallback"
            assert "error" in result
            assert "All strings must be XML compatible" in result["error"]

            # Verify AI client was still closed despite the error
            mock_ai_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_duckduckgo_specific_extraction_issue(self, test_config):
        """Test the specific DuckDuckGo URL extraction issue from the error"""

        mock_search_response = {
            "query": "search query",
            "provider": "duckduckgo",
            "results": [
                {
                    "title": "DuckDuckGo Result",
                    "url": "https://duckduckgo.com/",  # This URL was in the error
                    "snippet": "DuckDuckGo search engine",
                    "source": "duckduckgo.com",
                    "full_content": None,
                    "content_summary": None,
                    "extraction_success": False,
                }
            ],
            "total_results": 1,
            "search_time_ms": 400,
        }

        with (
            patch(
                "nova.core.config.config_manager.load_config", return_value=test_config
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

            # Execute search
            result = await web_search(query="search query")

            # Verify search works despite DuckDuckGo extraction failure
            assert result is not None
            assert len(result["results"]) == 1
            assert result["results"][0]["url"] == "https://duckduckgo.com/"
            assert result["results"][0]["extraction_success"] == False

            # Verify AI client cleanup
            mock_ai_client.close.assert_called_once()
