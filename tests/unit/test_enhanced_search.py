"""Tests for enhanced search functionality"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nova.search.enhancement.extractors import (
    KeywordExtractor, ExtractionConfig, KeywordResult
)
from nova.search.enhancement.classifier import TermClassifier
from nova.search.enhancement.enhancer import QueryEnhancer
from nova.search.manager import EnhancedSearchManager
from nova.search.models import (
    SearchEnhancementMode, SearchMemoryConstraints, 
    TermClassification, EnhancedSearchPlan
)


class TestKeywordExtractor:
    """Test keyword extraction functionality"""

    def test_extractor_initialization(self):
        """Test that extractor initializes correctly"""
        config = ExtractionConfig()
        extractor = KeywordExtractor(config)
        
        assert extractor.config.backend.value == "yake_only"
        assert extractor.config.yake_max_keywords == 10

    def test_yake_extraction(self):
        """Test YAKE keyword extraction"""
        extractor = KeywordExtractor()
        keywords = extractor.extract_keywords("Python async programming best practices")
        
        assert len(keywords) > 0
        assert all(isinstance(kw, KeywordResult) for kw in keywords)
        assert all(kw.source == "yake" for kw in keywords)
        
        # Check that we have reasonable keywords
        keyword_texts = [kw.keyword for kw in keywords]
        assert any("python" in kw.lower() for kw in keyword_texts)

    def test_entity_extraction(self):
        """Test named entity extraction"""
        extractor = KeywordExtractor()
        entities = extractor.extract_entities("Apple Inc. and Microsoft are competing in AI")
        
        # Note: This test might vary depending on spaCy model availability
        # Just check that it returns a list
        assert isinstance(entities, list)

    def test_performance_info(self):
        """Test performance information retrieval"""
        extractor = KeywordExtractor()
        info = extractor.get_performance_info()
        
        assert "backend" in info
        assert "spacy_available" in info
        assert "keybert_available" in info


class TestTermClassifier:
    """Test term classification functionality"""

    def test_classifier_initialization(self):
        """Test that classifier initializes correctly"""
        classifier = TermClassifier()
        assert len(classifier.technical_keywords) > 0
        assert len(classifier.stop_words) > 0

    def test_classify_terms(self):
        """Test term classification"""
        classifier = TermClassifier()
        
        # Create mock keywords
        keywords = [
            KeywordResult(keyword="python", score=0.9, type="technical", source="yake"),
            KeywordResult(keyword="async programming", score=0.8, type="technical", source="yake"),
            KeywordResult(keyword="best practices", score=0.6, type="general", source="yake"),
            KeywordResult(keyword="tutorial", score=0.3, type="general", source="yake"),
        ]
        
        entities = ["Python", "AsyncIO"]
        original_query = "Python async programming tutorial"
        
        classification = classifier.classify_terms(keywords, entities, original_query)
        
        assert isinstance(classification, TermClassification)
        assert len(classification.must_have_terms) > 0
        assert len(classification.entities) > 0
        
        # Technical terms should be in must-have
        assert any("python" in term for term in classification.must_have_terms)

    def test_prioritize_terms(self):
        """Test term prioritization"""
        classifier = TermClassifier()
        
        classification = TermClassification(
            must_have_terms=["python", "async", "programming"],
            nice_to_have_terms=["tutorial", "guide", "example"],
            entities=["Python"],
            technical_terms=["async", "programming"]
        )
        
        prioritized = classifier.prioritize_terms(classification, max_terms=5)
        
        assert "must_have" in prioritized
        assert "nice_to_have" in prioritized
        assert len(prioritized["must_have"]) <= 3  # max_terms // 2 + 1
        assert len(prioritized["nice_to_have"]) <= 5  # remaining slots

    def test_search_variations(self):
        """Test search query variations generation"""
        classifier = TermClassifier()
        
        classification = TermClassification(
            must_have_terms=["python", "async", "programming"],
            nice_to_have_terms=["best", "practices"],
            entities=["Python"],
            technical_terms=["async"]
        )
        
        variations = classifier.generate_search_variations(classification, max_variations=3)
        
        assert isinstance(variations, list)
        assert len(variations) <= 3
        assert all(isinstance(var, str) for var in variations)
        assert any("python" in var.lower() for var in variations)


class TestQueryEnhancer:
    """Test query enhancement pipeline"""

    @pytest.mark.asyncio
    async def test_enhancer_without_ai(self):
        """Test query enhancement without AI client"""
        enhancer = QueryEnhancer()
        
        plan = await enhancer.enhance_query(
            "Python async programming",
            enhancement_mode=SearchEnhancementMode.FAST
        )
        
        assert isinstance(plan, EnhancedSearchPlan)
        assert plan.original_query == "Python async programming"
        assert plan.enhancement_mode == SearchEnhancementMode.FAST
        assert len(plan.enhanced_queries) > 0
        assert plan.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_enhancer_with_context(self):
        """Test query enhancement with conversation context"""
        enhancer = QueryEnhancer()
        
        plan = await enhancer.enhance_query(
            "best practices",
            conversation_context="We were discussing Python async programming earlier.",
            enhancement_mode=SearchEnhancementMode.FAST
        )
        
        assert isinstance(plan, EnhancedSearchPlan)
        assert plan.context_used == True

    @pytest.mark.asyncio
    async def test_enhancer_disabled_mode(self):
        """Test enhancement in disabled mode"""
        enhancer = QueryEnhancer()
        
        plan = await enhancer.enhance_query(
            "test query",
            enhancement_mode=SearchEnhancementMode.DISABLED
        )
        
        # Should still return a plan but with minimal processing
        assert isinstance(plan, EnhancedSearchPlan)
        assert len(plan.enhanced_queries) > 0
        # First query should be the original
        assert plan.enhanced_queries[0].query == "test query"

    @pytest.mark.asyncio
    async def test_enhancer_with_mock_ai(self):
        """Test query enhancement with mocked AI client"""
        mock_ai_client = AsyncMock()
        mock_ai_client.generate_response = AsyncMock(return_value="""[
            {
                "query": "enhanced test query",
                "priority": 1,
                "expected_results": 10,
                "rationale": "Enhanced version"
            }
        ]""")
        
        enhancer = QueryEnhancer(ai_client=mock_ai_client)
        
        plan = await enhancer.enhance_query(
            "test query",
            enhancement_mode=SearchEnhancementMode.FAST
        )
        
        assert isinstance(plan, EnhancedSearchPlan)
        assert len(plan.enhanced_queries) > 0
        
        # Should have called AI client
        mock_ai_client.generate_response.assert_called_once()

    def test_cache_functionality(self):
        """Test enhancement caching"""
        enhancer = QueryEnhancer()
        
        # Clear cache and check stats
        enhancer.clear_cache()
        stats = enhancer.get_cache_stats()
        
        assert "cached_queries" in stats
        assert stats["cached_queries"] == 0


class TestEnhancedSearchManager:
    """Test enhanced search manager"""

    def test_manager_initialization(self):
        """Test manager initialization"""
        config = {
            "search": {
                "enabled": True,
                "default_provider": "duckduckgo",
                "default_enhancement": "fast"
            }
        }
        
        manager = EnhancedSearchManager(config)
        
        assert len(manager.providers) > 0
        assert "duckduckgo" in manager.providers

    def test_manager_with_ai_client(self):
        """Test manager with AI client"""
        config = {
            "search": {
                "enabled": True,
                "default_enhancement": "fast",
                "extraction_backend": "yake_only"
            }
        }
        
        mock_ai_client = MagicMock()
        manager = EnhancedSearchManager(config, ai_client=mock_ai_client)
        
        assert manager.ai_client is mock_ai_client
        assert manager.query_enhancer is not None

    @pytest.mark.asyncio
    async def test_enhanced_search_disabled_mode(self):
        """Test enhanced search in disabled mode"""
        config = {"search": {}}
        
        with patch('nova.search.manager.DuckDuckGoSearchClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=MagicMock(
                results=[],
                total_results=0,
                search_time_ms=100,
                provider="DuckDuckGo"
            ))
            mock_client_class.return_value = mock_client
            
            manager = EnhancedSearchManager(config)
            
            result = await manager.enhanced_search(
                "test query",
                enhancement_mode=SearchEnhancementMode.DISABLED
            )
            
            assert "query" in result
            assert "results" in result
            assert result["query"] == "test query"

    def test_get_available_providers(self):
        """Test getting available providers"""
        config = {"search": {}}
        manager = EnhancedSearchManager(config)
        
        providers = manager.get_available_providers()
        assert isinstance(providers, list)
        assert "duckduckgo" in providers


class TestSearchMemoryConstraints:
    """Test search memory constraints"""

    def test_constraints_creation(self):
        """Test creating memory constraints"""
        constraints = SearchMemoryConstraints(
            technical_level="expert",
            timeframe="recent",
            locale="en-US"
        )
        
        assert constraints.technical_level == "expert"
        assert constraints.timeframe == "recent"
        assert constraints.locale == "en-US"

    def test_constraints_defaults(self):
        """Test default constraint values"""
        constraints = SearchMemoryConstraints()
        
        assert constraints.technical_level == "intermediate"
        assert constraints.timeframe == "any"
        assert constraints.locale == "en-US"


class TestSearchEnhancementModes:
    """Test search enhancement mode enum"""

    def test_mode_values(self):
        """Test that all expected modes exist"""
        expected_modes = ["auto", "disabled", "fast", "semantic", "hybrid", "adaptive"]
        
        for mode in expected_modes:
            # Should not raise exception
            SearchEnhancementMode(mode)

    def test_mode_conversion(self):
        """Test converting strings to modes"""
        mode = SearchEnhancementMode("fast")
        assert mode == SearchEnhancementMode.FAST
        assert mode.value == "fast"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])