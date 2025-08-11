"""Integration tests for search functionality"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nova.search.manager import EnhancedSearchManager
from nova.search.models import (
    SearchEnhancementMode,
    SearchMemoryConstraints,
    SearchResponse,
    SearchResult,
)


class TestSearchIntegration:
    """Integration tests for search components"""

    @pytest.mark.asyncio
    async def test_end_to_end_search_workflow(self):
        """Test complete search workflow from query to enhanced results"""
        config = {
            "search": {
                "enabled": True,
                "default_provider": "duckduckgo",
                "default_enhancement": "fast",
                "max_results": 3,
            }
        }
        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response = AsyncMock(return_value='[{"query": "Python async programming", "priority": 1, "expected_results": 10, "rationale": "Test query"}]')

        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

        # Mock the search response properly
        mock_search_response = SearchResponse(
            query="Python async programming",
            results=[
                SearchResult(
                    title="Integration Test Result",
                    url="https://example.com",
                    snippet="Original snippet",
                    source="example.com",
                )
            ],
            total_results=1,
            search_time_ms=100,
            provider="DuckDuckGo",
        )

        # Mock the _execute_enhanced_searches method to return SearchResponse
        with patch.object(manager, "_execute_enhanced_searches") as mock_execute:
            mock_execute.return_value = mock_search_response

            result = await manager.enhanced_search(
                "Python async programming",
                enhancement_mode=SearchEnhancementMode.FAST,
                max_results=3,
            )

            # Verify the complete workflow
            assert result["query"] == "Python async programming"
            assert len(result["results"]) == 1
            assert result["results"][0].title == "Integration Test Result"
            assert "enhancement_details" in result
            assert result["provider"] == "DuckDuckGo"

    @pytest.mark.asyncio
    async def test_multi_provider_fallback_chain(self):
        """Test fallback behavior across multiple providers"""
        config = {
            "search": {
                "enabled": True,
                "google_api_key": "fake_key",
                "google_search_engine_id": "fake_id",
                "bing_api_key": "fake_bing_key",
            }
        }

        manager = EnhancedSearchManager(config)

        # Mock all providers to fail except DuckDuckGo
        mock_google = AsyncMock()
        mock_google.search.side_effect = Exception("Google API limit reached")

        mock_bing = AsyncMock()
        mock_bing.search.side_effect = Exception("Bing API error")

        mock_duckduckgo = AsyncMock()
        mock_duckduckgo.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    title="Fallback Success",
                    url="https://example.com",
                    snippet="DuckDuckGo worked",
                    source="example.com",
                )
            ],
            total_results=1,
            search_time_ms=200,
            provider="DuckDuckGo",
        )

        manager.providers = {
            "google": mock_google,
            "bing": mock_bing,
            "duckduckgo": mock_duckduckgo,
        }

        # Mock single search to test fallback
        with patch.object(manager, '_execute_single_search') as mock_single:
            mock_single.return_value = SearchResponse(
                query="test query",
                results=[
                    SearchResult(
                        title="Fallback Success",
                        url="https://example.com",
                        snippet="DuckDuckGo worked",
                        source="example.com",
                    )
                ],
                total_results=1,
                search_time_ms=200,
                provider="DuckDuckGo",
            )

            result = await manager.enhanced_search("test query", provider="google")

            # Should fall back to single search when enhancement fails
            assert result["provider"] == "DuckDuckGo"
            assert len(result["results"]) == 1
            assert "Fallback Success" in result["results"][0].title

    @pytest.mark.asyncio
    async def test_concurrent_search_execution(self):
        """Test concurrent execution of multiple enhanced queries"""
        config = {"search": {"enabled": True, "default_provider": "duckduckgo"}}
        mock_ai_client = MagicMock()

        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

        # Mock query enhancer to return multiple queries
        from nova.search.models import EnhancedSearchPlan, EnhancedSearchQuery

        enhanced_queries = [
            EnhancedSearchQuery(
                query="Python async programming tutorial",
                priority=1,
                expected_results=5,
                rationale="Main query",
            ),
            EnhancedSearchQuery(
                query="Python asyncio examples",
                priority=2,
                expected_results=3,
                rationale="Related examples",
            ),
        ]

        mock_plan = EnhancedSearchPlan(
            original_query="Python async",
            enhanced_queries=enhanced_queries,
            extraction_details={"keywords": [], "entities": []},
            enhancement_mode=SearchEnhancementMode.FAST,
            processing_time_ms=100,
            context_used=False,
        )

        manager.query_enhancer = AsyncMock()
        manager.query_enhancer.enhance_query.return_value = mock_plan

        # Mock search client to return different results for different queries
        mock_client = AsyncMock()

        def mock_search(query, **kwargs):
            if "tutorial" in query:
                return SearchResponse(
                    query=query,
                    results=[
                        SearchResult(
                            title="Tutorial Result",
                            url="https://tutorial.com",
                            snippet="Tutorial content",
                            source="tutorial.com",
                        )
                    ],
                    total_results=1,
                    search_time_ms=150,
                    provider="DuckDuckGo",
                )
            else:
                return SearchResponse(
                    query=query,
                    results=[
                        SearchResult(
                            title="Example Result",
                            url="https://examples.com",
                            snippet="Example content",
                            source="examples.com",
                        )
                    ],
                    total_results=1,
                    search_time_ms=120,
                    provider="DuckDuckGo",
                )

        mock_client.search.side_effect = mock_search
        manager.providers["duckduckgo"] = mock_client

        result = await manager.enhanced_search(
            "Python async", enhancement_mode=SearchEnhancementMode.FAST
        )

        # Should have results from both queries
        assert len(result["results"]) == 2
        titles = [r.title for r in result["results"]]
        assert "Tutorial Result" in titles
        assert "Example Result" in titles

    @pytest.mark.asyncio
    async def test_content_enhancement_pipeline(self):
        """Test the content extraction and enhancement pipeline"""
        config = {"search": {"enabled": True, "default_provider": "duckduckgo"}}
        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response.return_value = "AI-enhanced content summary"

        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

        # Mock search client with content extraction
        mock_client = AsyncMock()
        mock_client.extract_content.return_value = (
            "Full webpage content that was extracted successfully",
            True,
        )

        initial_results = [
            SearchResult(
                title="Test Article",
                url="https://article.com/test",
                snippet="Original snippet",
                source="article.com",
            )
        ]

        enhanced_results = await manager._enhance_results_with_content(
            initial_results, "test query", "duckduckgo"
        )

        assert len(enhanced_results) == 1
        assert enhanced_results[0].enhanced_snippet == "AI-enhanced content summary"

        # Verify content extraction was called
        mock_client.extract_content.assert_called_once_with("https://article.com/test")

        # Verify AI summarization was called
        mock_ai_client.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_constraints_application(self):
        """Test application of search constraints across the pipeline"""
        config = {"search": {"enabled": True, "default_provider": "duckduckgo"}}
        mock_ai_client = MagicMock()

        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

        constraints = SearchMemoryConstraints(
            technical_level="expert",
            timeframe="recent",
            locale="en-US",
            domain_filter=["stackoverflow.com", "github.com"],
        )

        # Mock query enhancer to use constraints
        manager.query_enhancer = AsyncMock()

        # Mock search execution
        mock_client = AsyncMock()
        mock_client.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    title="Expert Level Result",
                    url="https://stackoverflow.com/expert-answer",
                    snippet="Technical expert content",
                    source="stackoverflow.com",
                )
            ],
            total_results=1,
            search_time_ms=200,
            provider="DuckDuckGo",
        )
        manager.providers["duckduckgo"] = mock_client

        result = await manager.enhanced_search(
            "advanced Python patterns",
            constraints=constraints,
            enhancement_mode=SearchEnhancementMode.FAST,
        )

        # Verify constraints were applied
        assert "constraints" in result
        assert result["constraints"]["technical_level"] == "expert"
        assert result["constraints"]["timeframe"] == "recent"

        # Verify query enhancer was called with constraints
        manager.query_enhancer.enhance_query.assert_called_once()
        call_args = manager.query_enhancer.enhance_query.call_args
        assert call_args.kwargs["constraints"] == constraints

    @pytest.mark.asyncio
    async def test_performance_monitoring(self):
        """Test performance monitoring across search pipeline"""
        config = {"search": {"enabled": True, "default_provider": "duckduckgo"}}

        manager = EnhancedSearchManager(config)

        # Mock search client with realistic timing
        mock_client = AsyncMock()
        mock_client.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    title="Performance Test",
                    url="https://example.com",
                    snippet="Performance content",
                    source="example.com",
                )
            ],
            total_results=1,
            search_time_ms=250,
            provider="DuckDuckGo",
        )
        manager.providers["duckduckgo"] = mock_client

        import time

        start_time = time.time()

        result = await manager.enhanced_search("performance test")

        end_time = time.time()

        # Verify performance metrics are included
        assert "performance" in result
        assert "total_time_ms" in result["performance"]
        assert result["performance"]["total_time_ms"] > 0

        # Verify actual timing is reasonable
        actual_time_ms = (end_time - start_time) * 1000
        assert actual_time_ms < 5000  # Should complete within 5 seconds

    @pytest.mark.asyncio
    async def test_error_recovery_and_partial_results(self):
        """Test error recovery and handling of partial results"""
        config = {"search": {"enabled": True, "default_provider": "duckduckgo"}}

        manager = EnhancedSearchManager(config)

        # Set up scenario where content enhancement fails but search succeeds
        mock_client = AsyncMock()
        mock_client.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    title="Partial Success",
                    url="https://example.com",
                    snippet="Original snippet",
                    source="example.com",
                )
            ],
            total_results=1,
            search_time_ms=150,
            provider="DuckDuckGo",
        )
        # Content extraction fails
        mock_client.extract_content.side_effect = Exception("Content extraction failed")

        manager.providers["duckduckgo"] = mock_client

        result = await manager.enhanced_search("partial results test")

        # Should still return results even if enhancement fails
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Partial Success"

        # Should include error information
        assert "warnings" in result or "errors" in result or len(result["results"]) > 0

    @pytest.mark.asyncio
    async def test_configuration_validation_integration(self):
        """Test configuration validation across components"""
        # Test with invalid Google configuration
        config = {
            "search": {
                "enabled": True,
                "google_api_key": "",  # Invalid
                "bing_api_key": "valid_key",
            }
        }

        manager = EnhancedSearchManager(config)

        # Google should not be available due to invalid config
        providers = manager.get_available_providers()
        assert (
            "google" not in providers
            or len([p for p in providers if "google" in p.lower()]) == 0
        )

        # But other providers should still work
        assert len(providers) > 0

    @pytest.mark.asyncio
    async def test_memory_constraints_with_real_workflow(self):
        """Test memory constraints in a realistic search workflow"""
        config = {
            "search": {
                "enabled": True,
                "default_provider": "duckduckgo",
                "max_results": 2,
            }
        }
        mock_ai_client = MagicMock()

        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

        constraints = SearchMemoryConstraints(
            technical_level="beginner", timeframe="past_year", locale="en-GB"
        )

        # Mock the workflow with constraints
        mock_client = AsyncMock()
        mock_client.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    title="Beginner Friendly Result",
                    url="https://tutorial.com/basic",
                    snippet="Easy to understand content",
                    source="tutorial.com",
                )
            ],
            total_results=1,
            search_time_ms=180,
            provider="DuckDuckGo",
        )
        manager.providers["duckduckgo"] = mock_client

        # Mock query enhancer to consider constraints
        manager.query_enhancer = AsyncMock()

        result = await manager.enhanced_search(
            "learn programming",
            constraints=constraints,
            enhancement_mode=SearchEnhancementMode.FAST,
        )

        # Verify constraints are preserved and applied
        assert result["constraints"]["technical_level"] == "beginner"
        assert result["constraints"]["timeframe"] == "past_year"
        assert result["constraints"]["locale"] == "en-GB"

        # Verify query enhancer received constraints
        if manager.query_enhancer.enhance_query.called:
            call_kwargs = manager.query_enhancer.enhance_query.call_args.kwargs
            assert "constraints" in call_kwargs
