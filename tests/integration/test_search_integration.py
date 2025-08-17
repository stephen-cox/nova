"""Integration tests for search functionality with real search providers"""

import pytest

from nova.search import SearchError, SearchManager
from nova.tools.built_in.web_search import web_search


class TestSearchIntegration:
    """Integration tests for search engines using real search providers"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_duckduckgo_real_search(self):
        """Test DuckDuckGo search returns real results"""
        config = {}
        manager = SearchManager(config)

        try:
            response = await manager.search(
                "Python programming", provider="duckduckgo", max_results=3
            )

            # Verify response structure
            assert response.query == "Python programming"
            assert response.provider == "DuckDuckGo"
            assert response.search_time_ms >= 0
            assert response.total_results >= 0

            # Verify we got actual results
            assert len(response.results) > 0, "Should return at least one search result"
            # Note: Some providers may return slightly more results than requested
            assert (
                len(response.results) <= 5
            ), "Should return reasonable number of results"

            # Verify result structure and content
            first_result = response.results[0]
            assert first_result.title, "Result should have a title"
            assert first_result.url, "Result should have a URL"
            assert first_result.url.startswith(
                ("http://", "https://")
            ), "URL should be valid"
            assert first_result.snippet, "Result should have a snippet"
            assert first_result.source, "Result should have a source"

            # Verify content is related to Python
            search_terms = ["python", "programming", "code", "language", "development"]
            content = (first_result.title + " " + first_result.snippet).lower()
            assert any(
                term in content for term in search_terms
            ), f"Result should contain Python-related content: {content}"

        finally:
            await manager.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_google_search_with_api_key(self):
        """Test Google search returns real results when API key is configured"""
        import os

        # Skip if no Google API credentials
        google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        google_cx = os.getenv("GOOGLE_SEARCH_CX")

        if not google_api_key or not google_cx:
            pytest.skip("Google Search API credentials not configured")

        config = {
            "search": {
                "google": {"api_key": google_api_key, "search_engine_id": google_cx}
            }
        }
        manager = SearchManager(config)

        try:
            response = await manager.search(
                "machine learning", provider="google", max_results=3
            )

            # Verify response structure
            assert response.query == "machine learning"
            assert response.provider == "Google"
            assert response.search_time_ms >= 0

            # Verify we got actual results
            assert len(response.results) > 0, "Should return at least one search result"
            # Note: Some providers may return slightly more results than requested
            assert (
                len(response.results) <= 5
            ), "Should return reasonable number of results"

            # Verify result quality
            first_result = response.results[0]
            assert first_result.title, "Result should have a title"
            assert first_result.url.startswith(
                ("http://", "https://")
            ), "URL should be valid"
            assert first_result.snippet, "Result should have a snippet"

        finally:
            await manager.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bing_search_with_api_key(self):
        """Test Bing search returns real results when API key is configured"""
        import os

        # Skip if no Bing API credentials
        bing_api_key = os.getenv("BING_SEARCH_API_KEY")

        if not bing_api_key:
            pytest.skip("Bing Search API key not configured")

        config = {"search": {"bing": {"api_key": bing_api_key}}}
        manager = SearchManager(config)

        try:
            response = await manager.search(
                "artificial intelligence", provider="bing", max_results=3
            )

            # Verify response structure
            assert response.query == "artificial intelligence"
            assert response.provider == "Bing"
            assert response.search_time_ms >= 0

            # Verify we got actual results
            assert len(response.results) > 0, "Should return at least one search result"
            # Note: Some providers may return slightly more results than requested
            assert (
                len(response.results) <= 5
            ), "Should return reasonable number of results"

            # Verify result quality
            first_result = response.results[0]
            assert first_result.title, "Result should have a title"
            assert first_result.url.startswith(
                ("http://", "https://")
            ), "URL should be valid"
            assert first_result.snippet, "Result should have a snippet"

        finally:
            await manager.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_error_handling_real(self):
        """Test error handling with real search providers"""
        config = {}
        manager = SearchManager(config)

        try:
            # Test search with unavailable provider
            with pytest.raises(
                SearchError, match="Search provider 'nonexistent' not available"
            ):
                await manager.search("test", provider="nonexistent")

            # Test that empty query doesn't crash (may return empty results or still work)
            response = await manager.search("", provider="duckduckgo")
            assert response.query == ""
            assert response.provider == "DuckDuckGo"
            # Empty query might return no results or some default results, both are valid
            assert isinstance(response.results, list)

        finally:
            await manager.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_results_quality(self):
        """Test that multiple search results are diverse and relevant"""
        config = {}
        manager = SearchManager(config)

        try:
            response = await manager.search("web development tutorial", max_results=5)

            assert len(response.results) > 1, "Should return multiple results"

            # Check that results are diverse (different URLs)
            urls = [result.url for result in response.results]
            unique_urls = set(urls)
            assert len(unique_urls) == len(urls), "All results should have unique URLs"

            # Check that all results are relevant
            for i, result in enumerate(response.results):
                assert result.title, f"Result {i} should have a title"
                assert result.url.startswith(
                    ("http://", "https://")
                ), f"Result {i} should have valid URL"
                assert result.snippet, f"Result {i} should have a snippet"

                # Check relevance to search query
                content = (result.title + " " + result.snippet).lower()
                relevant_terms = [
                    "web",
                    "development",
                    "tutorial",
                    "programming",
                    "code",
                    "html",
                    "css",
                    "javascript",
                ]
                assert any(
                    term in content for term in relevant_terms
                ), f"Result {i} should contain web development related content: {content}"

        finally:
            await manager.close()


class TestWebSearchToolIntegration:
    """Integration tests for web_search tool with real search providers"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_web_search_tool_real_results(self):
        """Test web_search tool returns real results"""
        result = await web_search("data science Python", max_results=3)

        # Verify response structure
        assert result["query"] == "data science Python"
        assert result["provider"] in ["duckduckgo", "google", "bing"]
        assert "results" in result
        assert "total_results" in result

        # Verify we got actual results
        assert len(result["results"]) > 0, "Should return at least one search result"
        assert len(result["results"]) <= 5, "Should return reasonable number of results"

        # Verify result structure
        first_result = result["results"][0]
        assert "title" in first_result, "Result should have a title"
        assert "url" in first_result, "Result should have a URL"
        assert "snippet" in first_result, "Result should have a snippet"
        assert "source" in first_result, "Result should have a source"

        # Verify URL is valid
        assert first_result["url"].startswith(
            ("http://", "https://")
        ), "URL should be valid"

        # Verify content relevance
        content = (first_result["title"] + " " + first_result["snippet"]).lower()
        relevant_terms = [
            "data",
            "science",
            "python",
            "analysis",
            "machine",
            "learning",
        ]
        assert any(
            term in content for term in relevant_terms
        ), f"Result should contain data science related content: {content}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_web_search_tool_uses_config_provider(self):
        """Test web_search tool uses provider from configuration"""
        # Test with default configuration
        result = await web_search("JavaScript frameworks", max_results=2)
        assert len(result["results"]) > 0
        assert "provider" in result

        # Verify the result contains expected fields
        for search_result in result["results"]:
            assert search_result["title"]
            assert search_result["url"].startswith(("http://", "https://"))
            assert search_result["snippet"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_web_search_tool_max_results_limit(self):
        """Test web_search tool respects max_results parameter"""
        # Test with different limits
        for max_results in [1, 3, 5]:
            result = await web_search("Python libraries", max_results=max_results)
            assert (
                len(result["results"]) <= max_results
            ), f"Should not exceed max_results={max_results}"
            assert len(result["results"]) > 0, "Should return at least one result"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_web_search_tool_query_variations(self):
        """Test web_search tool with different types of queries"""
        test_queries = [
            "how to install Python",
            "best restaurants near me",
            "current weather forecast",
            "latest technology news",
            "machine learning algorithms",
        ]

        for query in test_queries:
            result = await web_search(query, max_results=2)

            assert result["query"] == query
            assert len(result["results"]) > 0, f"Query '{query}' should return results"

            # Verify each result has required fields
            for search_result in result["results"]:
                assert search_result["title"], f"Result for '{query}' should have title"
                assert search_result["url"], f"Result for '{query}' should have URL"
                assert search_result[
                    "snippet"
                ], f"Result for '{query}' should have snippet"
