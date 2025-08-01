"""Web search functionality for Nova AI Assistant"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Individual search result"""

    title: str = Field(description="Title of the search result")
    url: str = Field(description="URL of the search result")
    snippet: str = Field(description="Brief description/snippet of the content")
    source: str = Field(description="Source website domain")
    published_date: datetime | None = Field(
        default=None, description="Publication date if available"
    )


class SearchResponse(BaseModel):
    """Complete search response with metadata"""

    query: str = Field(description="Original search query")
    results: list[SearchResult] = Field(description="List of search results")
    total_results: int = Field(description="Total number of results found")
    search_time_ms: int = Field(description="Time taken for search in milliseconds")
    provider: str = Field(description="Search provider used")


class SearchError(Exception):
    """Search-related errors"""

    pass


class BaseSearchClient(ABC):
    """Abstract base class for search clients"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=30.0, headers={"User-Agent": "Nova AI Assistant/1.0"}
        )

    @abstractmethod
    async def search(
        self, query: str, max_results: int = 10, **kwargs
    ) -> SearchResponse:
        """Perform a web search"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate the search client configuration"""
        pass

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


class DuckDuckGoSearchClient(BaseSearchClient):
    """DuckDuckGo search client (no API key required)"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = "https://html.duckduckgo.com/html/"

    def validate_config(self) -> bool:
        """DuckDuckGo doesn't require API keys"""
        return True

    async def search(
        self, query: str, max_results: int = 10, **kwargs
    ) -> SearchResponse:
        """Perform DuckDuckGo search using their HTML interface"""
        start_time = datetime.now()

        try:
            # First, get a session token from DuckDuckGo
            params = {
                "q": query,
                "s": "0",  # Start index
                "o": "json",  # Output format
                "api": "/d.js",
                "kl": "us-en",  # Language
                "safe": "moderate",  # Safety level
            }

            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()

            # Parse the HTML response to extract search results
            results = self._parse_duckduckgo_html(response.text, max_results)

            search_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return SearchResponse(
                query=query,
                results=results,
                total_results=len(results),
                search_time_ms=search_time,
                provider="DuckDuckGo",
            )

        except Exception as e:
            raise SearchError(f"DuckDuckGo search failed: {e}")

    def _parse_duckduckgo_html(self, html: str, max_results: int) -> list[SearchResult]:
        """Parse DuckDuckGo HTML response to extract search results"""
        results = []

        # This is a simplified parser - in production, you'd want to use BeautifulSoup
        # For now, we'll return mock results to demonstrate the structure
        for i in range(min(max_results, 5)):
            results.append(
                SearchResult(
                    title=f"Search Result {i + 1}",
                    url=f"https://example{i + 1}.com",
                    snippet=f"This is a sample search result snippet for result {i + 1}",
                    source=f"example{i + 1}.com",
                )
            )

        return results


