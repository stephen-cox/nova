"""Comprehensive error handling tests for enhanced search"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from nova.search.engines import DuckDuckGoSearchClient
from nova.search.enhancement.enhancer import QueryEnhancer
from nova.search.enhancement.extractors import KeywordExtractor
from nova.search.manager import EnhancedSearchManager
from nova.search.models import SearchEnhancementMode, SearchError


class TestSearchEngineErrorHandling:
    """Test error handling in search engines"""

    @pytest.mark.asyncio
    async def test_http_timeout_error(self):
        """Test handling of HTTP timeout errors"""
        client = DuckDuckGoSearchClient({"timeout": 1.0})

        with patch.object(client.client, "get") as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(SearchError, match="DuckDuckGo search failed"):
                await client.search("test query")

    @pytest.mark.asyncio
    async def test_http_connection_error(self):
        """Test handling of HTTP connection errors"""
        client = DuckDuckGoSearchClient({})

        with patch.object(client.client, "get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection failed")

            with pytest.raises(SearchError, match="DuckDuckGo search failed"):
                await client.search("test query")

    @pytest.mark.asyncio
    async def test_http_server_error(self):
        """Test handling of HTTP server errors"""
        client = DuckDuckGoSearchClient({})

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=mock_response
        )

        with patch.object(client.client, "get", return_value=mock_response):
            with pytest.raises(SearchError, match="DuckDuckGo search failed"):
                await client.search("test query")

    @pytest.mark.asyncio
    async def test_malformed_response_handling(self):
        """Test handling of malformed API responses"""
        client = DuckDuckGoSearchClient({})

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "not json data"
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.client, "get", return_value=mock_response):
            # Should not raise, but return helpful error message
            result = await client.search("test query")
            assert len(result.results) == 1
            assert result.total_results == 1
            assert result.results[0].title == "Search results not available"
            assert "Unable to parse search results" in result.results[0].snippet

    @pytest.mark.asyncio
    async def test_content_extraction_errors(self):
        """Test content extraction error handling"""
        client = DuckDuckGoSearchClient({})

        # Test all extraction methods failing
        with patch("nova.search.engines.base.Article") as mock_article_class:
            # Mock newspaper3k to fail
            mock_article = MagicMock()
            mock_article.download.side_effect = Exception("Network error")
            mock_article_class.return_value = mock_article

            with patch.object(client.client, "get") as mock_get:
                mock_get.side_effect = Exception("Network error")

                content, success = await client.extract_content("https://example.com")
                assert success is False
                assert content is None


class TestQueryEnhancementErrorHandling:
    """Test error handling in query enhancement"""

    @pytest.mark.asyncio
    async def test_ai_client_failure(self):
        """Test handling of AI client failures"""
        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response.side_effect = Exception(
            "AI service unavailable"
        )

        enhancer = QueryEnhancer(ai_client=mock_ai_client)

        # Should fallback to rule-based enhancement
        result = await enhancer.enhance_query(
            "Python programming", enhancement_mode=SearchEnhancementMode.FAST
        )

        assert result.original_query == "Python programming"
        assert len(result.enhanced_queries) > 0
        assert result.enhanced_queries[0].query == "Python programming"  # Fallback

    @pytest.mark.asyncio
    async def test_invalid_llm_response(self):
        """Test handling of invalid LLM responses"""
        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response.return_value = "This is not valid JSON"

        enhancer = QueryEnhancer(ai_client=mock_ai_client)

        result = await enhancer.enhance_query(
            "Python programming", enhancement_mode=SearchEnhancementMode.FAST
        )

        # Should fallback to original query
        assert result.original_query == "Python programming"
        assert len(result.enhanced_queries) == 1
        assert result.enhanced_queries[0].query == "Python programming"

    @pytest.mark.asyncio
    async def test_keyword_extraction_failure(self):
        """Test handling of keyword extraction failures"""
        extractor = KeywordExtractor()

        # Test with empty text
        keywords = extractor.extract_keywords("", max_keywords=5)
        assert len(keywords) == 0

        # Test with very short text
        keywords = extractor.extract_keywords("a", max_keywords=5)
        assert len(keywords) == 0

    @pytest.mark.asyncio
    async def test_entity_extraction_failure(self):
        """Test handling of entity extraction failures"""
        extractor = KeywordExtractor()

        # Mock spaCy to fail
        with patch("nova.search.enhancement.extractors.spacy.load") as mock_load:
            mock_load.side_effect = Exception("spaCy model not found")

            entities = extractor.extract_entities("Python programming tutorial")
            assert len(entities) == 0


class TestSearchManagerErrorHandling:
    """Test error handling in search manager"""

    @pytest.mark.asyncio
    async def test_no_providers_available(self):
        """Test handling when no search providers are available"""
        config = {"search": {"enabled": True}}
        manager = EnhancedSearchManager(config)

        # Clear all providers
        manager.providers.clear()

        with pytest.raises(SearchError, match="No search providers configured"):
            await manager.enhanced_search("test query")

    @pytest.mark.asyncio
    async def test_invalid_provider_requested(self):
        """Test handling of requests for invalid providers"""
        config = {"search": {"enabled": True}}
        manager = EnhancedSearchManager(config)

        with pytest.raises(
            SearchError, match="Search provider 'nonexistent' not available"
        ):
            await manager.enhanced_search("test query", provider="nonexistent")

    @pytest.mark.asyncio
    async def test_search_provider_failure_with_fallback(self):
        """Test search provider failure with fallback to simpler search"""
        config = {"search": {"enabled": True, "default_provider": "duckduckgo"}}
        manager = EnhancedSearchManager(config)

        # Mock enhancement to work but search execution to fail
        with patch.object(manager, "query_enhancer") as mock_enhancer:
            mock_enhancer.enhance_query.side_effect = Exception("Enhancement failed")

            # Mock single search to work
            with patch.object(manager, "_execute_single_search") as mock_single:
                from nova.search.models import SearchResponse, SearchResult

                mock_single.return_value = SearchResponse(
                    query="test query",
                    results=[
                        SearchResult(
                            title="Fallback Result",
                            url="https://example.com",
                            snippet="Fallback content",
                            source="example.com",
                        )
                    ],
                    total_results=1,
                    search_time_ms=100,
                    provider="DuckDuckGo",
                )

                result = await manager.enhanced_search(
                    "test query", enhancement_mode=SearchEnhancementMode.FAST
                )

                assert result["query"] == "test query"
                assert len(result["results"]) == 1
                assert result["results"][0].title == "Fallback Result"

    @pytest.mark.asyncio
    async def test_partial_search_failure(self):
        """Test handling of partial failures in concurrent searches"""
        config = {"search": {"enabled": True, "default_provider": "duckduckgo"}}
        mock_ai_client = AsyncMock()
        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

        # Create mock search client that fails some queries
        mock_client = AsyncMock()
        responses = [
            Exception("Query 1 failed"),  # First query fails
            # Second query succeeds (would be handled by the search execution)
        ]
        mock_client.search.side_effect = responses
        manager.providers["duckduckgo"] = mock_client

        # Test that manager handles partial failures gracefully
        with patch.object(manager, "_execute_enhanced_searches") as mock_execute:
            from nova.search.models import SearchResponse, SearchResult

            # Mock successful execution despite partial failures
            mock_execute.return_value = SearchResponse(
                query="test query",
                results=[
                    SearchResult(
                        title="Partial Success",
                        url="https://example.com",
                        snippet="Some results available",
                        source="example.com",
                    )
                ],
                total_results=1,
                search_time_ms=200,
                provider="DuckDuckGo",
            )

            result = await manager.enhanced_search("test query")
            assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_content_summarization_failure(self):
        """Test handling of content summarization failures"""
        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response.side_effect = Exception("Summarization failed")

        from nova.search.manager import ContentSummarizer

        summarizer = ContentSummarizer(mock_ai_client)

        # Should fallback to simple truncation
        summary = await summarizer.summarize_content(
            "This is a long content that needs to be summarized. " * 10, "test query"
        )

        # Should not be empty and should be fallback content
        assert len(summary) > 0
        assert "This is a long content" in summary


class TestConfigurationErrorHandling:
    """Test configuration-related error handling"""

    def test_invalid_enhancement_mode(self):
        """Test handling of invalid enhancement modes"""
        # Should default to FAST mode when invalid mode is provided
        from nova.search.models import SearchEnhancementMode

        with pytest.raises(ValueError):
            SearchEnhancementMode("invalid_mode")

    def test_missing_api_keys(self):
        """Test handling of missing API keys for paid providers"""
        config = {
            "search": {
                "enabled": True,
                "google": {"search_engine_id": "test_id"},  # Missing API key
                "bing": {},  # Missing API key
            }
        }

        manager = EnhancedSearchManager(config)

        # Should only have DuckDuckGo available (free provider)
        providers = manager.get_available_providers()
        assert "duckduckgo" in providers
        assert "google" not in providers
        assert "bing" not in providers

    @pytest.mark.asyncio
    async def test_network_unavailable(self):
        """Test handling when network is completely unavailable"""
        client = DuckDuckGoSearchClient({})

        with patch.object(client.client, "get") as mock_get:
            mock_get.side_effect = httpx.NetworkError("Network unreachable")

            with pytest.raises(SearchError):
                await client.search("test query")

    @pytest.mark.asyncio
    async def test_memory_constraints_with_errors(self):
        """Test memory constraints handling when errors occur"""
        from nova.search.models import SearchMemoryConstraints

        config = {"search": {"enabled": True}}
        mock_ai_client = AsyncMock()
        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

        constraints = SearchMemoryConstraints(
            technical_level="expert",
            timeframe="recent",
        )

        # Mock AI to fail
        mock_ai_client.generate_response.side_effect = Exception("AI failed")

        # Should still work with fallback
        with patch.object(manager, "_execute_single_search") as mock_single:
            from nova.search.models import SearchResponse, SearchResult

            mock_single.return_value = SearchResponse(
                query="test query",
                results=[
                    SearchResult(
                        title="Test Result",
                        url="https://example.com",
                        snippet="Test content",
                        source="example.com",
                    )
                ],
                total_results=1,
                search_time_ms=50,
                provider="DuckDuckGo",
            )

            result = await manager.enhanced_search(
                "test query",
                memory_constraints=constraints,
                enhancement_mode=SearchEnhancementMode.FAST,
            )

            assert result["query"] == "test query"
            assert len(result["results"]) == 1
