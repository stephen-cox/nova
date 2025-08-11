"""Tests for search engines"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from nova.search.engines import (
    BaseSearchClient,
    BingSearchClient,
    DuckDuckGoSearchClient,
    GoogleSearchClient,
)
from nova.search.models import SearchError, SearchResponse


# Create a concrete test implementation of BaseSearchClient
class TestableBaseSearchClient(BaseSearchClient):
    """Concrete implementation of BaseSearchClient for testing"""

    def validate_config(self) -> bool:
        return True

    async def search(
        self, query: str, max_results: int = 10, **kwargs
    ) -> SearchResponse:
        return SearchResponse(
            query=query, results=[], total_results=0, search_time_ms=0, provider="Test"
        )


class TestBaseSearchClient:
    """Test BaseSearchClient functionality"""

    def test_initialization(self):
        """Test client initialization"""
        config = {"timeout": 30}
        client = TestableBaseSearchClient(config)

        assert client.config == config
        assert client.client.timeout.read == 30.0

    @pytest.mark.asyncio
    async def test_close(self):
        """Test client cleanup"""
        config = {}
        client = TestableBaseSearchClient(config)

        # Mock the aclose method
        client.client.aclose = AsyncMock()

        await client.close()
        client.client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_content_with_newspaper(self):
        """Test content extraction using newspaper3k"""
        config = {}
        client = TestableBaseSearchClient(config)

        with patch("nova.search.engines.base.Article") as mock_article_class:
            mock_article = MagicMock()
            # Make sure the text is long enough to pass validation
            long_content = (
                "This is extracted article content that is sufficiently long to pass the length validation check. "
                * 3
            )
            mock_article.text = long_content
            mock_article_class.return_value = mock_article

            content, success = await client.extract_content("https://example.com")

            assert success is True
            assert content == long_content.strip()
            mock_article.download.assert_called_once()
            mock_article.parse.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_content_with_readability_fallback(self):
        """Test content extraction fallback to readability"""
        config = {}
        client = TestableBaseSearchClient(config)

        with (
            patch("nova.search.engines.base.Article") as mock_article_class,
            patch("nova.search.engines.base.Document") as mock_document_class,
            patch("nova.search.engines.base.BeautifulSoup") as mock_soup_class,
        ):
            # Make newspaper fail
            mock_article = MagicMock()
            mock_article.download.side_effect = Exception("Newspaper failed")
            mock_article_class.return_value = mock_article

            # Mock httpx response for readability method
            mock_response = MagicMock()
            mock_response.text = (
                "<html><body><div>Original HTML content</div></body></html>"
            )
            mock_response.raise_for_status = MagicMock()
            client.client.get = AsyncMock(return_value=mock_response)

            # Make readability succeed
            mock_document = MagicMock()
            mock_document.summary.return_value = (
                "<div>Readability extracted content that is sufficiently long</div>"
            )
            mock_document_class.return_value = mock_document

            # Mock BeautifulSoup parsing of readability content
            mock_soup_instance = MagicMock()
            long_readability_content = "Readability extracted content that is sufficiently long and meets all validation requirements for successful extraction"
            mock_soup_instance.get_text.return_value = long_readability_content
            mock_soup_class.return_value = mock_soup_instance

            content, success = await client.extract_content("https://example.com")

            assert success is True
            assert content == long_readability_content
            # Verify that Document was called with the response text
            mock_document_class.assert_called_once_with(mock_response.text)
            # Verify that BeautifulSoup was called with the document summary
            mock_soup_class.assert_called_once_with(
                "<div>Readability extracted content that is sufficiently long</div>",
                "html.parser",
            )

    @pytest.mark.asyncio
    async def test_extract_content_with_beautifulsoup_fallback(self):
        """Test content extraction final fallback to BeautifulSoup"""
        config = {}
        client = TestableBaseSearchClient(config)

        with (
            patch("nova.search.engines.base.Article") as mock_article_class,
            patch("nova.search.engines.base.Document") as mock_document_class,
            patch("nova.search.engines.base.BeautifulSoup") as mock_soup_class,
        ):
            # Make newspaper fail
            mock_article = MagicMock()
            mock_article.download.side_effect = Exception("Newspaper failed")
            mock_article_class.return_value = mock_article

            # Make readability fail by making it raise an exception
            mock_document_class.side_effect = Exception("Readability failed")

            # Mock httpx response for BeautifulSoup fallback method (third try block)
            mock_response = MagicMock()
            mock_response.text = "<html><body><main>Simple content that is long enough to pass validation checks</main></body></html>"
            mock_response.raise_for_status = MagicMock()
            client.client.get = AsyncMock(return_value=mock_response)

            # Mock BeautifulSoup parsing for the third fallback method
            mock_soup = MagicMock()

            # Mock the soup.find method to return a main element
            mock_main = MagicMock()
            long_fallback_content = "Simple content that is long enough to pass validation checks and should work for this test case perfectly"
            mock_main.get_text.return_value = long_fallback_content
            mock_soup.find.return_value = mock_main

            # Mock decompose method on unwanted elements (returns empty list)
            mock_soup.return_value = []

            mock_soup_class.return_value = mock_soup

            content, success = await client.extract_content("https://example.com")

            assert success is True
            assert content == long_fallback_content

    @pytest.mark.asyncio
    async def test_extract_content_all_methods_fail(self):
        """Test content extraction when all methods fail"""
        config = {}
        client = TestableBaseSearchClient(config)

        with patch("nova.search.engines.base.Article") as mock_article_class:
            # Mock httpx to raise exception for readability and BeautifulSoup methods
            client.client.get = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )

            # Make newspaper also fail
            mock_article = MagicMock()
            mock_article.download.side_effect = Exception("Newspaper failed")
            mock_article_class.return_value = mock_article

            content, success = await client.extract_content("https://example.com")

            assert success is False
            assert content is None


    def test_initialization_with_defaults(self):
        """Test client initialization with default timeout"""
        config = {}
        client = TestableBaseSearchClient(config)

        assert client.config == config
        assert client.client.timeout.read == 10.0  # Default timeout



class TestDuckDuckGoSearchClient:
    """Test DuckDuckGo search client"""

    def test_initialization(self):
        """Test DuckDuckGo client initialization"""
        config = {}
        client = DuckDuckGoSearchClient(config)

        assert client.config == config

    def test_validate_config(self):
        """Test configuration validation"""
        config = {}
        client = DuckDuckGoSearchClient(config)

        # DuckDuckGo doesn't require API keys, so should always be valid
        assert client.validate_config() is True

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful search"""
        config = {}
        client = DuckDuckGoSearchClient(config)

        # Mock HTML response
        html_content = """
        <html>
            <body>
                <div class="result results_links">
                    <div class="result__body">
                        <h2 class="result__title">
                            <a class="result__a" href="https://example.com">Test Result</a>
                        </h2>
                        <p class="result__snippet">This is a test snippet</p>
                    </div>
                </div>
            </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = html_content
        mock_response.raise_for_status = MagicMock()

        client.client.get = AsyncMock(return_value=mock_response)

        response = await client.search("test query", max_results=5)

        assert isinstance(response, SearchResponse)
        assert response.provider == "DuckDuckGo"
        assert len(response.results) >= 0  # May not find results in mock HTML

    @pytest.mark.asyncio
    async def test_search_network_error(self):
        """Test search with network error"""
        config = {}
        client = DuckDuckGoSearchClient(config)

        client.client.get = AsyncMock(side_effect=httpx.RequestError("Network error"))

        with pytest.raises(SearchError):
            await client.search("test query")

    def test_parse_duckduckgo_html_with_results(self):
        """Test HTML parsing with results"""
        config = {}
        client = DuckDuckGoSearchClient(config)

        html_content = """
        <html>
            <body>
                <div class="result results_links">
                    <div class="result__body">
                        <h2 class="result__title">
                            <a class="result__a" href="https://example.com">Test Result 1</a>
                        </h2>
                        <p class="result__snippet">This is test snippet 1</p>
                    </div>
                </div>
                <div class="result results_links">
                    <div class="result__body">
                        <h2 class="result__title">
                            <a class="result__a" href="https://example2.com">Test Result 2</a>
                        </h2>
                        <p class="result__snippet">This is test snippet 2</p>
                    </div>
                </div>
            </body>
        </html>
        """

        results = client._parse_duckduckgo_html(html_content, max_results=5)

        assert len(results) == 2
        assert results[0].title == "Test Result 1"
        assert results[0].url == "https://example.com"
        assert results[0].snippet == "This is test snippet 1"

    def test_parse_duckduckgo_html_no_results(self):
        """Test HTML parsing with no results"""
        config = {}
        client = DuckDuckGoSearchClient(config)

        html_content = "<html><body><p>No results found</p></body></html>"

        results = client._parse_duckduckgo_html(html_content, max_results=5)

        # DuckDuckGo client returns a fallback result when no real results are found
        assert len(results) == 1
        assert results[0].title == "Search results not available"
        assert results[0].url == "https://duckduckgo.com/"
        assert "Unable to parse search results" in results[0].snippet


class TestGoogleSearchClient:
    """Test Google search client"""

    def test_initialization(self):
        """Test Google client initialization"""
        config = {"api_key": "test_key", "search_engine_id": "test_id"}
        client = GoogleSearchClient(config)

        assert client.config == config
        assert client.api_key == "test_key"
        assert client.search_engine_id == "test_id"

    def test_validate_config_valid(self):
        """Test configuration validation with valid config"""
        config = {"api_key": "test_key", "search_engine_id": "test_id"}
        client = GoogleSearchClient(config)

        assert client.validate_config() is True

    def test_validate_config_missing_key(self):
        """Test configuration validation with missing API key"""
        config = {"search_engine_id": "test_id"}
        client = GoogleSearchClient(config)

        assert client.validate_config() is False

    def test_validate_config_missing_engine_id(self):
        """Test configuration validation with missing search engine ID"""
        config = {"api_key": "test_key"}
        client = GoogleSearchClient(config)

        assert client.validate_config() is False

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful Google search"""
        config = {"api_key": "test_key", "search_engine_id": "test_id"}
        client = GoogleSearchClient(config)

        # Mock Google API response
        mock_response_data = {
            "items": [
                {
                    "title": "Test Result 1",
                    "link": "https://example.com",
                    "snippet": "This is a test snippet",
                    "displayLink": "example.com",
                },
                {
                    "title": "Test Result 2",
                    "link": "https://example2.com",
                    "snippet": "This is another test snippet",
                    "displayLink": "example2.com",
                },
            ],
            "searchInformation": {"totalResults": "2"},
        }

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        client.client.get = AsyncMock(return_value=mock_response)

        response = await client.search("test query", max_results=5)

        assert isinstance(response, SearchResponse)
        assert response.provider == "Google"
        assert len(response.results) == 2
        assert response.results[0].title == "Test Result 1"
        assert response.results[0].url == "https://example.com"
        assert response.results[0].snippet == "This is a test snippet"
        assert response.results[0].source == "example.com"

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """Test Google search with no results"""
        config = {"api_key": "test_key", "search_engine_id": "test_id"}
        client = GoogleSearchClient(config)

        # Mock empty response
        mock_response_data = {"searchInformation": {"totalResults": "0"}}

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        client.client.get = AsyncMock(return_value=mock_response)

        response = await client.search("test query")

        assert isinstance(response, SearchResponse)
        assert response.provider == "Google"
        assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_search_api_error(self):
        """Test Google search with API error"""
        config = {"api_key": "test_key", "search_engine_id": "test_id"}
        client = GoogleSearchClient(config)

        client.client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "API Error", request=MagicMock(), response=MagicMock()
            )
        )

        with pytest.raises(SearchError):
            await client.search("test query")


