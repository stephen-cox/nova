"""Google Custom Search engine implementation"""

import logging
from datetime import datetime

from ..models import SearchError, SearchResponse, SearchResult
from .base import BaseSearchEngine

logger = logging.getLogger(__name__)


class GoogleEngine(BaseSearchEngine):
    """Google Custom Search API engine"""

    def __init__(self, config: dict):
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
