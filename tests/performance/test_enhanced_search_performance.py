"""Performance tests for enhanced search functionality"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nova.search.enhancement.enhancer import QueryEnhancer
from nova.search.enhancement.extractors import ExtractionConfig, KeywordExtractor
from nova.search.manager import EnhancedSearchManager
from nova.search.models import SearchEnhancementMode


class TestKeywordExtractionPerformance:
    """Performance tests for keyword extraction"""

    def test_yake_extraction_performance(self):
        """Test YAKE extraction performance with various text sizes"""
        extractor = KeywordExtractor(ExtractionConfig(backend="yake_only"))

        # Test with different text sizes
        test_texts = {
            "short": "Python programming tutorial",
            "medium": "Python is a high-level programming language. " * 50,
            "long": "Python is a versatile programming language used for web development, data science, machine learning, and automation. "
            * 200,
        }

        performance_results = {}

        for size, text in test_texts.items():
            start_time = time.time()
            keywords = extractor.extract_keywords(text, max_keywords=15)
            end_time = time.time()

            execution_time = (end_time - start_time) * 1000  # Convert to ms
            performance_results[size] = {
                "time_ms": execution_time,
                "keywords_count": len(keywords),
                "text_length": len(text),
            }

            # Performance assertions (adjusted based on actual performance)
            if size == "short":
                assert execution_time < 200  # Should be very fast for short text
            elif size == "medium":
                assert execution_time < 400  # Should still be fast for medium text
            elif size == "long":
                assert execution_time < 1000  # Should be reasonable for long text

            assert len(keywords) > 0

        # Verify performance scales reasonably
        assert (
            performance_results["short"]["time_ms"]
            <= performance_results["medium"]["time_ms"]
        )
        assert (
            performance_results["medium"]["time_ms"]
            <= performance_results["long"]["time_ms"] * 2
        )  # Shouldn't be drastically worse

    @pytest.mark.skipif(True, reason="KeyBERT requires additional dependencies")
    def test_keybert_extraction_performance(self):
        """Test KeyBERT extraction performance (requires keybert installation)"""
        try:
            config = ExtractionConfig(backend="keybert_only")
            extractor = KeywordExtractor(config)

            if not extractor._keybert_available:
                pytest.skip("KeyBERT not available")

            text = (
                "Machine learning and artificial intelligence in Python development. "
                * 20
            )

            start_time = time.time()
            keywords = extractor.extract_keywords(text, max_keywords=10)
            end_time = time.time()

            execution_time = (end_time - start_time) * 1000

            # KeyBERT should complete within reasonable time
            assert execution_time < 2000  # 2 seconds max for moderate text
            assert len(keywords) > 0

        except ImportError:
            pytest.skip("KeyBERT not installed")

    def test_hybrid_extraction_performance(self):
        """Test hybrid extraction performance"""
        config = ExtractionConfig(backend="hybrid")
        extractor = KeywordExtractor(config)

        text = (
            "Python web development using Django and Flask frameworks for scalable applications. "
            * 30
        )

        start_time = time.time()
        keywords = extractor.extract_keywords(text, max_keywords=12)
        end_time = time.time()

        execution_time = (end_time - start_time) * 1000

        # Hybrid mode might take longer but should be reasonable
        assert execution_time < 3000  # 3 seconds max
        assert len(keywords) > 0

    def test_extraction_caching_performance(self):
        """Test that repeated extractions benefit from caching"""
        extractor = KeywordExtractor()
        text = "Python async programming with asyncio and concurrent futures"

        # First extraction (uncached)
        start_time = time.time()
        keywords1 = extractor.extract_keywords(text)
        first_time = time.time() - start_time

        # Second extraction (may benefit from spaCy internal caching)
        start_time = time.time()
        keywords2 = extractor.extract_keywords(text)
        second_time = time.time() - start_time

        # Results should be consistent
        assert len(keywords1) == len(keywords2)

        # Second run should be same or faster (due to caching)
        assert second_time <= first_time * 1.2  # Allow 20% variance


class TestQueryEnhancementPerformance:
    """Performance tests for query enhancement"""

    @pytest.mark.asyncio
    async def test_enhancement_mode_performance_comparison(self):
        """Compare performance of different enhancement modes"""

        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response = AsyncMock(
            return_value='[{"query": "enhanced query", "priority": 1, "expected_results": 5, "rationale": "test"}]'
        )

        enhancer = QueryEnhancer(ai_client=mock_ai_client)
        query = "Python machine learning tutorial for beginners"

        performance_results = {}

        # Test each enhancement mode
        modes = [
            SearchEnhancementMode.DISABLED,
            SearchEnhancementMode.FAST,
            SearchEnhancementMode.SEMANTIC,
            SearchEnhancementMode.HYBRID,
        ]

        for mode in modes:
            start_time = time.time()

            plan = await enhancer.enhance_query(
                query,
                enhancement_mode=mode,
                conversation_context="Previous discussion about machine learning",
            )

            end_time = time.time()
            execution_time = (end_time - start_time) * 1000

            performance_results[mode.value] = {
                "time_ms": execution_time,
                "queries_count": len(plan.enhanced_queries),
                "processing_time_ms": plan.processing_time_ms,
            }

        # Performance expectations
        assert performance_results["disabled"]["time_ms"] < 50  # Should be very fast
        assert performance_results["fast"]["time_ms"] < 200  # Should be reasonably fast

        # Verify disabled is fastest
        disabled_time = performance_results["disabled"]["time_ms"]
        for mode in ["fast", "semantic", "hybrid"]:
            if mode in performance_results:
                assert performance_results[mode]["time_ms"] >= disabled_time

    @pytest.mark.asyncio
    async def test_enhancement_with_context_performance(self):
        """Test performance impact of conversation context"""

        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response = AsyncMock(
            return_value='[{"query": "enhanced query", "priority": 1, "expected_results": 5, "rationale": "test"}]'
        )

        enhancer = QueryEnhancer(ai_client=mock_ai_client)
        query = "best practices"

        # Test without context
        start_time = time.time()
        await enhancer.enhance_query(
            query,
            enhancement_mode=SearchEnhancementMode.FAST,
            conversation_context="",
        )
        time_no_context = (time.time() - start_time) * 1000

        # Test with context
        large_context = (
            "We discussed Python programming, web development, and database design. "
            * 100
        )

        start_time = time.time()
        plan_with_context = await enhancer.enhance_query(
            query,
            enhancement_mode=SearchEnhancementMode.FAST,
            conversation_context=large_context,
        )
        time_with_context = (time.time() - start_time) * 1000

        # Context processing should not significantly impact performance
        assert time_with_context <= time_no_context * 3  # Allow up to 3x overhead
        assert plan_with_context.context_used is True

    @pytest.mark.asyncio
    async def test_enhancement_caching_performance(self):
        """Test enhancement caching effectiveness"""

        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response = AsyncMock(
            return_value='[{"query": "cached query", "priority": 1, "expected_results": 5, "rationale": "cached"}]'
        )

        enhancer = QueryEnhancer(ai_client=mock_ai_client)
        query = "caching test query"
        context = "test context for caching"

        # First enhancement (uncached)
        start_time = time.time()
        plan1 = await enhancer.enhance_query(
            query,
            enhancement_mode=SearchEnhancementMode.FAST,
            conversation_context=context,
        )
        first_time = (time.time() - start_time) * 1000

        # Second enhancement (should be cached)
        start_time = time.time()
        plan2 = await enhancer.enhance_query(
            query,
            enhancement_mode=SearchEnhancementMode.FAST,
            conversation_context=context,
        )
        second_time = (time.time() - start_time) * 1000

        # Cached result should be much faster
        assert second_time < first_time * 0.5  # At least 50% faster
        assert plan1.enhanced_queries == plan2.enhanced_queries  # Same results

        # AI client should only be called once due to caching
        assert mock_ai_client.generate_response.call_count == 1


class TestSearchManagerPerformance:
    """Performance tests for search manager"""

    @pytest.mark.asyncio
    async def test_concurrent_search_performance(self):
        """Test performance of concurrent search execution"""

        config = {"search": {"default_provider": "duckduckgo"}}

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            # Mock search client with controlled delays
            async def mock_search_with_delay(query, max_results, **kwargs):
                await asyncio.sleep(0.1)  # Simulate network delay
                return MagicMock(
                    results=[
                        MagicMock(
                            title=f"Result for {query}",
                            url="https://example.com",
                            snippet="test",
                            source="test",
                        )
                    ],
                    total_results=1,
                    search_time_ms=100,
                    provider="DuckDuckGo",
                )

            mock_client = AsyncMock()
            mock_client.search = mock_search_with_delay
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock AI client for enhancement
            mock_ai_client = AsyncMock()
            mock_ai_client.generate_response = AsyncMock(
                return_value="""[
                    {"query": "query1", "priority": 1, "expected_results": 5, "rationale": "test1"},
                    {"query": "query2", "priority": 2, "expected_results": 5, "rationale": "test2"},
                    {"query": "query3", "priority": 3, "expected_results": 5, "rationale": "test3"}
                ]"""
            )

            manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

            # Test concurrent execution
            start_time = time.time()
            result = await manager.enhanced_search(
                "performance test query",
                enhancement_mode=SearchEnhancementMode.FAST,
                max_results=9,  # Will be distributed across 3 queries
            )
            end_time = time.time()

            total_time = (end_time - start_time) * 1000

            # With 3 concurrent queries of 0.1s each, total should be closer to 0.1s than 0.3s
            assert total_time < 300  # Should be much faster than sequential execution
            assert "results" in result

            await manager.close()

    @pytest.mark.asyncio
    async def test_search_with_content_extraction_performance(self):
        """Test performance impact of content extraction"""

        config = {"search": {}}

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            # Mock content extraction with delay
            async def mock_extract_content(url):
                await asyncio.sleep(0.05)  # Simulate content extraction delay
                return ("Extracted content for " + url, True)

            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=MagicMock(
                    results=[
                        MagicMock(
                            title="Test Result",
                            url=f"https://example.com/{i}",
                            snippet="test",
                            source="test",
                        )
                        for i in range(3)
                    ],
                    total_results=3,
                    search_time_ms=50,
                    provider="DuckDuckGo",
                )
            )
            mock_client.extract_content = mock_extract_content
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(config)

            # Test without content extraction
            start_time = time.time()
            await manager.enhanced_search(
                "performance test",
                extract_content=False,
                enhancement_mode=SearchEnhancementMode.DISABLED,
                max_results=3,
            )
            time_no_extraction = (time.time() - start_time) * 1000

            # Test with content extraction
            start_time = time.time()
            await manager.enhanced_search(
                "performance test",
                extract_content=True,
                enhancement_mode=SearchEnhancementMode.DISABLED,
                max_results=3,
            )
            time_with_extraction = (time.time() - start_time) * 1000

            # Content extraction should add some overhead but be concurrent
            assert time_with_extraction > time_no_extraction
            # But concurrent extraction should keep the total reasonable
            assert time_with_extraction < time_no_extraction + 200  # Max 200ms overhead

            await manager.close()

    @pytest.mark.asyncio
    async def test_large_result_set_performance(self):
        """Test performance with large result sets"""

        config = {"search": {}}

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            # Create many mock results
            large_results = [
                MagicMock(
                    title=f"Result {i}",
                    url=f"https://example.com/result/{i}",
                    snippet=f"This is result number {i} with some content",
                    source="example.com",
                    enhancement_priority=1,
                    enhancement_rationale="test",
                )
                for i in range(100)  # Large result set
            ]

            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=MagicMock(
                    results=large_results,
                    total_results=len(large_results),
                    search_time_ms=200,
                    provider="DuckDuckGo",
                )
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(config)

            start_time = time.time()
            result = await manager.enhanced_search(
                "large result test",
                enhancement_mode=SearchEnhancementMode.DISABLED,
                max_results=50,
            )
            end_time = time.time()

            processing_time = (end_time - start_time) * 1000

            # Should handle large result sets efficiently
            assert processing_time < 1000  # Under 1 second
            assert len(result["results"]) == 50  # Properly limited
            assert result["total_results"] == 50  # Correctly reported

            await manager.close()


class TestMemoryUsagePerformance:
    """Test memory usage patterns"""

    @pytest.mark.asyncio
    async def test_memory_cleanup_after_searches(self):
        """Test that memory is properly cleaned up after searches"""

        config = {"search": {}}

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=MagicMock(
                    results=[
                        MagicMock(
                            title="Test",
                            url="https://example.com",
                            snippet="test",
                            source="test",
                        )
                    ],
                    total_results=1,
                    search_time_ms=10,
                    provider="DuckDuckGo",
                )
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(config)

            # Perform many searches
            for i in range(50):
                await manager.enhanced_search(
                    f"memory test {i}",
                    enhancement_mode=SearchEnhancementMode.DISABLED,
                    max_results=1,
                )

            # Close manager should clean up resources
            await manager.close()

            # Verify cleanup was called
            mock_client.close.assert_called()

    def test_enhancement_cache_memory_management(self):
        """Test that enhancement cache doesn't grow unbounded"""

        enhancer = QueryEnhancer()

        # Add many items to cache
        for i in range(1000):
            cache_key = f"query_{i}:fast:context_{i}"
            enhancer._enhancement_cache[cache_key] = MagicMock()

        # Cache should have all items
        stats = enhancer.get_cache_stats()
        assert stats["cached_queries"] == 1000

        # Clear cache should free memory
        enhancer.clear_cache()
        stats = enhancer.get_cache_stats()
        assert stats["cached_queries"] == 0


