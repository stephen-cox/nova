"""DuckDuckGo search engine implementation"""

import logging
import re
from datetime import datetime
from urllib.parse import unquote

from bs4 import BeautifulSoup

from ..models import SearchError, SearchResponse, SearchResult
from .base import BaseSearchEngine

logger = logging.getLogger(__name__)


class DuckDuckGoEngine(BaseSearchEngine):
    """DuckDuckGo search engine (no API key required)"""

    def __init__(self, config: dict):
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
            # DuckDuckGo HTML search parameters
            params = {
                "q": query,
                "kl": "us-en",  # Language/region
                "s": "0",  # Start index
                "df": "",  # Date filter
                "vqd": "",  # DuckDuckGo verification query data (will be filled automatically)
            }

            # First request to get the search page
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
        soup = BeautifulSoup(html, "html.parser")

        # First, check for instant answers (like IP address)
        instant_answer = soup.select_one(".zci__result")
        if instant_answer:
            answer_text = instant_answer.get_text(strip=True)
            if answer_text:
                results.append(
                    SearchResult(
                        title="Instant Answer",
                        url="https://duckduckgo.com/",
                        snippet=answer_text,
                        source="DuckDuckGo",
                    )
                )

        # Find search result containers using DuckDuckGo's actual structure
        search_results = soup.select(".result.results_links")

        count = 0
        for result in search_results:
            if count >= max_results:
                break

            try:
                # Look for the main link in the result
                title_link = result.select_one("a.result__a")
                if not title_link:
                    # Fallback: find any link in the result
                    title_link = result.find("a", href=True)

                if not title_link:
                    continue

                # Extract title
                title = title_link.get_text(strip=True)
                if not title:
                    continue

                # Extract URL
                url = title_link.get("href", "")

                # Clean up DuckDuckGo redirect URLs
                if "/l/?uddg=" in url:
                    # Extract the actual URL from DuckDuckGo redirect
                    url_match = re.search(r"uddg=([^&]+)", url)
                    if url_match:
                        url = unquote(url_match.group(1))
                elif url.startswith("//duckduckgo.com/l/?uddg="):
                    # Handle the //duckduckgo.com/l/ format
                    url_match = re.search(r"uddg=([^&]+)", url)
                    if url_match:
                        url = unquote(url_match.group(1))
                elif url.startswith("/l/?"):
                    # Other redirect format
                    url_match = re.search(r"https?://[^&\s]+", url)
                    if url_match:
                        url = unquote(url_match.group(0))

                # Skip if URL is not external
                if not url.startswith("http"):
                    continue

                # Extract snippet/description
                snippet = ""
                # Look for snippet in result body
                snippet_elem = result.select_one(".result__snippet")
                if snippet_elem:
                    snippet = snippet_elem.get_text(strip=True)
                else:
                    # Alternative: look for any description text
                    body_elem = result.select_one(".result__body")
                    if body_elem:
                        # Get text but exclude the title
                        body_text = body_elem.get_text(strip=True)
                        if body_text and title:
                            snippet = body_text.replace(title, "").strip()

                # Extract source domain from URL
                source = ""
                if url:
                    try:
                        from urllib.parse import urlparse

                        parsed_url = urlparse(url)
                        source = parsed_url.netloc.replace("www.", "")
                    except Exception:
                        # Fallback parsing
                        if "://" in url:
                            source = (
                                url.split("://")[1].split("/")[0].replace("www.", "")
                            )

                # Clean up and validate
                title = title[:200] if title else "No title"
                snippet = snippet[:400] if snippet else "No description available"
                source = source or "Unknown source"

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source=source,
                    )
                )
                count += 1

            except Exception as e:
                logger.debug(f"Error parsing search result: {e}")
                continue

        # If we still don't have results, provide a fallback message
        if not results:
            results.append(
                SearchResult(
                    title="Search results not available",
                    url="https://duckduckgo.com/",
                    snippet="Unable to parse search results. You can search manually at DuckDuckGo.",
                    source="duckduckgo.com",
                )
            )

        return results
