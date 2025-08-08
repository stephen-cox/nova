"""Web search and time tools

These tools provide web search functionality and current time information.
"""

from datetime import UTC, datetime

from nova.models.tools import PermissionLevel, ToolCategory, ToolExample
from nova.tools import tool


@tool(
    description="Search the web for information on any topic",
    permission_level=PermissionLevel.ELEVATED,
    category=ToolCategory.INFORMATION,
    tags=["web", "search", "internet", "information"],
    examples=[
        ToolExample(
            description="Search for current events",
            arguments={"query": "latest AI developments 2024"},
            expected_result="Web search results with titles, URLs, and summaries",
        ),
        ToolExample(
            description="Technical search with specific provider",
            arguments={
                "query": "Python async best practices",
                "provider": "google",
                "max_results": 3,
            },
            expected_result="Top 3 Google search results about Python async",
        ),
    ],
)
async def web_search(
    query: str,
    provider: str = "duckduckgo",
    max_results: int = 5,
    include_content: bool = True,
) -> dict:
    """
    Search the web for information on any topic.

    Args:
        query: Search query or question
        provider: Search provider to use (duckduckgo, google, bing)
        max_results: Maximum number of results to return (1-20)
        include_content: Include detailed content extraction from pages

    Returns:
        Dictionary with search results including titles, URLs, and summaries
    """
    # Validate provider
    if provider not in ["duckduckgo", "google", "bing"]:
        provider = "duckduckgo"

    # Validate max_results
    max_results = max(1, min(20, max_results))

    # Import here to avoid circular dependencies
    try:
        from nova.core.search import SearchManager
    except ImportError:
        # Fallback implementation
        return await _fallback_search(query, max_results)

    # Convert config to expected format for SearchManager
    search_config = {
        "search": {
            "google": {},
            "bing": {},
        }
    }

    try:
        # Use SearchManager directly for async operation
        search_manager = SearchManager(search_config)
        search_response = await search_manager.search(
            query=query,
            provider=provider,
            max_results=max_results,
            extract_content=include_content,
            ai_client=None,  # Skip AI summarization for now
        )

        # Close the search manager after use
        await search_manager.close()

        # Format results
        results = []
        for result in search_response.results:
            result_dict = {
                "title": result.title,
                "url": result.url,
                "snippet": result.snippet,
                "source": result.source,
            }

            # Add enhanced content if available
            if hasattr(result, "content_summary") and result.content_summary:
                result_dict["content_summary"] = result.content_summary
                result_dict["extraction_success"] = getattr(
                    result, "extraction_success", True
                )

            results.append(result_dict)

        return {
            "query": query,
            "provider": provider,
            "results": results,
            "total_results": len(results),
        }

    except Exception as e:
        # Fallback to basic search
        return await _fallback_search(query, max_results, error=str(e))


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
