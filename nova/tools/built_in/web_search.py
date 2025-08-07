"""Enhanced web search tools"""

from datetime import UTC
from typing import Any

from nova.core.tools.handler import AsyncToolHandler, BuiltInToolModule
from nova.models.tools import (
    ExecutionContext,
    PermissionLevel,
    ToolCategory,
    ToolDefinition,
    ToolExample,
    ToolSourceType,
)


class WebSearchHandler(AsyncToolHandler):
    """Handler for web search functionality"""

    def __init__(self, search_config: dict = None):
        super().__init__()
        self.search_config = search_config or {}

    async def execute(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> dict:
        query = arguments["query"]
        provider = arguments.get(
            "provider", self.search_config.get("default_provider", "duckduckgo")
        )
        max_results = arguments.get(
            "max_results", self.search_config.get("max_results", 5)
        )
        include_content = arguments.get("include_content", True)

        # Import here to avoid circular dependencies
        try:
            from nova.core.search import SearchManager
        except ImportError:
            # Fallback implementation
            return await self._fallback_search(query, max_results)

        # Convert config to expected format for SearchManager
        search_config = {
            "search": {
                "google": self.search_config.get("google", {}),
                "bing": self.search_config.get("bing", {}),
            }
        }

        # Get AI client for content summarization if available
        ai_client = None
        if include_content and self.search_config.get("use_ai_answers", True):
            try:
                # This would need the AI config - for now skip AI summarization
                pass
            except Exception:
                pass

        try:
            # Use SearchManager directly for async operation
            search_manager = SearchManager(search_config)
            search_response = await search_manager.search(
                query=query,
                provider=provider,
                max_results=max_results,
                extract_content=include_content,
                ai_client=ai_client,
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
            return await self._fallback_search(query, max_results, error=str(e))

    async def _fallback_search(
        self, query: str, max_results: int, error: str = None
    ) -> dict:
        """Fallback search implementation"""

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


class GetCurrentTimeHandler(AsyncToolHandler):
    """Handler for getting current time and date"""

    async def execute(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> dict:
        from datetime import datetime

        timezone_name = arguments.get("timezone", "UTC")
        format_str = arguments.get("format", "%Y-%m-%d %H:%M:%S %Z")

        try:
            now = datetime.now(UTC)

            # If specific timezone requested, try to handle it
            if timezone_name != "UTC":
                try:
                    import zoneinfo

                    tz = zoneinfo.ZoneInfo(timezone_name)
                    now = now.astimezone(tz)
                except ImportError:
                    # Fallback without timezone conversion
                    pass
                except Exception:
                    # Invalid timezone, stick with UTC
                    pass

            return {
                "current_time": now.strftime(format_str),
                "timestamp": now.timestamp(),
                "timezone": timezone_name,
                "iso_format": now.isoformat(),
            }

        except Exception as e:
            raise ValueError(f"Failed to get current time: {e}")


class WebSearchTools(BuiltInToolModule):
    """Enhanced web search and information tools"""

    def __init__(self, search_config: dict = None):
        self.search_config = search_config or {}

    async def get_tools(self) -> list[tuple[ToolDefinition, Any]]:
        return [
            (
                ToolDefinition(
                    name="web_search",
                    description="Search the web for information on any topic",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query or question",
                            },
                            "provider": {
                                "type": "string",
                                "enum": ["duckduckgo", "google", "bing"],
                                "description": "Search provider to use (default: duckduckgo)",
                            },
                            "max_results": {
                                "type": "integer",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 20,
                                "description": "Maximum number of results to return",
                            },
                            "include_content": {
                                "type": "boolean",
                                "default": True,
                                "description": "Include detailed content extraction from pages",
                            },
                        },
                        "required": ["query"],
                    },
                    source_type=ToolSourceType.BUILT_IN,
                    permission_level=PermissionLevel.SAFE,
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
                ),
                WebSearchHandler(self.search_config),
            ),
            (
                ToolDefinition(
                    name="get_current_time",
                    description="Get the current date and time",
                    parameters={
                        "type": "object",
                        "properties": {
                            "timezone": {
                                "type": "string",
                                "default": "UTC",
                                "description": "Timezone name (e.g., 'UTC', 'America/New_York', 'Europe/London')",
                            },
                            "format": {
                                "type": "string",
                                "default": "%Y-%m-%d %H:%M:%S %Z",
                                "description": "Time format string (Python strftime format)",
                            },
                        },
                    },
                    source_type=ToolSourceType.BUILT_IN,
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
                ),
                GetCurrentTimeHandler(),
            ),
        ]
