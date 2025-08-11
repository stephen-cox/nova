"""Integration tests for search functionality - Fixed version"""

from unittest.mock import AsyncMock, patch

import pytest

from nova.search.manager import EnhancedSearchManager
from nova.search.models import (
    EnhancedSearchPlan,
    EnhancedSearchQuery,
    SearchEnhancementMode,
    SearchMemoryConstraints,
    SearchResponse,
    SearchResult,
)


class TestSearchIntegrationFixed:
    """Fixed integration tests for search components"""

    @pytest.mark.asyncio
    async def test_enhanced_search_end_to_end(self):
        """Test complete enhanced search workflow"""
        config = {
            "search": {
                "enabled": True,
                "default_provider": "duckduckgo",
                "default_enhancement": "fast",
                "max_results": 3,
            }
        }

        # Create proper AI client mock
        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response = AsyncMock(
            return_value='[{"query": "Python async tutorial", "priority": 1, "expected_results": 10, "rationale": "Enhanced query"}]'
        )

        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

        # Mock the search client
        mock_search_response = SearchResponse(
            query="Python async tutorial",
            results=[
                SearchResult(
                    title="Python Async Tutorial",
                    url="https://example.com/tutorial",
                    snippet="Learn Python asyncio",
                    source="example.com",
                )
            ],
            total_results=1,
            search_time_ms=150,
            provider="DuckDuckGo",
        )

        with patch.object(manager, "_execute_enhanced_searches", return_value=mock_search_response):
            result = await manager.enhanced_search(
                "Python async programming",
                enhancement_mode=SearchEnhancementMode.FAST,
                max_results=3,
            )

        # Assertions
        assert result["query"] == "Python async programming"
        assert len(result["results"]) == 1
        assert result["results"][0].title == "Python Async Tutorial"
        assert "enhancement_details" in result
        assert result["provider"] == "DuckDuckGo"

    @pytest.mark.asyncio
    async def test_search_without_enhancement(self):
        """Test search workflow without AI enhancement"""
        config = {"search": {"enabled": True, "default_provider": "duckduckgo"}}

        manager = EnhancedSearchManager(config)  # No AI client

        # Mock single search execution
        mock_response = SearchResponse(
            query="test query",
            results=[
                SearchResult(
                    title="Test Result",
                    url="https://test.com",
                    snippet="Test snippet",
                    source="test.com",
                )
            ],
            total_results=1,
            search_time_ms=100,
            provider="DuckDuckGo",
        )

        with patch.object(manager, "_execute_single_search", return_value=mock_response):
            result = await manager.enhanced_search(
                "test query",
                enhancement_mode=SearchEnhancementMode.DISABLED
            )

        assert result["query"] == "test query"
        assert len(result["results"]) == 1
        assert result["results"][0].title == "Test Result"

    @pytest.mark.asyncio
    async def test_search_provider_availability(self):
        """Test search provider initialization"""
        config = {"search": {"enabled": True}}
        manager = EnhancedSearchManager(config)

        providers = manager.get_available_providers()
        assert "duckduckgo" in providers  # Always available

    @pytest.mark.asyncio
    async def test_memory_constraints_application(self):
        """Test that memory constraints are properly applied"""
        config = {"search": {"enabled": True, "default_provider": "duckduckgo"}}

        mock_ai_client = AsyncMock()
        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

        constraints = SearchMemoryConstraints(
            technical_level="expert",
            timeframe="recent",
            locale="en-US"
        )

        # Mock query enhancer to verify constraints are passed
        with patch.object(manager, "query_enhancer") as mock_enhancer:
            mock_plan = EnhancedSearchPlan(
                original_query="test query",
                enhanced_queries=[
                    EnhancedSearchQuery(
                        query="enhanced test query",
                        priority=1,
                        expected_results=5,
                        rationale="Expert level recent results"
                    )
                ],
                extraction_details={"keywords": [], "entities": []},
                enhancement_mode=SearchEnhancementMode.FAST,
                processing_time_ms=50,
                context_used=False,
            )
            mock_enhancer.enhance_query.return_value = mock_plan

            # Mock search execution
            with patch.object(manager, "_execute_enhanced_searches") as mock_execute:
                mock_execute.return_value = SearchResponse(
                    query="test query",
                    results=[],
                    total_results=0,
                    search_time_ms=0,
                    provider="DuckDuckGo"
                )

                await manager.enhanced_search(
                    "test query",
                    memory_constraints=constraints,
                    enhancement_mode=SearchEnhancementMode.FAST
                )

                # Verify constraints were passed to enhancer
                mock_enhancer.enhance_query.assert_called_once()
                call_args = mock_enhancer.enhance_query.call_args
                passed_constraints = call_args[1]["memory_constraints"]
                assert passed_constraints.technical_level == "expert"
                assert passed_constraints.timeframe == "recent"

    @pytest.mark.asyncio
    async def test_concurrent_search_execution(self):
        """Test concurrent execution with multiple queries"""
        config = {"search": {"enabled": True, "default_provider": "duckduckgo"}}

        mock_ai_client = AsyncMock()
        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

        # Create multiple enhanced queries
        enhanced_queries = [
            EnhancedSearchQuery(
                query="Python async tutorial",
                priority=1,
                expected_results=5,
                rationale="Main query"
            ),
            EnhancedSearchQuery(
                query="Python asyncio guide",
                priority=2,
                expected_results=3,
                rationale="Alternative query"
            ),
        ]

        mock_plan = EnhancedSearchPlan(
            original_query="Python async",
            enhanced_queries=enhanced_queries,
            extraction_details={"keywords": [], "entities": []},
            enhancement_mode=SearchEnhancementMode.FAST,
            processing_time_ms=75,
            context_used=False,
        )

        # Mock the enhancement process
        with patch.object(manager, "query_enhancer") as mock_enhancer:
            mock_enhancer.enhance_query.return_value = mock_plan

            # Mock search client responses
            mock_client = AsyncMock()
            responses = [
                SearchResponse(
                    query="Python async tutorial",
                    results=[SearchResult(title="Tutorial", url="https://tutorial.com", snippet="Tutorial", source="tutorial.com")],
                    total_results=1,
                    search_time_ms=100,
                    provider="DuckDuckGo"
                ),
                SearchResponse(
                    query="Python asyncio guide",
                    results=[SearchResult(title="Guide", url="https://guide.com", snippet="Guide", source="guide.com")],
                    total_results=1,
                    search_time_ms=120,
                    provider="DuckDuckGo"
                )
            ]
            mock_client.search.side_effect = responses
            manager.providers["duckduckgo"] = mock_client

            result = await manager.enhanced_search(
                "Python async",
                enhancement_mode=SearchEnhancementMode.FAST,
                max_results=5
            )

        # Should have results from concurrent execution
        assert result["query"] == "Python async"
        assert len(result["results"]) == 2
        titles = [r.title for r in result["results"]]
        assert "Tutorial" in titles
        assert "Guide" in titles