class TestScalabilityTests:
    """Test scalability with increasing loads"""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_managers(self):
        """Test multiple search managers running concurrently"""

        config = {"search": {}}

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=MagicMock(
                    results=[
                        MagicMock(
                            title="Concurrent test",
                            url="https://example.com",
                            snippet="test",
                            source="test",
                        )
                    ],
                    total_results=1,
                    search_time_ms=50,
                    provider="DuckDuckGo",
                )
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            # Create multiple managers
            managers = [EnhancedSearchManager(config) for _ in range(10)]

            # Run searches concurrently across all managers
            search_tasks = []
            for i, manager in enumerate(managers):
                task = manager.enhanced_search(
                    f"concurrent manager test {i}",
                    enhancement_mode=SearchEnhancementMode.DISABLED,
                    max_results=1,
                )
                search_tasks.append(task)

            start_time = time.time()
            results = await asyncio.gather(*search_tasks)
            end_time = time.time()

            total_time = (end_time - start_time) * 1000

            # All searches should complete
            assert len(results) == 10
            for result in results:
                assert "results" in result

            # Should scale reasonably
            assert total_time < 2000  # Under 2 seconds for 10 concurrent managers

            # Clean up all managers
            cleanup_tasks = [manager.close() for manager in managers]
            await asyncio.gather(*cleanup_tasks)

    @pytest.mark.asyncio
    async def test_high_frequency_searches(self):
        """Test handling of high-frequency search requests"""

        config = {"search": {}}

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=MagicMock(
                    results=[
                        MagicMock(
                            title="Frequency test",
                            url="https://example.com",
                            snippet="test",
                            source="test",
                        )
                    ],
                    total_results=1,
                    search_time_ms=25,
                    provider="DuckDuckGo",
                )
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(config)

            # Create many rapid search requests
            search_tasks = []
            for i in range(100):  # 100 rapid searches
                task = manager.enhanced_search(
                    f"frequency test {i}",
                    enhancement_mode=SearchEnhancementMode.DISABLED,
                    max_results=1,
                )
                search_tasks.append(task)

            start_time = time.time()
            results = await asyncio.gather(*search_tasks, return_exceptions=True)
            end_time = time.time()

            total_time = (end_time - start_time) * 1000

            # All searches should complete without errors
            successful_results = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_results) == 100

            # Average time per search should be reasonable
            avg_time_per_search = total_time / 100
            assert avg_time_per_search < 100  # Under 100ms per search on average

            await manager.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
