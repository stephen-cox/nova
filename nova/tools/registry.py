"""Tool auto-discovery and registration system"""

import importlib
import inspect
import logging
import pkgutil

from nova.core.tools.handler import ToolHandler
from nova.models.tools import ToolDefinition

from .decorators import get_tool_metadata, is_tool_function

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Auto-discovery and registration system for tools"""

    def __init__(self):
        self.discovered_tools: dict[str, tuple[ToolDefinition, ToolHandler]] = {}
        self._discovery_paths: list[str] = []

    def add_discovery_path(self, module_path: str) -> None:
        """Add a module path for tool discovery"""
        if module_path not in self._discovery_paths:
            self._discovery_paths.append(module_path)
            logger.debug(f"Added discovery path: {module_path}")

    def discover_tools(
        self, module_paths: list[str] = None
    ) -> dict[str, tuple[ToolDefinition, ToolHandler]]:
        """
        Discover all tools from specified module paths.

        Args:
            module_paths: List of module paths to scan. If None, uses registered paths.

        Returns:
            Dictionary mapping tool names to (ToolDefinition, ToolHandler) tuples
        """
        if module_paths:
            paths_to_scan = module_paths
        else:
            paths_to_scan = self._discovery_paths

        self.discovered_tools.clear()

        for module_path in paths_to_scan:
            self._discover_in_module(module_path)

        logger.info(
            f"Discovered {len(self.discovered_tools)} tools from {len(paths_to_scan)} modules"
        )
        return self.discovered_tools.copy()

    def _discover_in_module(self, module_path: str) -> None:
        """Discover tools in a specific module path"""
        try:
            # Import the module
            module = importlib.import_module(module_path)

            # Scan for submodules
            if hasattr(module, "__path__"):
                for importer, modname, ispkg in pkgutil.iter_modules(module.__path__):
                    submodule_path = f"{module_path}.{modname}"
                    self._scan_module_for_tools(submodule_path)
            else:
                # Single module
                self._scan_module_for_tools(module_path)

        except ImportError as e:
            logger.warning(f"Could not import module {module_path}: {e}")
        except Exception as e:
            logger.error(f"Error discovering tools in {module_path}: {e}")

    def _scan_module_for_tools(self, module_path: str) -> None:
        """Scan a specific module for decorated tool functions"""
        try:
            module = importlib.import_module(module_path)

            # Look for tool-decorated functions
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and is_tool_function(obj):
                    try:
                        tool_def, handler = get_tool_metadata(obj)

                        if tool_def.name in self.discovered_tools:
                            logger.warning(
                                f"Duplicate tool name '{tool_def.name}' found in {module_path}"
                            )
                            continue

                        self.discovered_tools[tool_def.name] = (tool_def, handler)
                        logger.debug(
                            f"Discovered tool '{tool_def.name}' in {module_path}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Error processing tool {name} in {module_path}: {e}"
                        )

        except ImportError as e:
            logger.warning(f"Could not import module {module_path}: {e}")
        except Exception as e:
            logger.error(f"Error scanning module {module_path}: {e}")

    def get_tool(self, name: str) -> tuple[ToolDefinition, ToolHandler] | None:
        """Get a specific tool by name"""
        return self.discovered_tools.get(name)

    def list_tool_names(self) -> list[str]:
        """Get list of all discovered tool names"""
        return list(self.discovered_tools.keys())

    def filter_tools_by_category(
        self, category: str
    ) -> dict[str, tuple[ToolDefinition, ToolHandler]]:
        """Filter tools by category"""
        return {
            name: (tool_def, handler)
            for name, (tool_def, handler) in self.discovered_tools.items()
            if tool_def.category.value == category
        }

    def filter_tools_by_tag(
        self, tag: str
    ) -> dict[str, tuple[ToolDefinition, ToolHandler]]:
        """Filter tools by tag"""
        return {
            name: (tool_def, handler)
            for name, (tool_def, handler) in self.discovered_tools.items()
            if tag in tool_def.tags
        }

    def search_tools(self, query: str) -> dict[str, tuple[ToolDefinition, ToolHandler]]:
        """Search tools by name or description"""
        query_lower = query.lower()
        return {
            name: (tool_def, handler)
            for name, (tool_def, handler) in self.discovered_tools.items()
            if (
                query_lower in name.lower()
                or query_lower in tool_def.description.lower()
                or any(query_lower in tag.lower() for tag in tool_def.tags)
            )
        }


# Global registry instance
_global_registry = ToolRegistry()


def get_global_registry() -> ToolRegistry:
    """Get the global tool registry instance"""
    return _global_registry


def discover_built_in_tools() -> dict[str, tuple[ToolDefinition, ToolHandler]]:
    """Discover all built-in tools"""
    registry = get_global_registry()
    registry.add_discovery_path("nova.tools.built_in")
    return registry.discover_tools(["nova.tools.built_in"])


def discover_user_tools() -> dict[str, tuple[ToolDefinition, ToolHandler]]:
    """Discover user-defined tools"""
    registry = get_global_registry()
    registry.add_discovery_path("nova.tools.user")
    return registry.discover_tools(["nova.tools.user"])


def discover_all_tools() -> dict[str, tuple[ToolDefinition, ToolHandler]]:
    """Discover all tools from all sources"""
    registry = get_global_registry()
    registry.add_discovery_path("nova.tools.built_in")
    registry.add_discovery_path("nova.tools.user")
    registry.add_discovery_path("nova.tools.mcp")

    return registry.discover_tools(
        ["nova.tools.built_in", "nova.tools.user", "nova.tools.mcp"]
    )
