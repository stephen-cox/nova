"""Enhanced web search and time tools

These tools provide advanced web search functionality with intelligent query enhancement
and current time information.
"""

import logging
from datetime import UTC, datetime

from nova.models.tools import PermissionLevel, ToolCategory, ToolExample
from nova.tools import tool

logger = logging.getLogger(__name__)


@tool(
    description="Intelligent web search with context-aware query enhancement",
    permission_level=PermissionLevel.ELEVATED,
    category=ToolCategory.INFORMATION,
    tags=["web", "search", "internet", "nlp", "enhanced"],
    examples=[
        ToolExample(
            description="Basic search using default provider",
            arguments={"query": "Python async programming"},
            expected_result="Search results using default provider (DuckDuckGo)",
        ),
        ToolExample(
            description="Enhanced search with automatic optimization",
            arguments={"query": "machine learning basics", "enhancement": "auto"},
            expected_result="Optimized search queries with extracted keywords and enhanced results",
        ),
        ToolExample(
            description="Fast search without enhancement",
            arguments={"query": "exact search terms", "enhancement": "disabled"},
            expected_result="Direct search results without query modification",
        ),
        ToolExample(
            description="Semantic search for complex topics",
            arguments={
                "query": "machine learning deployment",
                "enhancement": "semantic",
            },
            expected_result="Semantically enhanced search with KeyBERT extraction",
        ),
        ToolExample(
            description="Technical search",
            arguments={
                "query": "Rust memory safety",
                "max_results": 3,
                "technical_level": "expert",
            },
            expected_result="Expert-level search results about Rust memory safety",
        ),
    ],
)
async def web_search(
    query: str,
    enhancement: str | None = None,
    max_results: int | None = None,
    timeframe: str | None = None,
    technical_level: str | None = None,
    conversation_context: str | None = None,
) -> dict:
    """
    Enhanced web search with intelligent query optimization.

    Enhancement modes:
    - auto: Automatically choose best enhancement (YAKE + context)
    - disabled: No enhancement, direct search
    - fast: YAKE-only enhancement (~50ms)
    - semantic: KeyBERT semantic enhancement (~200-500ms)
    - hybrid: YAKE + KeyBERT for best accuracy (~300-600ms)

    Args:
        query: Search query or question
        enhancement: Enhancement mode (uses config default if None)
        max_results: Maximum results to return (1-20)
        timeframe: Preferred time range (recent, past_year, any)
        technical_level: Adjust query complexity (beginner, intermediate, expert)
        conversation_context: Recent conversation context for enhancement (optional)

    Returns:
        Enhanced search results with optimization details
    """
    # Import here to avoid circular dependencies
    try:
        from nova.core.config import config_manager
        from nova.search.manager import EnhancedSearchManager
        from nova.search.models import SearchEnhancementMode, SearchMemoryConstraints
    except ImportError as e:
        # Log import error for debugging
        import logging

        import_logger = logging.getLogger(__name__)
        import_logger.error(f"Import failed in web_search: {e}")
        # Fallback to legacy search
        return await _fallback_search(
            query, max_results or 5, error=f"Import error: {e}"
        )

    try:
        # Get configuration
        config = config_manager.load_config()

        # Apply configuration defaults for None values
        enhancement = enhancement or config.search.default_enhancement
        provider = config.search.default_provider
        max_results = max_results or config.search.max_results
        timeframe = timeframe or config.search.default_timeframe
        technical_level = technical_level or config.search.default_technical_level

        # Convert and validate parameters (handle string inputs from chat interface)
        if provider not in ["duckduckgo", "google", "bing"]:
            provider = "duckduckgo"

        # Convert max_results to int if it's a string
        if isinstance(max_results, str):
            try:
                max_results = int(max_results)
            except ValueError:
                logger.warning(
                    f"Invalid max_results value '{max_results}', using default"
                )
                max_results = config.search.max_results

        max_results = max(1, min(20, max_results))

        # Ensure string parameters are properly handled
        enhancement = str(enhancement) if enhancement is not None else enhancement
        timeframe = str(timeframe) if timeframe is not None else timeframe
        technical_level = (
            str(technical_level) if technical_level is not None else technical_level
        )
        conversation_context = (
            str(conversation_context)
            if conversation_context is not None
            else conversation_context
        )

        # Convert enhancement string to enum
        try:
            enhancement_mode = SearchEnhancementMode(enhancement)
        except ValueError:
            enhancement_mode = SearchEnhancementMode.FAST

        # Create memory constraints
        memory_constraints = SearchMemoryConstraints(
            technical_level=technical_level, timeframe=timeframe, locale="en-US"
        )

        # Enable AI client only if meaningful enhancement is needed
        ai_client = None
        should_create_ai_client = (
            config.search.use_ai_answers  # AI answers enabled in config
            and enhancement_mode
            != SearchEnhancementMode.DISABLED  # Enhancement not disabled
            and (
                not conversation_context or len(conversation_context.strip()) >= 50
            )  # Meaningful context or no context
        )

        if should_create_ai_client:
            # Import AI client when needed to avoid circular dependencies
            try:
                from nova.core.ai_client import create_ai_client

                active_config = config.get_active_ai_config()
                ai_client = create_ai_client(active_config)
            except Exception as e:
                logger.warning(
                    f"Could not initialize AI client for search enhancement: {e}"
                )
                ai_client = None

        # Log if conversation context is being used
        if conversation_context and len(conversation_context.strip()) > 50:
            logger.info(
                "Using conversation context for keyword-based search enhancement"
            )

        # Use provided conversation context or empty string
        context = conversation_context or ""

        # Use EnhancedSearchManager for search with proper cleanup
        search_config = {"search": config.search.model_dump()}

        # Execute search with timeout protection using async context manager
        import asyncio

        # Use the configured timeout from search config, with a reasonable default
        try:
            enhancement_timeout = getattr(config.search, "enhancement_timeout", 30.0)
        except AttributeError:
            enhancement_timeout = 30.0
        search_timeout = (
            enhancement_timeout + 15.0
        )  # Allow enhancement time plus buffer for actual search

        try:
            async with EnhancedSearchManager(
                search_config, ai_client
            ) as search_manager:
                try:
                    logger.info(
                        f"Starting enhanced search for query: {query} (timeout: {search_timeout}s)"
                    )
                    search_response = await asyncio.wait_for(
                        search_manager.enhanced_search(
                            query=query,
                            provider=provider,
                            max_results=max_results,
                            extract_content=True,
                            enhancement_mode=enhancement_mode,
                            conversation_context=context,
                            memory_constraints=memory_constraints,
                        ),
                        timeout=search_timeout,
                    )
                    logger.info("Enhanced search completed successfully")
                except TimeoutError:
                    logger.warning(
                        f"Search operation timed out after {search_timeout} seconds for query: {query}"
                    )
                    # Try a fallback search with simpler settings
                    try:
                        logger.info(
                            "Attempting fallback search with disabled enhancement..."
                        )
                        async with EnhancedSearchManager(
                            search_config, ai_client=None
                        ) as fallback_manager:
                            search_response = await asyncio.wait_for(
                                fallback_manager.enhanced_search(
                                    query=query,
                                    provider=provider,
                                    max_results=3,  # Reduced results for faster search
                                    extract_content=False,  # No content extraction to speed up
                                    enhancement_mode=SearchEnhancementMode.DISABLED,  # No enhancement
                                    conversation_context="",  # No context
                                    memory_constraints=memory_constraints,
                                ),
                                timeout=10.0,  # Shorter timeout for fallback
                            )
                            logger.info("Fallback search completed successfully")
                    except Exception as fallback_error:
                        logger.warning(f"Fallback search also failed: {fallback_error}")
                        return {
                            "query": query,
                            "provider": provider,
                            "results": [],
                            "total_results": 0,
                            "search_time_ms": int(search_timeout * 1000),
                            "enhancement_mode": (
                                enhancement_mode.value
                                if enhancement_mode
                                else "disabled"
                            ),
                            "error": "Search timed out - try with simpler query or disable enhancement",
                        }

            # Format results for tool output
            results = []
            for result in search_response["results"]:
                result_dict = {
                    "title": (
                        result.title
                        if hasattr(result, "title")
                        else result.get("title", "")
                    ),
                    "url": (
                        result.url if hasattr(result, "url") else result.get("url", "")
                    ),
                    "snippet": (
                        result.snippet
                        if hasattr(result, "snippet")
                        else result.get("snippet", "")
                    ),
                    "source": (
                        result.source
                        if hasattr(result, "source")
                        else result.get("source", "")
                    ),
                }

                # Add extracted content if available
                if hasattr(result, "full_content") and result.full_content:
                    result_dict["content"] = result.full_content
                elif isinstance(result, dict) and result.get("full_content"):
                    result_dict["content"] = result["full_content"]

                # Add content summary if available
                if hasattr(result, "content_summary") and result.content_summary:
                    result_dict["content_summary"] = result.content_summary
                elif isinstance(result, dict) and result.get("content_summary"):
                    result_dict["content_summary"] = result["content_summary"]

                if hasattr(result, "extraction_success"):
                    result_dict["extraction_success"] = result.extraction_success
                elif isinstance(result, dict) and "extraction_success" in result:
                    result_dict["extraction_success"] = result["extraction_success"]

                results.append(result_dict)

            # Prepare response
            response = {
                "query": search_response["query"],
                "provider": search_response["provider"],
                "results": results,
                "total_results": search_response["total_results"],
                "search_time_ms": search_response.get("search_time_ms", 0),
            }

            # Add enhancement details if available
            if "enhancement_details" in search_response:
                enhancement_details = search_response["enhancement_details"]
                response["enhancement"] = {
                    "mode": enhancement_details["mode"],
                    "processing_time_ms": enhancement_details["processing_time_ms"],
                    "context_used": enhancement_details["context_used"],
                    "enhanced_queries_count": len(
                        enhancement_details.get("enhanced_queries", [])
                    ),
                }

                # Include enhanced queries for debugging/transparency
                if enhancement_details.get("enhanced_queries"):
                    response["enhancement"]["enhanced_queries"] = [
                        {
                            "query": eq["query"],
                            "priority": eq["priority"],
                            "rationale": eq["rationale"],
                        }
                        for eq in enhancement_details["enhanced_queries"]
                    ]

            return response

        finally:
            # Ensure AI client is properly closed
            if ai_client:
                try:
                    await ai_client.close()
                    logger.debug("AI client closed successfully in web_search")
                except Exception as close_error:
                    logger.warning(
                        f"Error closing AI client in web_search: {close_error}"
                    )

    except Exception as e:
        # Log the full exception for debugging
        import traceback

        logger.error(f"Web search failed: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")

        # Fallback to basic search
        return await _fallback_search(query, max_results or 5, error=str(e))


