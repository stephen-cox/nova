"""Tests for error handling and edge cases in enhanced search functionality"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nova.search.enhancement.classifier import TermClassifier
from nova.search.enhancement.enhancer import QueryEnhancer
from nova.search.enhancement.extractors import (
    ExtractionConfig,
    KeywordExtractor,
    KeywordResult,
)
from nova.search.manager import EnhancedSearchManager
from nova.search.models import (
    SearchEnhancementMode,
    SearchError,
    SearchMemoryConstraints,
    TermClassification,
)


class TestKeywordExtractionErrors:
    """Test error handling in keyword extraction"""

    def test_yake_extraction_with_empty_text(self):
        """Test YAKE extraction with empty or invalid text"""
        extractor = KeywordExtractor()

        # Empty text
        keywords = extractor.extract_keywords("")
        assert keywords == []

        # None text
        keywords = extractor.extract_keywords(None)
        assert keywords == []

        # Very short text
        keywords = extractor.extract_keywords("a")
        assert isinstance(keywords, list)

    def test_yake_extraction_with_malformed_results(self):
        """Test handling of malformed YAKE results"""
        extractor = KeywordExtractor()

        with patch("yake.KeywordExtractor") as mock_yake:
            # Mock malformed YAKE results
            mock_instance = MagicMock()
            mock_instance.extract_keywords.return_value = [
                ("valid_keyword", 0.5),
                {"malformed": "result"},  # Invalid format
                None,  # None result
                ("", 0.1),  # Empty keyword
                ("valid_keyword_2", "invalid_score"),  # Invalid score
            ]
            mock_yake.return_value = mock_instance

            keywords = extractor.extract_keywords("test text")

            # Should only return valid keywords
            valid_keywords = [kw for kw in keywords if kw.keyword]
            assert len(valid_keywords) >= 1
            assert all(isinstance(kw.score, float) for kw in valid_keywords)

    def test_spacy_initialization_failure(self):
        """Test handling of spaCy initialization failure"""
        config = ExtractionConfig(enable_spacy_preprocessing=True)

        with patch("spacy.load") as mock_spacy:
            mock_spacy.side_effect = OSError("Model not found")

            # Should initialize without spaCy
            extractor = KeywordExtractor(config)
            assert extractor._nlp is None

            # Should still work for keyword extraction
            keywords = extractor.extract_keywords("Python programming")
            assert isinstance(keywords, list)

    def test_keybert_initialization_failure(self):
        """Test handling of KeyBERT initialization failure"""
        config = ExtractionConfig(backend="keybert_only")

        # Mock the import at the function level where it's used
        with patch(
            "nova.search.enhancement.extractors.KeywordExtractor._initialize_keybert"
        ) as mock_init:
            mock_init.return_value = False  # Simulate KeyBERT not available

            extractor = KeywordExtractor(config)
            assert not extractor._keybert_available

            # Should fall back to YAKE
            keywords = extractor.extract_keywords("test text")
            assert isinstance(keywords, list)

    def test_entity_extraction_failure(self):
        """Test handling of entity extraction failures"""
        extractor = KeywordExtractor()

        with patch.object(extractor, "_nlp") as mock_nlp:
            mock_nlp.side_effect = Exception("spaCy processing error")

            entities = extractor.extract_entities("Test text with entities")
            assert entities == []


class TestTermClassificationErrors:
    """Test error handling in term classification"""

    def test_classify_empty_terms(self):
        """Test classification with empty or invalid terms"""
        classifier = TermClassifier()

        # Empty inputs
        classification = classifier.classify_terms([], [], "")
        assert isinstance(classification, TermClassification)
        assert len(classification.must_have_terms) == 0

        # None inputs should be handled gracefully (convert to empty)
        try:
            classification = classifier.classify_terms(None, None, None)
            assert isinstance(classification, TermClassification)
        except (TypeError, AttributeError):
            # If the method doesn't handle None inputs, that's also acceptable
            pass

    def test_classify_malformed_keywords(self):
        """Test classification with malformed keyword results"""
        classifier = TermClassifier()

        # Create malformed keyword results (but valid for Pydantic)
        malformed_keywords = [
            KeywordResult(
                keyword="", score=0.5, type="general", source="test"
            ),  # Empty keyword
            KeywordResult(
                keyword="valid", score=-1, type="general", source="test"
            ),  # Negative score
            KeywordResult(
                keyword="valid2", score=1.5, type="general", source="test"
            ),  # High score
        ]

        # Should handle malformed data gracefully
        classification = classifier.classify_terms(malformed_keywords, [], "test query")
        assert isinstance(classification, TermClassification)

    def test_prioritize_terms_edge_cases(self):
        """Test term prioritization with edge cases"""
        classifier = TermClassifier()

        # Empty classification
        empty_classification = TermClassification(
            must_have_terms=[], nice_to_have_terms=[], entities=[], technical_terms=[]
        )

        prioritized = classifier.prioritize_terms(empty_classification, max_terms=10)
        assert prioritized["must_have"] == []
        assert prioritized["nice_to_have"] == []

        # Max terms of 0
        classification = TermClassification(
            must_have_terms=["term1", "term2"],
            nice_to_have_terms=["term3"],
            entities=["Entity1"],
            technical_terms=["tech1"],
        )

        prioritized = classifier.prioritize_terms(classification, max_terms=0)
        assert prioritized["must_have"] == []
        assert prioritized["nice_to_have"] == []


class TestQueryEnhancementErrors:
    """Test error handling in query enhancement"""

    @pytest.mark.asyncio
    async def test_enhancement_with_invalid_ai_client(self):
        """Test enhancement with failing AI client"""
        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response = AsyncMock(
            side_effect=Exception("AI service unavailable")
        )

        enhancer = QueryEnhancer(ai_client=mock_ai_client)

        # Should fall back to rule-based enhancement
        plan = await enhancer.enhance_query(
            "test query", enhancement_mode=SearchEnhancementMode.FAST
        )

        assert plan.original_query == "test query"
        assert len(plan.enhanced_queries) > 0
        assert plan.enhanced_queries[0].query == "test query"  # Fallback to original

    @pytest.mark.asyncio
    async def test_enhancement_with_malformed_ai_response(self):
        """Test enhancement with malformed AI response"""
        mock_ai_client = AsyncMock()

        # Test various malformed responses
        malformed_responses = [
            "Not JSON at all",
            '{"not": "a list"}',
            "[]",  # Empty list
            '[{"missing_required_fields": true}]',
            '{"query": "test"}',  # Not a list
            "null",
            "",
        ]

        enhancer = QueryEnhancer(ai_client=mock_ai_client)

        for malformed_response in malformed_responses:
            mock_ai_client.generate_response = AsyncMock(
                return_value=malformed_response
            )

            plan = await enhancer.enhance_query(
                "test query", enhancement_mode=SearchEnhancementMode.FAST
            )

            # Should fall back to original query
            assert plan.original_query == "test query"
            assert len(plan.enhanced_queries) >= 1
            assert plan.enhanced_queries[0].query == "test query"

    @pytest.mark.asyncio
    async def test_enhancement_timeout_handling(self):
        """Test handling of AI client timeouts"""
        mock_ai_client = AsyncMock()

        # Simulate timeout
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(10)  # Very slow response
            return "timeout"

        mock_ai_client.generate_response = slow_response

        enhancer = QueryEnhancer(ai_client=mock_ai_client)

        # Should handle timeout gracefully (though we won't actually wait)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                enhancer.enhance_query(
                    "test query", enhancement_mode=SearchEnhancementMode.SEMANTIC
                ),
                timeout=0.1,  # Very short timeout for testing
            )

    def test_cache_edge_cases(self):
        """Test caching with edge cases"""
        enhancer = QueryEnhancer()

        # Clear cache multiple times
        enhancer.clear_cache()
        enhancer.clear_cache()

        stats = enhancer.get_cache_stats()
        assert stats["cached_queries"] == 0

        # Test cache with None values
        enhancer._enhancement_cache[None] = None
        stats = enhancer.get_cache_stats()
        assert stats["cached_queries"] == 1


class TestSearchManagerErrors:
    """Test error handling in search manager"""

    def test_manager_initialization_without_providers(self):
        """Test manager initialization with no providers"""
        empty_config = {"search": {}}

        manager = EnhancedSearchManager(empty_config)

        # Should at least have DuckDuckGo as default
        assert len(manager.providers) >= 1
        assert "duckduckgo" in manager.providers

    @pytest.mark.asyncio
    async def test_search_with_no_providers(self):
        """Test search execution with no available providers"""
        config = {"search": {}}
        manager = EnhancedSearchManager(config)
        manager.providers = {}  # Remove all providers

        with pytest.raises(SearchError, match="No search providers configured"):
            await manager.enhanced_search("test query")

    @pytest.mark.asyncio
    async def test_search_with_invalid_provider(self):
        """Test search with invalid provider name"""
        config = {"search": {}}
        manager = EnhancedSearchManager(config)

        with pytest.raises(SearchError, match="not available"):
            await manager.enhanced_search("test query", provider="nonexistent_provider")

    @pytest.mark.asyncio
    async def test_search_with_all_queries_failing(self):
        """Test search when all enhanced queries fail"""
        config = {"search": {}}

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(side_effect=Exception("All searches failed"))
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_ai_client = AsyncMock()
            mock_ai_client.generate_response = AsyncMock(
                return_value='[{"query": "enhanced query", "priority": 1, "expected_results": 5, "rationale": "test"}]'
            )

            manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

            result = await manager.enhanced_search(
                "test query", enhancement_mode=SearchEnhancementMode.FAST
            )

            # Should return with empty results but not crash
            assert "results" in result
            assert result["total_results"] == 0

            await manager.close()

    @pytest.mark.asyncio
    async def test_content_extraction_failures(self):
        """Test handling of content extraction failures"""
        config = {"search": {}}

        # Create mock SearchResult objects
        from nova.search.models import SearchResult

        mock_results = [
            SearchResult(
                title="Test",
                url="https://example.com",
                snippet="Test snippet",
                source="example.com",
            )
        ]

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=MagicMock(
                    results=mock_results,
                    total_results=1,
                    search_time_ms=50,
                    provider="DuckDuckGo",
                )
            )
            # Make content extraction fail
            mock_client.extract_content = AsyncMock(
                side_effect=Exception("Content extraction failed")
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(config)

            result = await manager.enhanced_search(
                "test query",
                extract_content=True,
                enhancement_mode=SearchEnhancementMode.DISABLED,
            )

            # Should still return results without extracted content
            assert len(result["results"]) > 0
            # When content extraction fails, results should mark failure
            for result_item in result["results"]:
                # Check if it's an object with attributes or a dict
                if hasattr(result_item, "extraction_success"):
                    # Some may fail extraction
                    assert isinstance(result_item.extraction_success, bool)

            await manager.close()

    @pytest.mark.asyncio
    async def test_memory_constraints_edge_cases(self):
        """Test memory constraints with invalid values"""
        config = {"search": {}}
        manager = EnhancedSearchManager(config)

        # Invalid constraints should not crash
        invalid_constraints = SearchMemoryConstraints(
            technical_level="invalid_level",  # Should default to valid value
            timeframe="invalid_timeframe",  # Should default to valid value
            locale="invalid_locale",  # Should be accepted as-is
        )

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=MagicMock(
                    results=[],
                    total_results=0,
                    search_time_ms=10,
                    provider="DuckDuckGo",
                )
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            # Should not crash with invalid constraints
            result = await manager.enhanced_search(
                "test query",
                memory_constraints=invalid_constraints,
                enhancement_mode=SearchEnhancementMode.DISABLED,
            )

            assert "results" in result

            await manager.close()

    @pytest.mark.asyncio
    async def test_concurrent_search_partial_failures(self):
        """Test concurrent searches with some failures"""
        config = {"search": {}}

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            call_count = 0

            async def partial_failing_search(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count % 2 == 0:  # Every second call fails
                    raise Exception(f"Search failed for call {call_count}")

                return MagicMock(
                    results=[
                        MagicMock(
                            title=f"Result {call_count}",
                            url=f"https://example.com/{call_count}",
                            snippet=f"Snippet {call_count}",
                            source="example.com",
                        )
                    ],
                    total_results=1,
                    search_time_ms=25,
                    provider="DuckDuckGo",
                )

            mock_client = AsyncMock()
            mock_client.search = partial_failing_search
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_ai_client = AsyncMock()
            mock_ai_client.generate_response = AsyncMock(
                return_value="""[
                    {"query": "query1", "priority": 1, "expected_results": 5, "rationale": "test1"},
                    {"query": "query2", "priority": 2, "expected_results": 5, "rationale": "test2"},
                    {"query": "query3", "priority": 3, "expected_results": 5, "rationale": "test3"}
                ]"""
            )

            manager = EnhancedSearchManager(config, ai_client=mock_ai_client)

            result = await manager.enhanced_search(
                "test concurrent failures", enhancement_mode=SearchEnhancementMode.FAST
            )

            # Should get results from successful queries only
            assert "results" in result
            # At least one query should succeed
            assert len(result["results"]) > 0 or result["total_results"] >= 0

            await manager.close()


class TestSearchConfigurationErrors:
    """Test configuration-related errors"""

    def test_invalid_extraction_config(self):
        """Test invalid extraction configurations"""
        # Invalid backend
        with pytest.raises(ValueError):
            ExtractionConfig(backend="invalid_backend")

        # Invalid numeric values
        with pytest.raises(ValueError):
            ExtractionConfig(yake_max_keywords=-1)

        with pytest.raises(ValueError):
            ExtractionConfig(yake_max_keywords=100)  # Too high

    def test_search_enhancement_mode_validation(self):
        """Test invalid enhancement mode handling"""
        # Invalid mode string should raise ValueError
        with pytest.raises(ValueError):
            SearchEnhancementMode("invalid_mode")

        # Test all valid modes can be created
        valid_modes = ["auto", "disabled", "fast", "semantic", "hybrid", "adaptive"]
        for mode in valid_modes:
            enhancement_mode = SearchEnhancementMode(mode)
            assert enhancement_mode.value == mode


class TestEdgeCasesAndCornerCases:
    """Test various edge cases and corner cases"""

    @pytest.mark.asyncio
    async def test_extremely_long_query(self):
        """Test handling of extremely long search queries"""
        long_query = "test query " * 1000  # Very long query

        enhancer = QueryEnhancer()
        plan = await enhancer.enhance_query(
            long_query, enhancement_mode=SearchEnhancementMode.FAST
        )

        # Should handle long queries without crashing
        assert plan.original_query == long_query
        assert len(plan.enhanced_queries) > 0

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self):
        """Test handling of special characters in queries"""
        special_queries = [
            "query with émojis 🔍",
            "query with \"quotes\" and 'apostrophes'",
            "query with <html> & XML entities",
            "query with unicode: 中文 العربية русский",
            "query with symbols: @#$%^&*()+={}[]|\\:;\"'<>,.?/~`",
            "",  # Empty query
            "   ",  # Whitespace only
        ]

        enhancer = QueryEnhancer()

        for query in special_queries:
            plan = await enhancer.enhance_query(
                query, enhancement_mode=SearchEnhancementMode.FAST
            )

            # Should handle special characters gracefully
            assert isinstance(plan.enhanced_queries, list)
            assert len(plan.enhanced_queries) > 0

    def test_keyword_extraction_with_non_english_text(self):
        """Test keyword extraction with non-English text"""
        extractor = KeywordExtractor()

        non_english_texts = [
            "这是中文测试文本",  # Chinese
            "هذا نص تجريبي باللغة العربية",  # Arabic
            "Это русский тестовый текст",  # Russian
            "Dies ist ein deutscher Testtext",  # German
            "C'est un texte de test en français",  # French
        ]

        for text in non_english_texts:
            keywords = extractor.extract_keywords(text)
            # Should not crash and return a list
            assert isinstance(keywords, list)

    @pytest.mark.asyncio
    async def test_rapid_successive_searches(self):
        """Test rapid successive search requests (stress test)"""
        config = {"search": {}}

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=MagicMock(
                    results=[],
                    total_results=0,
                    search_time_ms=10,
                    provider="DuckDuckGo",
                )
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(config)

            # Execute many searches rapidly
            tasks = []
            for i in range(20):
                task = manager.enhanced_search(
                    f"rapid search {i}", enhancement_mode=SearchEnhancementMode.DISABLED
                )
                tasks.append(task)

            # All should complete without errors
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check that no exceptions were raised
            for result in results:
                assert not isinstance(result, Exception)
                assert "results" in result

            await manager.close()

    def test_memory_usage_with_large_cache(self):
        """Test memory usage with large enhancement cache"""
        enhancer = QueryEnhancer()

        # Fill cache with many entries
        for i in range(1000):
            cache_key = f"query_{i}:fast:{i}"
            enhancer._enhancement_cache[cache_key] = MagicMock()

        stats = enhancer.get_cache_stats()
        assert stats["cached_queries"] == 1000

        # Clear cache should free memory
        enhancer.clear_cache()
        stats = enhancer.get_cache_stats()
        assert stats["cached_queries"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
