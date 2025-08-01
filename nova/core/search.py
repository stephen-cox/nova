"""Web search functionality for Nova AI Assistant"""

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup
from newspaper import Article
from pydantic import BaseModel, Field
from readability import Document

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
    full_content: str | None = Field(
        default=None, description="Full extracted webpage content"
    )
    content_summary: str | None = Field(
        default=None, description="AI-generated summary of the content"
    )
    extraction_success: bool = Field(
        default=False, description="Whether content extraction was successful"
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

    async def extract_content(self, url: str) -> tuple[str | None, bool]:
        """Extract full content from a webpage URL

        Returns:
            tuple: (extracted_content, success_flag)
        """
        try:
            # Method 1: Try newspaper3k first (better for articles)
            article = Article(url)
            article.download()
            article.parse()

            if article.text and len(article.text.strip()) > 100:
                logger.debug(f"Content extracted via newspaper3k from {url}")
                return article.text.strip(), True

        except Exception as e:
            logger.debug(f"Newspaper3k extraction failed for {url}: {e}")

        try:
            # Method 2: Fallback to readability-lxml (better for general pages)
            response = await self.client.get(url, timeout=15.0)
            response.raise_for_status()

            doc = Document(response.text)
            content = doc.summary()

            if content:
                # Parse with BeautifulSoup to extract clean text
                soup = BeautifulSoup(content, "html.parser")
                clean_text = soup.get_text(separator=" ", strip=True)

                if len(clean_text.strip()) > 100:
                    logger.debug(f"Content extracted via readability from {url}")
                    return clean_text.strip(), True

        except Exception as e:
            logger.debug(f"Readability extraction failed for {url}: {e}")

        try:
            # Method 3: Basic HTML parsing fallback
            response = await self.client.get(url, timeout=10.0)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted elements
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()

            # Try to find main content areas
            main_content = (
                soup.find("main")
                or soup.find("article")
                or soup.find(class_=re.compile(r"content|main|article", re.I))
                or soup.find("div", class_=re.compile(r"post|entry|body", re.I))
                or soup.body
            )

            if main_content:
                text = main_content.get_text(separator=" ", strip=True)
                if len(text.strip()) > 100:
                    logger.debug(f"Content extracted via basic HTML parsing from {url}")
                    return text.strip()[:5000], True  # Limit to 5000 chars

        except Exception as e:
            logger.debug(f"Basic HTML extraction failed for {url}: {e}")

        logger.warning(f"All content extraction methods failed for {url}")
        return None, False


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


class ContentSummarizer:
    """Handles advanced multi-level summarization using AI providers"""

    def __init__(self, ai_client):
        self.ai_client = ai_client

    async def summarize_content(
        self, content: str, query: str, max_length: int = 200
    ) -> str:
        """Generate a focused summary of content based on the search query"""
        if not content or len(content.strip()) < 50:
            return "Content too short to summarize"

        # Truncate very long content to avoid token limits
        if len(content) > 3000:
            content = content[:3000] + "..."

        prompt = f"""Summarize the following content in relation to the search query "{query}".
Focus on information most relevant to the query. Keep the summary under {max_length} words and make it informative and actionable.

Content:
{content}

Summary:"""

        try:
            # Use Nova's AI client interface
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates concise, relevant summaries.",
                },
                {"role": "user", "content": prompt},
            ]

            response = await self.ai_client.generate_response(messages)
            return response.strip() if response else "Summary generation failed"

        except Exception as e:
            logger.warning(f"AI summarization failed: {e}")
            # Fallback to simple truncation
            sentences = content.split(". ")
            summary = sentences[0]
            for sentence in sentences[1:3]:  # Take first 3 sentences max
                if len(summary + sentence) < max_length * 6:  # Rough char limit
                    summary += ". " + sentence
                else:
                    break
            return summary + ("..." if len(sentences) > 3 else "")

    async def synthesize_results(
        self, search_results: list[SearchResult], query: str
    ) -> str:
        """Create a comprehensive synthesis across multiple search results"""
        if not search_results:
            return "No search results available to synthesize."

        # Prepare synthesis prompt with all summaries
        summaries = []
        for i, result in enumerate(search_results[:5], 1):  # Limit to top 5 results
            content = result.content_summary or result.snippet
            if content:
                summaries.append(f"{i}. {result.title} ({result.source}):\n{content}")

        if not summaries:
            return "No content available for synthesis."

        synthesis_prompt = f"""Based on the following search results for the query "{query}", provide a comprehensive answer that:
1. Synthesizes information from multiple sources
2. Highlights key points and insights
3. Notes any conflicting information
4. Provides a balanced perspective

Search Results:
{chr(10).join(summaries)}

Comprehensive Answer:"""

        try:
            # Use Nova's AI client interface
            messages = [
                {
                    "role": "system",
                    "content": "You are a research assistant that synthesizes information from multiple sources to provide comprehensive, balanced answers.",
                },
                {"role": "user", "content": synthesis_prompt},
            ]

            response = await self.ai_client.generate_response(messages)
            return response.strip() if response else "Synthesis generation failed"

        except Exception as e:
            logger.warning(f"AI synthesis failed: {e}")
            # Fallback to simple concatenation
            return "\n\n".join(
                [
                    f"**{result.title}**: {result.content_summary or result.snippet}"
                    for result in search_results[:3]
                ]
            )


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
        extract_content: bool = False,
        ai_client=None,
        **kwargs,
    ) -> SearchResponse:
        """Perform web search using specified or default provider

        Args:
            query: Search query
            provider: Specific search provider to use
            max_results: Maximum number of results
            extract_content: Whether to extract full webpage content
            ai_client: AI client for content summarization
            **kwargs: Additional search parameters
        """
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
            # Perform initial search
            search_response = await search_client.search(query, max_results, **kwargs)

            # Extract content and generate summaries if requested
            if extract_content and search_response.results:
                summarizer = ContentSummarizer(ai_client) if ai_client else None

                # Process results concurrently for better performance
                enhanced_results = []
                extraction_tasks = []

                for result in search_response.results:
                    task = self._enhance_result_with_content(
                        result, search_client, query, summarizer
                    )
                    extraction_tasks.append(task)

                # Execute content extraction tasks concurrently (limit to 3 at a time)
                semaphore = asyncio.Semaphore(3)

                async def limited_task(task):
                    async with semaphore:
                        return await task

                enhanced_results = await asyncio.gather(
                    *[limited_task(task) for task in extraction_tasks],
                    return_exceptions=True,
                )

                # Filter out failed extractions and update results
                valid_results = []
                for result in enhanced_results:
                    if isinstance(result, SearchResult):
                        valid_results.append(result)
                    elif isinstance(result, Exception):
                        logger.warning(f"Content extraction failed: {result}")
                        # Add original result without enhancement
                        continue

                search_response.results = valid_results

            return search_response

        except Exception as e:
            logger.error(f"Search failed with {search_client.__class__.__name__}: {e}")
            raise SearchError(f"Search failed: {e}")

    async def _enhance_result_with_content(
        self,
        result: SearchResult,
        search_client: BaseSearchClient,
        query: str,
        summarizer: ContentSummarizer | None,
    ) -> SearchResult:
        """Enhance a search result with extracted content and summary"""
        try:
            # Extract content
            content, success = await search_client.extract_content(result.url)

            # Generate summary if content was extracted and summarizer is available
            summary = None
            if success and content and summarizer:
                try:
                    summary = await summarizer.summarize_content(content, query)
                except Exception as e:
                    logger.debug(f"Summary generation failed for {result.url}: {e}")

            # Return enhanced result
            return SearchResult(
                title=result.title,
                url=result.url,
                snippet=result.snippet,
                source=result.source,
                published_date=result.published_date,
                full_content=content,
                content_summary=summary,
                extraction_success=success,
            )

        except Exception as e:
            logger.warning(f"Result enhancement failed for {result.url}: {e}")
            # Return original result with extraction failure marked
            return SearchResult(
                title=result.title,
                url=result.url,
                snippet=result.snippet,
                source=result.source,
                published_date=result.published_date,
                full_content=None,
                content_summary=None,
                extraction_success=False,
            )

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
    extract_content: bool = False,
    ai_client=None,
    **kwargs,
) -> SearchResponse:
    """Synchronous wrapper for web search with content extraction"""

    async def _search():
        search_manager = SearchManager(config)
        try:
            return await search_manager.search(
                query, provider, max_results, extract_content, ai_client, **kwargs
            )
        finally:
            await search_manager.close()

    try:
        # Get or create event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, use thread pool
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _search)
                return future.result()
        else:
            return loop.run_until_complete(_search())
    except RuntimeError:
        # No event loop exists, create a new one
        return asyncio.run(_search())