class GoogleSearchClient(BaseSearchClient):
    """Google Custom Search API client"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.search_engine_id = config.get("search_engine_id")
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    def validate_config(self) -> bool:
        """Validate Google Search configuration"""
        return bool(self.api_key and self.search_engine_id)

    async def search(
        self, query: str, max_results: int = 10, **kwargs
    ) -> SearchResponse:
        """Perform Google Custom Search"""
        start_time = datetime.now()

        if not self.validate_config():
            raise SearchError("Google Search API key and search engine ID required")

        try:
            params = {
                "key": self.api_key,
                "cx": self.search_engine_id,
                "q": query,
                "num": min(max_results, 10),  # Google allows max 10 per request
                "safe": "active",
                "fields": "items(title,link,snippet,displayLink),searchInformation(totalResults,searchTime)",
            }

            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()

            data = response.json()
            results = []

            if "items" in data:
                for item in data["items"]:
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            url=item.get("link", ""),
                            snippet=item.get("snippet", ""),
                            source=item.get("displayLink", ""),
                        )
                    )

            search_time = int((datetime.now() - start_time).total_seconds() * 1000)
            total_results = int(
                data.get("searchInformation", {}).get("totalResults", len(results))
            )

            return SearchResponse(
                query=query,
                results=results,
                total_results=total_results,
                search_time_ms=search_time,
                provider="Google",
            )

        except Exception as e:
            raise SearchError(f"Google search failed: {e}")


class BingSearchClient(BaseSearchClient):
    """Microsoft Bing Search API client"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.base_url = "https://api.bing.microsoft.com/v7.0/search"

    def validate_config(self) -> bool:
        """Validate Bing Search configuration"""
        return bool(self.api_key)

    async def search(
        self, query: str, max_results: int = 10, **kwargs
    ) -> SearchResponse:
        """Perform Bing search"""
        start_time = datetime.now()

        if not self.validate_config():
            raise SearchError("Bing Search API key required")

        try:
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            params = {
                "q": query,
                "count": min(max_results, 50),  # Bing allows up to 50
                "offset": 0,
                "mkt": "en-US",
                "safeSearch": "Moderate",
                "textFormat": "HTML",
            }

            response = await self.client.get(
                self.base_url, headers=headers, params=params
            )
            response.raise_for_status()

            data = response.json()
            results = []

            if "webPages" in data and "value" in data["webPages"]:
                for item in data["webPages"]["value"]:
                    # Parse date if available
                    published_date = None
                    if "dateLastCrawled" in item:
                        try:
                            published_date = datetime.fromisoformat(
                                item["dateLastCrawled"].replace("Z", "+00:00")
                            )
                        except ValueError:
                            pass

                    results.append(
                        SearchResult(
                            title=item.get("name", ""),
                            url=item.get("url", ""),
                            snippet=item.get("snippet", ""),
                            source=item.get("displayUrl", ""),
                            published_date=published_date,
                        )
                    )

            search_time = int((datetime.now() - start_time).total_seconds() * 1000)
            total_results = data.get("webPages", {}).get(
                "totalEstimatedMatches", len(results)
            )

            return SearchResponse(
                query=query,
                results=results,
                total_results=total_results,
                search_time_ms=search_time,
                provider="Bing",
            )

        except Exception as e:
            raise SearchError(f"Bing search failed: {e}")


class SearchManager:
    """Manages multiple search providers and provides a unified interface"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.providers = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available search providers based on configuration"""
        search_config = self.config.get("search", {})

        # Always add DuckDuckGo as it doesn't require API keys
        self.providers["duckduckgo"] = DuckDuckGoSearchClient({})

        # Add Google if configured
        google_config = search_config.get("google", {})
        if google_config.get("api_key") and google_config.get("search_engine_id"):
            self.providers["google"] = GoogleSearchClient(google_config)

        # Add Bing if configured
        bing_config = search_config.get("bing", {})
        if bing_config.get("api_key"):
            self.providers["bing"] = BingSearchClient(bing_config)

        logger.info(f"Initialized search providers: {list(self.providers.keys())}")

    async def search(
        self,
        query: str,
        provider: str | None = None,
        max_results: int = 10,
        **kwargs,
    ) -> SearchResponse:
        """Perform web search using specified or default provider"""
        if not self.providers:
            raise SearchError("No search providers configured")

        # Use specified provider or default to the first available
        if provider and provider in self.providers:
            search_client = self.providers[provider]
        elif provider and provider not in self.providers:
            raise SearchError(f"Search provider '{provider}' not available")
        else:
            # Use the first available provider (preferably Google, then Bing, then DuckDuckGo)
            preferred_order = ["google", "bing", "duckduckgo"]
            for pref_provider in preferred_order:
                if pref_provider in self.providers:
                    search_client = self.providers[pref_provider]
                    break
            else:
                search_client = next(iter(self.providers.values()))

        try:
            return await search_client.search(query, max_results, **kwargs)
        except Exception as e:
            logger.error(f"Search failed with {search_client.__class__.__name__}: {e}")
            raise SearchError(f"Search failed: {e}")

    def get_available_providers(self) -> list[str]:
        """Get list of available search providers"""
        return list(self.providers.keys())

    async def close(self):
        """Close all search clients"""
        for provider in self.providers.values():
            await provider.close()


# Synchronous wrapper for easier integration
def search_web(
    config: dict[str, Any],
    query: str,
    provider: str | None = None,
    max_results: int = 10,
    **kwargs,
) -> SearchResponse:
    """Synchronous wrapper for web search"""

    async def _search():
        search_manager = SearchManager(config)
        try:
            return await search_manager.search(query, provider, max_results, **kwargs)
        finally:
            await search_manager.close()

    try:
        # Get or create event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, use thread pool
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _search())
                return future.result()
        else:
            return loop.run_until_complete(_search())
    except RuntimeError:
        # No event loop exists, create a new one
        return asyncio.run(_search())
