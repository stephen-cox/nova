"""Nova Tools Package

This package contains all tool implementations for Nova, including:
- Built-in tools (file operations, web search, conversation tools)
- User-defined tools (custom tools created by users)
- MCP tools (Model Context Protocol integrations)

The tools system uses a decorator-based approach for easy tool creation
and automatic registration with the tool registry.
"""

from .decorators import tool
from .registry import (
    ToolRegistry,
    discover_all_tools,
    discover_built_in_tools,
    discover_user_tools,
    get_global_registry,
)

__all__ = [
    "tool",
    "ToolRegistry",
    "get_global_registry",
    "discover_built_in_tools",
    "discover_user_tools",
    "discover_all_tools",
]