async def _fallback_search(query: str, max_results: int, error: str = None) -> dict:
    """Fallback search implementation when SearchManager is not available"""
    error_msg = error if error else "Unknown error occurred"
    logger.error(f"Fallback search called for query '{query}' due to: {error_msg}")

    return {
        "query": query,
        "provider": "fallback",
        "results": [
            {
                "title": "Web Search Error",
                "url": "",
                "snippet": f"Web search failed: {error_msg}. Please try again or check your network connection.",
                "source": "nova",
                "content": f"Search error details: {error_msg}",
                "extraction_success": False,
            }
        ],
        "total_results": 1,
        "error": error_msg,
    }


@tool(
    description="Get the current date and time",
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.INFORMATION,
    tags=["time", "date", "timezone"],
    examples=[
        ToolExample(
            description="Get current UTC time",
            arguments={},
            expected_result="Current date and time in UTC",
        ),
        ToolExample(
            description="Get time in specific timezone",
            arguments={
                "timezone": "America/New_York",
                "format": "%B %d, %Y at %I:%M %p",
            },
            expected_result="Current time in New York timezone with custom format",
        ),
    ],
)
async def get_current_time(
    timezone: str = "UTC", format: str = "%Y-%m-%d %H:%M:%S %Z"
) -> dict:
    """
    Get the current date and time.

    Args:
        timezone: Timezone name (e.g., 'UTC', 'America/New_York', 'Europe/London')
        format: Time format string (Python strftime format)

    Returns:
        Dictionary with current time information including formatted time, timestamp, and timezone
    """
    try:
        now = datetime.now(UTC)

        # If specific timezone requested, try to handle it
        if timezone != "UTC":
            try:
                import zoneinfo

                tz = zoneinfo.ZoneInfo(timezone)
                now = now.astimezone(tz)
            except ImportError:
                # Fallback without timezone conversion
                pass
            except Exception:
                # Invalid timezone, stick with UTC
                pass

        return {
            "current_time": now.strftime(format),
            "timestamp": now.timestamp(),
            "timezone": timezone,
            "iso_format": now.isoformat(),
        }

    except Exception as e:
        raise ValueError(f"Failed to get current time: {e}")
