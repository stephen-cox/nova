"""Search manager that coordinates multiple search engines"""

import asyncio
import logging
from typing import Any

from .content import ContentSummarizer
from .engines import get_search_engine, list_search_engines
from .models import SearchError, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


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
        try:
            self.providers["duckduckgo"] = get_search_engine("duckduckgo", {})
        except Exception as e:
            logger.warning(f"Failed to initialize DuckDuckGo search: {e}")

        # Add Google if configured
        google_config = search_config.get("google", {})
        if google_config.get("api_key") and google_config.get("search_engine_id"):
            try:
                self.providers["google"] = get_search_engine("google", google_config)
            except Exception as e:
                logger.warning(f"Failed to initialize Google search: {e}")

        # Add Bing if configured
        bing_config = search_config.get("bing", {})
        if bing_config.get("api_key"):
            try:
                self.providers["bing"] = get_search_engine("bing", bing_config)
            except Exception as e:
                logger.warning(f"Failed to initialize Bing search: {e}")

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
        search_client,
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

    def get_available_engines(self) -> list[str]:
        """Get list of all available search engines"""
        return list_search_engines()

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
