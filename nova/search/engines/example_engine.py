"""Example search engine implementation - template for adding new engines"""

import logging
from datetime import datetime
from typing import Any

from ..models import SearchError, SearchResponse, SearchResult
from .base import BaseSearchEngine

logger = logging.getLogger(__name__)


class ExampleEngine(BaseSearchEngine):
    """Example search engine implementation

    This is a template for creating new search engines. To add a new search engine:

    1. Copy this file and rename it (e.g., 'yandex.py')
    2. Rename the class (e.g., 'YandexEngine')
    3. Implement the search() and validate_config() methods
    4. Add your engine to engines/__init__.py SEARCH_ENGINES dict
    5. Test your implementation

    Required methods:
    - __init__(self, config: dict): Initialize with configuration
    - validate_config(self) -> bool: Validate configuration
    - search(self, query, max_results, **kwargs) -> SearchResponse: Perform search

    Optional methods you can override:
    - extract_content(self, url) -> tuple[str|None, bool]: Custom content extraction
    - close(self): Custom cleanup when search engine is closed
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Initialize your engine-specific settings here
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url", "https://api.example.com/search")
        # Add other configuration parameters as needed

    def validate_config(self) -> bool:
        """Validate the search engine configuration

        Returns:
            bool: True if configuration is valid, False otherwise
        """
        # Implement your validation logic here
        # For example, check if required API keys are present
        return bool(self.api_key)

    async def search(
        self, query: str, max_results: int = 10, **kwargs
    ) -> SearchResponse:
        """Perform search using your engine's API

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            **kwargs: Additional engine-specific parameters

        Returns:
            SearchResponse: Response with search results and metadata

        Raises:
            SearchError: If search fails
        """
        start_time = datetime.now()

        if not self.validate_config():
            raise SearchError("Example Engine API key required")

        try:
            # Implement your search logic here
            # This is just an example structure

            # 1. Prepare API request parameters
            params = {
                "q": query,
                "count": min(max_results, 50),  # Adjust based on your API limits
                # Add other parameters as needed
            }

            # 2. Make API request
            headers = {"Authorization": f"Bearer {self.api_key}"}  # Adjust as needed
            response = await self.client.get(
                self.base_url, params=params, headers=headers
            )
            response.raise_for_status()

            # 3. Parse response
            data = response.json()
            results = self._parse_response(data)

            # 4. Calculate search time
            search_time = int((datetime.now() - start_time).total_seconds() * 1000)

            # 5. Return SearchResponse
            return SearchResponse(
                query=query,
                results=results,
                total_results=len(results),  # Or extract from API response if available
                search_time_ms=search_time,
                provider="ExampleEngine",  # Change to your engine name
            )

        except Exception as e:
            raise SearchError(f"Example Engine search failed: {e}")

    def _parse_response(self, data: dict) -> list[SearchResult]:
        """Parse API response into SearchResult objects

        Args:
            data: Raw API response data

        Returns:
            list[SearchResult]: Parsed search results
        """
        results = []

        # This is example parsing logic - adjust based on your API response structure
        items = data.get("results", [])  # Adjust key name based on your API

        for item in items:
            # Extract data from each result item
            title = item.get("title", "")
            url = item.get("url", "")
            snippet = item.get("description", "")  # Or "summary", "excerpt", etc.
            source = item.get("domain", "")

            # Parse date if available
            published_date = None
            if "published" in item:
                try:
                    # Adjust date parsing based on your API's date format
                    published_date = datetime.fromisoformat(item["published"])
                except (ValueError, KeyError):
                    pass

            # Create SearchResult
            if title and url:  # Only add results with required fields
                results.append(
                    SearchResult(
                        title=title[:200],  # Truncate if too long
                        url=url,
                        snippet=snippet[:400],  # Truncate if too long
                        source=source,
                        published_date=published_date,
                    )
                )

        return results


# TO ADD THIS ENGINE TO NOVA:
#
# 1. Import it in engines/__init__.py:
#    from .example_engine import ExampleEngine
#
# 2. Add it to SEARCH_ENGINES dict in engines/__init__.py:
#    SEARCH_ENGINES = {
#        "duckduckgo": DuckDuckGoEngine,
#        "google": GoogleEngine,
#        "bing": BingEngine,
#        "example": ExampleEngine,  # Add this line
#    }
#
# 3. Configure it in your Nova config file:
#    search:
#      example:
#        api_key: "your-api-key-here"
#        base_url: "https://api.example.com/search"  # if needed
#
# 4. Use it in Nova:
#    search_manager = SearchManager(config)
#    results = await search_manager.search("your query", provider="example")
