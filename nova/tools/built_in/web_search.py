"""Enhanced web search and time tools

These tools provide advanced web search functionality with intelligent query enhancement
and current time information.
"""

from datetime import UTC, datetime
from typing import Optional

from nova.models.tools import PermissionLevel, ToolCategory, ToolExample
from nova.tools import tool


@tool(
    description="Intelligent web search with context-aware query enhancement",
    permission_level=PermissionLevel.ELEVATED,
    category=ToolCategory.INFORMATION,
    tags=["web", "search", "internet", "nlp", "enhanced"],
    examples=[
        ToolExample(
            description="Enhanced search with automatic optimization",
            arguments={"query": "Python async programming", "enhancement": "auto"},
            expected_result="Optimized search queries with extracted keywords and enhanced results",
        ),
        ToolExample(
            description="Fast search without enhancement",
            arguments={"query": "exact search terms", "enhancement": "disabled"},
            expected_result="Direct search results without query modification",
        ),
        ToolExample(
            description="Semantic search for complex topics",
            arguments={"query": "machine learning deployment", "enhancement": "semantic"},
            expected_result="Semantically enhanced search with KeyBERT extraction",
        ),
        ToolExample(
            description="Technical search with specific provider",
            arguments={
                "query": "Rust memory safety",
                "provider": "google",
                "max_results": 3,
                "technical_level": "expert"
            },
            expected_result="Expert-level search results about Rust memory safety",
        ),
    ],
)
async def web_search(
    query: str,
    enhancement: Optional[str] = None,
    provider: Optional[str] = None,
    max_results: Optional[int] = None,
    include_content: bool = True,
    timeframe: Optional[str] = None,
    technical_level: Optional[str] = None,
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
        provider: Search provider (duckduckgo, google, bing)
        max_results: Maximum results to return (1-20)
        include_content: Extract detailed content from pages
        timeframe: Preferred time range (recent, past_year, any)
        technical_level: Adjust query complexity (beginner, intermediate, expert)

    Returns:
        Enhanced search results with optimization details
    """
    # Import here to avoid circular dependencies
    try:
        from nova.search.manager import EnhancedSearchManager
        from nova.search.models import SearchEnhancementMode, SearchMemoryConstraints
        from nova.core.config import config_manager
    except ImportError:
        # Fallback to legacy search
        return await _fallback_search(query, max_results or 5)

    try:
        # Get configuration
        config = config_manager.load_config()
        
        # Apply configuration defaults for None values
        enhancement = enhancement or config.search.default_enhancement
        provider = provider or config.search.default_provider
        max_results = max_results or config.search.max_results
        timeframe = timeframe or config.search.default_timeframe
        technical_level = technical_level or config.search.default_technical_level

        # Validate parameters
        if provider not in ["duckduckgo", "google", "bing"]:
            provider = "duckduckgo"
        max_results = max(1, min(20, max_results))
        
        # Convert enhancement string to enum
        try:
            enhancement_mode = SearchEnhancementMode(enhancement)
        except ValueError:
            enhancement_mode = SearchEnhancementMode.FAST

        # Create memory constraints
        memory_constraints = SearchMemoryConstraints(
            technical_level=technical_level,
            timeframe=timeframe,
            locale="en-US"
        )

        # Get AI client for query enhancement (from tool context)
        ai_client = None
        conversation_context = ""
        try:
            from nova.core.ai_client import create_ai_client
            active_config = config.get_active_ai_config()
            ai_client = create_ai_client(active_config)
            
            # TODO: Extract conversation context from tool execution context
            # This would be populated by the chat manager when tools are called
            # For now, we'll let the search manager handle enhancement without context
        except Exception:
            pass

        # Use EnhancedSearchManager for search
        search_config = {
            "search": config.search.model_dump()
        }
        search_manager = EnhancedSearchManager(search_config, ai_client)
        
        search_response = await search_manager.enhanced_search(
            query=query,
            provider=provider,
            max_results=max_results,
            extract_content=include_content,
            enhancement_mode=enhancement_mode,
            conversation_context=conversation_context,
            memory_constraints=memory_constraints
        )

        # Close the search manager after use
        await search_manager.close()

        # Format results for tool output
        results = []
        for result in search_response["results"]:
            result_dict = {
                "title": result.title if hasattr(result, 'title') else result.get('title', ''),
                "url": result.url if hasattr(result, 'url') else result.get('url', ''),
                "snippet": result.snippet if hasattr(result, 'snippet') else result.get('snippet', ''),
                "source": result.source if hasattr(result, 'source') else result.get('source', ''),
            }

            # Add enhanced content if available
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
            "search_time_ms": search_response.get("search_time_ms", 0)
        }

        # Add enhancement details if available
        if "enhancement_details" in search_response:
            enhancement_details = search_response["enhancement_details"]
            response["enhancement"] = {
                "mode": enhancement_details["mode"],
                "processing_time_ms": enhancement_details["processing_time_ms"],
                "context_used": enhancement_details["context_used"],
                "enhanced_queries_count": len(enhancement_details.get("enhanced_queries", []))
            }
            
            # Include enhanced queries for debugging/transparency
            if enhancement_details.get("enhanced_queries"):
                response["enhancement"]["enhanced_queries"] = [
                    {
                        "query": eq["query"],
                        "priority": eq["priority"],
                        "rationale": eq["rationale"]
                    } for eq in enhancement_details["enhanced_queries"]
                ]

        return response

    except Exception as e:
        # Fallback to basic search
        return await _fallback_search(query, max_results or 5, error=str(e))


async def _fallback_search(query: str, max_results: int, error: str = None) -> dict:
    """Fallback search implementation when SearchManager is not available"""
    return {
        "query": query,
        "provider": "fallback",
        "results": [
            {
                "title": "Search functionality temporarily unavailable",
                "url": "",
                "snippet": f"Web search is not available. {error if error else 'Please check your configuration.'}",
                "source": "nova",
            }
        ],
        "total_results": 1,
        "error": error,
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
