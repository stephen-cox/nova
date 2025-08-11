"""Integration tests for enhanced search functionality"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nova.search.manager import EnhancedSearchManager
from nova.search.models import (
    SearchEnhancementMode,
    SearchMemoryConstraints,
    SearchResponse,
    SearchResult,
)
from nova.tools.built_in.web_search import web_search


class TestEnhancedSearchIntegration:
    """Test complete enhanced search pipeline integration"""

    @pytest.fixture
    def mock_search_config(self):
        """Mock search configuration"""
        return {
            "search": {
                "enabled": True,
                "default_provider": "duckduckgo",
                "max_results": 5,
                "default_enhancement": "fast",
                "enable_conversation_context": True,
                "default_technical_level": "intermediate",
                "default_timeframe": "any",
                "performance_mode": True,
                "enhancement_cache_enabled": True,
                "extraction_backend": "yake_only",
                "yake_max_keywords": 10,
                "keybert_max_keywords": 6,
            }
        }

    @pytest.fixture
    def mock_ai_client(self):
        """Mock AI client for testing"""
        mock_client = AsyncMock()
        mock_client.generate_response = AsyncMock(
            return_value="""[
            {
                "query": "enhanced Python async programming tutorial",
                "priority": 1,
                "expected_results": 10,
                "rationale": "Focused on Python async programming with tutorial emphasis"
            },
            {
                "query": "asyncio Python concurrent programming guide",
                "priority": 2,
                "expected_results": 8,
                "rationale": "Alternative approach using asyncio terminology"
            }
        ]"""
        )
        return mock_client

    @pytest.fixture
    def mock_search_results(self):
        """Mock search results for testing"""
        return [
            SearchResult(
                title="Python Asyncio Tutorial",
                url="https://example.com/asyncio-tutorial",
                snippet="Complete guide to Python async programming",
                source="example.com",
                content_summary="Detailed tutorial covering asyncio fundamentals",
                extraction_success=True,
            ),
            SearchResult(
                title="Advanced Async Patterns",
                url="https://example.com/async-patterns",
                snippet="Advanced patterns for async Python development",
                source="example.com",
                content_summary="In-depth coverage of async design patterns",
                extraction_success=True,
            ),
        ]

    @pytest.mark.asyncio
    async def test_complete_enhancement_pipeline(
        self, mock_ai_client, mock_search_config, mock_search_results
    ):
        """Test complete enhancement pipeline from query to results"""

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            # Mock search client
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=SearchResponse(
                    query="test query",
                    results=mock_search_results,
                    total_results=len(mock_search_results),
                    search_time_ms=100,
                    provider="DuckDuckGo",
                )
            )
            mock_client.extract_content = AsyncMock(
                return_value=("Sample content for testing", True)
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            # Create enhanced search manager
            manager = EnhancedSearchManager(
                mock_search_config, ai_client=mock_ai_client
            )

            # Execute enhanced search
            result = await manager.enhanced_search(
                query="Python async programming tutorial",
                enhancement_mode=SearchEnhancementMode.FAST,
                conversation_context="We were discussing Python development",
                memory_constraints=SearchMemoryConstraints(),
                max_results=5,
                extract_content=True,
            )

            # Verify results structure
            assert "query" in result
            assert "results" in result
            assert "enhancement_details" in result
            assert result["query"] == "Python async programming tutorial"
            assert len(result["results"]) > 0

            # Verify enhancement details
            enhancement = result["enhancement_details"]
            assert enhancement["mode"] == SearchEnhancementMode.FAST
            assert enhancement["context_used"] is True
            assert enhancement["processing_time_ms"] > 0
            assert len(enhancement["enhanced_queries"]) > 0

            # Verify AI client was called for enhancement
            mock_ai_client.generate_response.assert_called()

            await manager.close()

    @pytest.mark.asyncio
    async def test_disabled_enhancement_mode(
        self, mock_ai_client, mock_search_config, mock_search_results
    ):
        """Test search with enhancement disabled"""

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            # Mock search client
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=SearchResponse(
                    query="test query",
                    results=mock_search_results,
                    total_results=len(mock_search_results),
                    search_time_ms=50,
                    provider="DuckDuckGo",
                )
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(
                mock_search_config, ai_client=mock_ai_client
            )

            result = await manager.enhanced_search(
                query="simple search query",
                enhancement_mode=SearchEnhancementMode.DISABLED,
                max_results=3,
            )

            # Enhancement should not be used
            assert "enhancement_details" not in result
            assert result["query"] == "simple search query"

            # AI client should not be called for enhancement
            mock_ai_client.generate_response.assert_not_called()

            await manager.close()

    @pytest.mark.asyncio
    async def test_fallback_when_ai_fails(
        self, mock_ai_client, mock_search_config, mock_search_results
    ):
        """Test fallback to rule-based enhancement when AI fails"""

        # Make AI client fail
        mock_ai_client.generate_response = AsyncMock(
            side_effect=Exception("AI service unavailable")
        )

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=SearchResponse(
                    query="test query",
                    results=mock_search_results,
                    total_results=len(mock_search_results),
                    search_time_ms=75,
                    provider="DuckDuckGo",
                )
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(
                mock_search_config, ai_client=mock_ai_client
            )

            result = await manager.enhanced_search(
                query="Python async programming",
                enhancement_mode=SearchEnhancementMode.FAST,
                max_results=3,
            )

            # Should still get results via fallback
            assert "results" in result
            assert len(result["results"]) > 0
            assert (
                "enhancement_details" in result
            )  # Rule-based fallback still provides enhancement

            await manager.close()

    @pytest.mark.asyncio
    async def test_concurrent_search_execution(
        self, mock_ai_client, mock_search_config, mock_search_results
    ):
        """Test concurrent execution of multiple enhanced queries"""

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            # Track call count for concurrent execution
            call_count = 0

            async def mock_search_with_delay(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.01)  # Small delay to simulate real search
                return SearchResponse(
                    query=f"query_{call_count}",
                    results=mock_search_results[:1],  # Return 1 result per query
                    total_results=1,
                    search_time_ms=20,
                    provider="DuckDuckGo",
                )

            mock_client = AsyncMock()
            mock_client.search = mock_search_with_delay
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(
                mock_search_config, ai_client=mock_ai_client
            )

            start_time = asyncio.get_event_loop().time()
            result = await manager.enhanced_search(
                query="concurrent search test",
                enhancement_mode=SearchEnhancementMode.FAST,
                max_results=6,
            )
            end_time = asyncio.get_event_loop().time()

            # Should execute multiple queries concurrently
            assert call_count >= 2  # AI should generate multiple enhanced queries
            assert len(result["results"]) > 0

            # Should be faster than sequential execution (rough check)
            execution_time = end_time - start_time
            assert execution_time < 0.5  # Should be much faster than sequential

            await manager.close()

    @pytest.mark.asyncio
    async def test_content_extraction_and_summarization(
        self, mock_ai_client, mock_search_config, mock_search_results
    ):
        """Test content extraction and AI summarization"""

        # Mock AI client to return summaries
        def mock_ai_response(messages):
            if "summarize" in messages[1]["content"].lower():
                return "AI-generated summary of the content"
            return """[{"query": "enhanced query", "priority": 1, "expected_results": 5, "rationale": "enhanced"}]"""

        mock_ai_client.generate_response = AsyncMock(side_effect=mock_ai_response)

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(
                return_value=SearchResponse(
                    query="test query",
                    results=mock_search_results,
                    total_results=len(mock_search_results),
                    search_time_ms=100,
                    provider="DuckDuckGo",
                )
            )
            mock_client.extract_content = AsyncMock(
                return_value=("Detailed content for summarization", True)
            )
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(
                mock_search_config, ai_client=mock_ai_client
            )

            await manager.enhanced_search(
                query="test content extraction",
                extract_content=True,
                enhancement_mode=SearchEnhancementMode.FAST,
                max_results=2,
            )

            # Verify content extraction occurred
            mock_client.extract_content.assert_called()

            # Verify AI summarization was attempted
            assert (
                mock_ai_client.generate_response.call_count >= 2
            )  # Enhancement + summarization

            await manager.close()

    @pytest.mark.asyncio
    async def test_multiple_provider_handling(self, mock_ai_client, mock_search_config):
        """Test handling multiple search providers"""

        # Add multiple providers to config
        mock_search_config["search"]["google"] = {
            "api_key": "test_key",
            "search_engine_id": "test_id",
        }
        mock_search_config["search"]["bing"] = {"api_key": "test_bing_key"}

        with (
            patch("nova.search.engines.DuckDuckGoSearchClient"),
            patch("nova.search.engines.GoogleSearchClient") as mock_google_class,
            patch("nova.search.engines.BingSearchClient") as mock_bing_class,
        ):
            # Mock all providers
            for mock_class in [mock_google_class, mock_bing_class]:
                mock_client = AsyncMock()
                mock_client.close = AsyncMock()
                mock_class.return_value = mock_client

            manager = EnhancedSearchManager(
                mock_search_config, ai_client=mock_ai_client
            )

            # Should initialize all configured providers
            assert len(manager.providers) == 3  # DuckDuckGo + Google + Bing
            assert "duckduckgo" in manager.providers
            assert "google" in manager.providers
            assert "bing" in manager.providers

            await manager.close()

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(
        self, mock_ai_client, mock_search_config, mock_search_results
    ):
        """Test error handling and graceful recovery"""

        with patch("nova.search.engines.DuckDuckGoSearchClient") as mock_client_class:
            # Make first search fail, second succeed
            call_count = 0

            async def failing_search(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Search API error")
                return SearchResponse(
                    query="recovery query",
                    results=mock_search_results,
                    total_results=len(mock_search_results),
                    search_time_ms=50,
                    provider="DuckDuckGo",
                )

            mock_client = AsyncMock()
            mock_client.search = failing_search
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = EnhancedSearchManager(
                mock_search_config, ai_client=mock_ai_client
            )

            # Should handle partial failures gracefully
            result = await manager.enhanced_search(
                query="error handling test",
                enhancement_mode=SearchEnhancementMode.FAST,
                max_results=5,
            )

            # Should still return results from successful queries
            assert "results" in result
            assert len(result["results"]) >= 0  # May be empty or partial

            await manager.close()


class TestWebSearchToolIntegration:
    """Integration tests for web_search tool"""

    @pytest.mark.asyncio
    async def test_web_search_tool_with_enhancement(self):
        """Test web_search tool with enhancement enabled"""

        with patch("nova.core.config.config_manager.load_config") as mock_config:
            # Mock configuration
            mock_config_obj = MagicMock()
            mock_config_obj.search.default_enhancement = "fast"
            mock_config_obj.search.default_provider = "duckduckgo"
            mock_config_obj.search.max_results = 5
            mock_config_obj.search.default_timeframe = "any"
            mock_config_obj.search.default_technical_level = "intermediate"
            mock_config_obj.get_active_ai_config.return_value = {}
            mock_config.return_value = mock_config_obj

            with patch(
                "nova.search.manager.EnhancedSearchManager"
            ) as mock_manager_class:
                # Mock search manager
                mock_manager = AsyncMock()
                mock_manager.enhanced_search = AsyncMock(
                    return_value={
                        "query": "test query",
                        "provider": "duckduckgo",
                        "results": [
                            {
                                "title": "Test Result",
                                "url": "https://example.com",
                                "snippet": "Test snippet",
                                "source": "example.com",
                                "content_summary": "AI summary",
                            }
                        ],
                        "total_results": 1,
                        "search_time_ms": 100,
                        "enhancement_details": {
                            "mode": SearchEnhancementMode.FAST,
                            "processing_time_ms": 50,
                            "context_used": False,
                            "enhanced_queries": [
                                {
                                    "query": "enhanced test query",
                                    "priority": 1,
                                    "rationale": "Enhanced version",
                                }
                            ],
                        },
                    }
                )
                mock_manager.close = AsyncMock()
                mock_manager_class.return_value = mock_manager

                # Test the tool
                result = await web_search(
                    query="Python async programming",
                    enhancement="fast",
                    max_results=3,
                    include_content=True,
                )

                # Verify tool output structure
                assert "query" in result
                assert "provider" in result
                assert "results" in result
                assert "enhancement" in result

                # Verify enhancement details
                assert result["enhancement"]["mode"] == SearchEnhancementMode.FAST
                assert result["enhancement"]["processing_time_ms"] == 50
                assert len(result["enhancement"]["enhanced_queries"]) == 1

                # Verify manager was called correctly
                mock_manager.enhanced_search.assert_called_once()
                mock_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_web_search_tool_fallback(self):
        """Test web_search tool fallback when search manager fails"""

        with patch("nova.core.config.config_manager.load_config") as mock_config:
            mock_config.side_effect = Exception("Config error")

            # Should fall back gracefully
            result = await web_search(
                query="fallback test", enhancement="disabled", max_results=3
            )

            # Should return fallback result
            assert result["provider"] == "fallback"
            assert "error" in result
            assert len(result["results"]) == 1
            assert "unavailable" in result["results"][0]["title"].lower()

    @pytest.mark.asyncio
    async def test_web_search_parameter_validation(self):
        """Test web_search tool parameter validation"""

        with patch("nova.core.config.config_manager.load_config") as mock_config:
            mock_config_obj = MagicMock()
            mock_config_obj.search.default_enhancement = "fast"
            mock_config_obj.search.default_provider = "duckduckgo"
            mock_config_obj.search.max_results = 10
            mock_config_obj.search.default_timeframe = "any"
            mock_config_obj.search.default_technical_level = "intermediate"
            mock_config_obj.get_active_ai_config.return_value = {}
            mock_config.return_value = mock_config_obj

            with patch(
                "nova.search.manager.EnhancedSearchManager"
            ) as mock_manager_class:
                mock_manager = AsyncMock()
                mock_manager.enhanced_search = AsyncMock(
                    return_value={
                        "query": "test",
                        "provider": "duckduckgo",
                        "results": [],
                        "total_results": 0,
                        "search_time_ms": 10,
                    }
                )
                mock_manager.close = AsyncMock()
                mock_manager_class.return_value = mock_manager

                # Test parameter validation and defaults
                await web_search(
                    query="validation test",
                    provider="invalid_provider",  # Should default to duckduckgo
                    max_results=100,  # Should be capped at 20
                    enhancement="invalid_mode",  # Should default to fast
                )

                # Verify call was made with corrected parameters
                call_args = mock_manager.enhanced_search.call_args
                assert call_args.kwargs["provider"] == "duckduckgo"
                assert call_args.kwargs["max_results"] == 20
                # Enhancement mode should be corrected to FAST
                assert (
                    call_args.kwargs["enhancement_mode"] == SearchEnhancementMode.FAST
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
