"""Tests for web search functionality"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from nova.core.search import (
    BingSearchClient,
    DuckDuckGoSearchClient,
    GoogleSearchClient,
    SearchError,
    SearchManager,
    SearchResponse,
    SearchResult,
    search_web,
)
from nova.models.config import SearchConfig


class TestSearchResult:
    """Test SearchResult model"""

    def test_search_result_creation(self):
        """Test creating a search result"""
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            snippet="Test snippet",
            source="example.com",
        )

        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.snippet == "Test snippet"
        assert result.source == "example.com"
        assert result.published_date is None

    def test_search_result_with_date(self):
        """Test creating a search result with published date"""
        date = datetime.now()
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            snippet="Test snippet",
            source="example.com",
            published_date=date,
        )

        assert result.published_date == date


class TestSearchResponse:
    """Test SearchResponse model"""

    def test_search_response_creation(self):
        """Test creating a search response"""
        results = [
            SearchResult(
                title="Test 1",
                url="https://example1.com",
                snippet="Snippet 1",
                source="example1.com",
            ),
            SearchResult(
                title="Test 2",
                url="https://example2.com",
                snippet="Snippet 2",
                source="example2.com",
            ),
        ]

        response = SearchResponse(
            query="test query",
            results=results,
            total_results=2,
            search_time_ms=100,
            provider="test",
        )

        assert response.query == "test query"
        assert len(response.results) == 2
        assert response.total_results == 2
        assert response.search_time_ms == 100
        assert response.provider == "test"


class TestSearchConfig:
    """Test SearchConfig model"""

    def test_search_config_defaults(self):
        """Test SearchConfig default values"""
        config = SearchConfig()

        assert config.enabled is True
        assert config.default_provider == "duckduckgo"
        assert config.max_results == 5
        assert config.google == {}
        assert config.bing == {}

    def test_search_config_validation(self):
        """Test SearchConfig provider validation"""
        # Valid provider
        config = SearchConfig(default_provider="google")
        assert config.default_provider == "google"

        # Invalid provider should raise error
        with pytest.raises(ValueError, match="Provider must be one of"):
            SearchConfig(default_provider="invalid")

    def test_search_config_custom_values(self):
        """Test SearchConfig with custom values"""
        config = SearchConfig(
            enabled=False,
            default_provider="bing",
            max_results=10,
            use_ai_answers=False,
            google={"api_key": "test_google_key", "search_engine_id": "test_cx"},
            bing={"api_key": "test_bing_key"},
        )

        assert config.enabled is False
        assert config.default_provider == "bing"
        assert config.max_results == 10
        assert config.use_ai_answers is False
        assert config.google["api_key"] == "test_google_key"
        assert config.bing["api_key"] == "test_bing_key"


class TestDuckDuckGoSearchClient:
    """Test DuckDuckGo search client"""

    def test_validate_config(self):
        """Test DuckDuckGo config validation"""
        client = DuckDuckGoSearchClient({})
        assert client.validate_config() is True

    @pytest.mark.asyncio
    async def test_search_mock_response(self):
        """Test DuckDuckGo search with mocked response"""
        client = DuckDuckGoSearchClient({})

        # Mock HTML response with realistic DuckDuckGo structure
        mock_html = """
        <html>
            <body>
                <div class="result results_links">
                    <a class="result__a" href="https://example1.com">Test Result 1</a>
                    <div class="result__snippet">This is a test snippet for result 1</div>
                </div>
                <div class="result results_links">
                    <a class="result__a" href="https://example2.com">Test Result 2</a>
                    <div class="result__snippet">This is a test snippet for result 2</div>
                </div>
            </body>
        </html>
        """

        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status = Mock()

        with patch.object(client.client, "get", return_value=mock_response) as mock_get:
            response = await client.search("test query", max_results=3)

            assert response.query == "test query"
            assert response.provider == "DuckDuckGo"
            assert len(response.results) >= 1  # Should find at least one result
            assert response.search_time_ms >= 0

            # Check first result
            if response.results:
                first_result = response.results[0]
                assert first_result.title == "Test Result 1"
                assert first_result.url == "https://example1.com"
                assert "test snippet" in first_result.snippet.lower()

            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_error_handling(self):
        """Test DuckDuckGo search error handling"""
        client = DuckDuckGoSearchClient({})

        with patch.object(client.client, "get", side_effect=Exception("Network error")):
            with pytest.raises(SearchError, match="DuckDuckGo search failed"):
                await client.search("test query")


class TestGoogleSearchClient:
    """Test Google search client"""

    def test_validate_config_missing_keys(self):
        """Test Google config validation with missing keys"""
        client = GoogleSearchClient({})
        assert client.validate_config() is False

        client = GoogleSearchClient({"api_key": "test"})
        assert client.validate_config() is False

        client = GoogleSearchClient({"search_engine_id": "test"})
        assert client.validate_config() is False

    def test_validate_config_valid(self):
        """Test Google config validation with valid keys"""
        client = GoogleSearchClient(
            {"api_key": "test_key", "search_engine_id": "test_cx"}
        )
        assert client.validate_config() is True

    @pytest.mark.asyncio
    async def test_search_no_config(self):
        """Test Google search without proper configuration"""
        client = GoogleSearchClient({})

        with pytest.raises(SearchError, match="Google Search API key"):
            await client.search("test query")


class TestBingSearchClient:
    """Test Bing search client"""

    def test_validate_config_missing_key(self):
        """Test Bing config validation with missing key"""
        client = BingSearchClient({})
        assert client.validate_config() is False

    def test_validate_config_valid(self):
        """Test Bing config validation with valid key"""
        client = BingSearchClient({"api_key": "test_key"})
        assert client.validate_config() is True

    @pytest.mark.asyncio
    async def test_search_no_config(self):
        """Test Bing search without proper configuration"""
        client = BingSearchClient({})

        with pytest.raises(SearchError, match="Bing Search API key"):
            await client.search("test query")


class TestSearchManager:
    """Test SearchManager"""

    def test_initialization_duckduckgo_only(self):
        """Test SearchManager initialization with DuckDuckGo only"""
        config = {}
        manager = SearchManager(config)

        assert "duckduckgo" in manager.providers
        assert len(manager.providers) == 1

    def test_initialization_with_google(self):
        """Test SearchManager initialization with Google configured"""
        config = {
            "search": {"google": {"api_key": "test_key", "search_engine_id": "test_cx"}}
        }
        manager = SearchManager(config)

        assert "duckduckgo" in manager.providers
        assert "google" in manager.providers

    def test_initialization_with_bing(self):
        """Test SearchManager initialization with Bing configured"""
        config = {"search": {"bing": {"api_key": "test_key"}}}
        manager = SearchManager(config)

        assert "duckduckgo" in manager.providers
        assert "bing" in manager.providers

    def test_get_available_providers(self):
        """Test getting available providers"""
        manager = SearchManager({})
        providers = manager.get_available_providers()

        assert "duckduckgo" in providers
        assert isinstance(providers, list)

    @pytest.mark.asyncio
    async def test_search_invalid_provider(self):
        """Test search with invalid provider"""
        manager = SearchManager({})

        with pytest.raises(
            SearchError, match="Search provider 'invalid' not available"
        ):
            await manager.search("test query", provider="invalid")

    @pytest.mark.asyncio
    async def test_search_default_provider(self):
        """Test search with default provider"""
        manager = SearchManager({})

        # Mock the DuckDuckGo client's search method
        mock_response = SearchResponse(
            query="test query",
            results=[],
            total_results=0,
            search_time_ms=100,
            provider="DuckDuckGo",
        )

        with patch.object(
            manager.providers["duckduckgo"], "search", return_value=mock_response
        ) as mock_search:
            result = await manager.search("test query")

            assert result.query == "test query"
            assert result.provider == "DuckDuckGo"
            mock_search.assert_called_once_with("test query", 10)


class TestSearchWebFunction:
    """Test search_web synchronous wrapper function"""

    def test_search_web_basic(self):
        """Test basic search_web function call"""
        # This test would require complex async mocking, so we'll test the
        # integration through the SearchManager tests instead
        pass

    @patch("nova.core.search.asyncio.get_event_loop")
    def test_search_web_with_loop(self, mock_get_loop):
        """Test search_web with existing event loop"""
        mock_loop = Mock()
        mock_loop.is_running.return_value = False
        mock_loop.run_until_complete.return_value = SearchResponse(
            query="test query",
            results=[],
            total_results=0,
            search_time_ms=100,
            provider="DuckDuckGo",
        )
        mock_get_loop.return_value = mock_loop

        result = search_web({}, "test query")

        assert result.query == "test query"
        mock_loop.run_until_complete.assert_called_once()
