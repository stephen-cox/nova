"""Microsoft Bing search engine implementation"""

import logging
from datetime import datetime

from ..models import SearchError, SearchResponse, SearchResult
from .base import BaseSearchEngine

logger = logging.getLogger(__name__)


class BingEngine(BaseSearchEngine):
    """Microsoft Bing Search API engine"""

    def __init__(self, config: dict):
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