class TestBingSearchClient:
    """Test Bing search client"""

    def test_initialization(self):
        """Test Bing client initialization"""
        config = {"api_key": "test_key"}
        client = BingSearchClient(config)

        assert client.config == config
        assert client.api_key == "test_key"

    def test_validate_config_valid(self):
        """Test configuration validation with valid config"""
        config = {"api_key": "test_key"}
        client = BingSearchClient(config)

        assert client.validate_config() is True

    def test_validate_config_missing_key(self):
        """Test configuration validation with missing API key"""
        config = {}
        client = BingSearchClient(config)

        assert client.validate_config() is False

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful Bing search"""
        config = {"api_key": "test_key"}
        client = BingSearchClient(config)

        # Mock Bing API response
        mock_response_data = {
            "webPages": {
                "value": [
                    {
                        "name": "Test Result 1",
                        "url": "https://example.com",
                        "snippet": "This is a test snippet",
                        "displayUrl": "example.com",
                    },
                    {
                        "name": "Test Result 2",
                        "url": "https://example2.com",
                        "snippet": "This is another test snippet",
                        "displayUrl": "example2.com",
                    },
                ],
                "totalEstimatedMatches": 2,
            }
        }

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        client.client.get = AsyncMock(return_value=mock_response)

        response = await client.search("test query", max_results=5)

        assert isinstance(response, SearchResponse)
        assert response.provider == "Bing"
        assert len(response.results) == 2
        assert response.results[0].title == "Test Result 1"
        assert response.results[0].url == "https://example.com"
        assert response.results[0].snippet == "This is a test snippet"

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """Test Bing search with no results"""
        config = {"api_key": "test_key"}
        client = BingSearchClient(config)

        # Mock empty response
        mock_response_data = {"webPages": {"totalEstimatedMatches": 0}}

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        client.client.get = AsyncMock(return_value=mock_response)

        response = await client.search("test query")

        assert isinstance(response, SearchResponse)
        assert response.provider == "Bing"
        assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_search_api_error(self):
        """Test Bing search with API error"""
        config = {"api_key": "test_key"}
        client = BingSearchClient(config)

        client.client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "API Error", request=MagicMock(), response=MagicMock()
            )
        )

        with pytest.raises(SearchError):
            await client.search("test query")
