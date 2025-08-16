"""Enhanced search manager with intelligent query optimization"""

import asyncio
import logging
from typing import Any

from .engines import (
    BaseSearchClient,
    BingSearchClient,
    DuckDuckGoSearchClient,
    GoogleSearchClient,
)
from .enhancement import QueryEnhancer
from .enhancement.extractors import ExtractionConfig
from .models import (
    EnhancedSearchPlan,
    SearchEnhancementMode,
    SearchError,
    SearchMemoryConstraints,
    SearchResponse,
    SearchResult,
)

logger = logging.getLogger(__name__)


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


class EnhancedSearchManager:
    """Enhanced search manager with intelligent query optimization"""

    def __init__(self, config: dict[str, Any], ai_client=None):
        self.config = config
        self.ai_client = ai_client
        self.providers = {}
        self.query_enhancer = None

        # Initialize search providers
        self._initialize_providers()

        # Initialize query enhancer if AI client is available
        if ai_client:
            extraction_config = self._build_extraction_config()
            self.query_enhancer = QueryEnhancer(ai_client, extraction_config)

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.close()

    def _initialize_providers(self):
        """Initialize available search providers based on configuration"""
        search_config = self.config.get("search", {})

        # Always add DuckDuckGo as it doesn't require API keys
        ddg_config = {"timeout": search_config.get("request_timeout", 10.0)}
        self.providers["duckduckgo"] = DuckDuckGoSearchClient(ddg_config)

        # Add Google if configured
        google_config = search_config.get("google", {})
        if google_config.get("api_key") and google_config.get("search_engine_id"):
            google_config["timeout"] = search_config.get("request_timeout", 10.0)
            self.providers["google"] = GoogleSearchClient(google_config)

        # Add Bing if configured
        bing_config = search_config.get("bing", {})
        if bing_config.get("api_key"):
            bing_config["timeout"] = search_config.get("request_timeout", 10.0)
            self.providers["bing"] = BingSearchClient(bing_config)

        logger.info(f"Initialized search providers: {list(self.providers.keys())}")

    def _build_extraction_config(self) -> ExtractionConfig:
        """Build extraction configuration from Nova config"""
        search_config = self.config.get("search", {})

        return ExtractionConfig(
            backend=search_config.get("extraction_backend", "yake_only"),
            yake_max_keywords=search_config.get("yake_max_keywords", 10),
            keybert_max_keywords=search_config.get("keybert_max_keywords", 6),
            keybert_model=search_config.get("keybert_model", "all-MiniLM-L6-v2"),
            performance_mode=search_config.get("performance_mode", True),
        )

    async def enhanced_search(
        self,
        query: str,
        provider: str | None = None,
        max_results: int = 10,
        extract_content: bool = False,
        enhancement_mode: SearchEnhancementMode = SearchEnhancementMode.FAST,
        conversation_context: str = "",
        memory_constraints: SearchMemoryConstraints | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Perform enhanced web search with intelligent query optimization

        Returns:
            Dict containing search results and enhancement details
        """

        if not self.providers:
            raise SearchError("No search providers configured")

        # Stage 1: Query Enhancement (if enabled)
        enhancement_plan = None
        if enhancement_mode != SearchEnhancementMode.DISABLED and self.query_enhancer:
            try:
                # Add timeout for query enhancement to prevent performance issues
                search_config = self.config.get("search", {})
                enhancement_timeout = search_config.get("enhancement_timeout", 30.0)
                enhancement_plan = await asyncio.wait_for(
                    self.query_enhancer.enhance_query(
                        user_query=query,
                        conversation_context=conversation_context,
                        memory_constraints=memory_constraints,
                        enhancement_mode=enhancement_mode,
                        max_queries=3,
                    ),
                    timeout=enhancement_timeout,
                )
                logger.info(
                    f"Enhanced query in {enhancement_plan.processing_time_ms}ms"
                )
            except TimeoutError:
                logger.warning(
                    f"Query enhancement timed out after {enhancement_timeout} seconds, using original query"
                )
            except Exception as e:
                logger.warning(f"Query enhancement failed: {e}")

        # Stage 2: Execute searches (with or without enhancement)
        if enhancement_plan and enhancement_plan.enhanced_queries:
            search_results = await self._execute_enhanced_searches(
                enhancement_plan, provider, max_results, extract_content, **kwargs
            )
        else:
            # Fallback to single query search
            search_results = await self._execute_single_search(
                query, provider, max_results, extract_content, **kwargs
            )

        # Stage 3: Prepare response with enhancement details
        response = {
            "query": query,
            "results": (
                search_results.results
                if hasattr(search_results, "results")
                else search_results
            ),
            "total_results": (
                search_results.total_results
                if hasattr(search_results, "total_results")
                else len(search_results)
            ),
            "search_time_ms": (
                search_results.search_time_ms
                if hasattr(search_results, "search_time_ms")
                else 0
            ),
            "provider": (
                search_results.provider
                if hasattr(search_results, "provider")
                else (provider or "duckduckgo")
            ),
        }

        # Add enhancement details if available
        if enhancement_plan:
            response["enhancement_details"] = {
                "mode": enhancement_plan.enhancement_mode,
                "processing_time_ms": enhancement_plan.processing_time_ms,
                "context_used": enhancement_plan.context_used,
                "enhanced_queries": [
                    eq.model_dump() for eq in enhancement_plan.enhanced_queries
                ],
                "extraction_summary": enhancement_plan.extraction_details,
            }

        return response

    async def _execute_enhanced_searches(
        self,
        enhancement_plan: EnhancedSearchPlan,
        provider: str | None,
        max_results: int,
        extract_content: bool,
        **kwargs,
    ) -> SearchResponse:
        """Execute multiple enhanced queries and merge results"""

        search_client = self._get_search_client(provider)
        all_results = []
        total_search_time = 0

        # Execute queries in parallel with limited concurrency
        semaphore = asyncio.Semaphore(2)  # Max 2 concurrent searches

        async def execute_query(enhanced_query):
            async with semaphore:
                try:
                    # Distribute max_results across queries
                    query_max_results = max_results // len(
                        enhancement_plan.enhanced_queries
                    )
                    if query_max_results < 3:
                        query_max_results = 3

                    response = await search_client.search(
                        enhanced_query.query, query_max_results, **kwargs
                    )

                    # Add query metadata to results
                    for result in response.results:
                        result.enhancement_priority = enhanced_query.priority
                        result.enhancement_rationale = enhanced_query.rationale

                    return response
                except Exception as e:
                    logger.warning(
                        f"Enhanced query failed: {enhanced_query.query} - {e}"
                    )
                    return None

        # Execute all enhanced queries
        search_tasks = [execute_query(eq) for eq in enhancement_plan.enhanced_queries]

        search_responses = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Merge and deduplicate results
        seen_urls = set()
        for response in search_responses:
            if response and hasattr(response, "results"):
                total_search_time += response.search_time_ms
                for result in response.results:
                    if result.url not in seen_urls:
                        all_results.append(result)
                        seen_urls.add(result.url)

        # Sort by enhancement priority and relevance
        all_results.sort(
            key=lambda r: (
                getattr(r, "enhancement_priority", 999),
                -len(r.snippet),  # Prefer results with more detailed snippets
            )
        )

        # Extract content if requested
        if extract_content and all_results:
            all_results = await self._enhance_results_with_content(
                all_results[:max_results],
                search_client,
                enhancement_plan.original_query,
            )

        return SearchResponse(
            query=enhancement_plan.original_query,
            results=all_results[:max_results],
            total_results=len(all_results),
            search_time_ms=total_search_time,
            provider=search_client.__class__.__name__.replace("SearchClient", ""),
        )

    async def _execute_single_search(
        self,
        query: str,
        provider: str | None,
        max_results: int,
        extract_content: bool,
        **kwargs,
    ) -> SearchResponse:
        """Execute a single search query (fallback)"""

        search_client = self._get_search_client(provider)

        try:
            search_response = await search_client.search(query, max_results, **kwargs)

            # Extract content if requested
            if extract_content and search_response.results:
                enhanced_results = await self._enhance_results_with_content(
                    search_response.results, search_client, query
                )
                search_response.results = enhanced_results

            return search_response

        except Exception as e:
            logger.error(f"Single search failed: {e}")
            raise SearchError(f"Search failed: {e}")

    def _get_search_client(self, provider: str | None) -> BaseSearchClient:
        """Get the appropriate search client"""

        if provider and provider in self.providers:
            return self.providers[provider]
        elif provider and provider not in self.providers:
            raise SearchError(f"Search provider '{provider}' not available")
        else:
            # Use configured default provider first
            search_config = self.config.get("search", {})
            default_provider = search_config.get("default_provider", "duckduckgo")

            if default_provider in self.providers:
                return self.providers[default_provider]

            # Fallback to any available provider
            preferred_order = ["google", "bing", "duckduckgo"]
            for pref_provider in preferred_order:
                if pref_provider in self.providers:
                    return self.providers[pref_provider]

            # Final fallback to first available
            return next(iter(self.providers.values()))

    async def _enhance_results_with_content(
        self, results: list[SearchResult], search_client: BaseSearchClient, query: str
    ) -> list[SearchResult]:
        """Enhance search results with extracted content and summaries"""

        summarizer = ContentSummarizer(self.ai_client) if self.ai_client else None

        # Process results concurrently for better performance
        enhancement_tasks = []
        semaphore = asyncio.Semaphore(3)  # Limit concurrent content extractions

        async def enhance_result(result: SearchResult):
            async with semaphore:
                try:
                    # Extract content
                    content, success = await search_client.extract_content(result.url)

                    # Generate summary if content was extracted and summarizer is available
                    summary = None
                    if success and content and summarizer:
                        try:
                            summary = await summarizer.summarize_content(content, query)
                        except Exception as e:
                            logger.debug(
                                f"Summary generation failed for {result.url}: {e}"
                            )

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
                    result.extraction_success = False
                    return result

        enhancement_tasks = [enhance_result(result) for result in results]
        enhanced_results = await asyncio.gather(
            *enhancement_tasks, return_exceptions=True
        )

        # Filter out failed enhancements
        valid_results = []
        for result in enhanced_results:
            if isinstance(result, SearchResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"Content enhancement failed: {result}")

        return valid_results

    def get_available_providers(self) -> list[str]:
        """Get list of available search providers"""
        return list(self.providers.keys())

    async def close(self):
        """Close all search clients"""
        for provider_name, provider in self.providers.items():
            try:
                await provider.close()
                logger.debug(f"Closed search provider: {provider_name}")
            except Exception as e:
                logger.warning(f"Error closing search provider {provider_name}: {e}")

    # Backward compatibility methods
    async def search(self, *args, **kwargs) -> SearchResponse:
        """Backward compatibility method"""
        result = await self.enhanced_search(*args, **kwargs)

        # Convert back to SearchResponse format for compatibility
        return SearchResponse(
            query=result["query"],
            results=result["results"],
            total_results=result["total_results"],
            search_time_ms=result["search_time_ms"],
            provider=result["provider"],
        )
