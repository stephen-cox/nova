"""Unified function registry for all callable tools"""

import asyncio
import logging
import time

from nova.models.tools import (
    ExecutionContext,
    PermissionDeniedError,
    ToolDefinition,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolResult,
    ToolSourceType,
    ToolTimeoutError,
)

from .handler import ToolHandler
from .permissions import ToolPermissionManager

logger = logging.getLogger(__name__)


class FunctionRegistry:
    """Unified registry for all callable functions"""

    def __init__(self, nova_config):
        self.nova_config = nova_config
        self.config = nova_config.get_effective_tools_config()
        self.tools: dict[str, ToolDefinition] = {}
        self.handlers: dict[str, ToolHandler] = {}
        self.permission_manager = ToolPermissionManager(self.config.permission_mode)

        # Note: Built-in tools are now discovered automatically using decorators

        # Statistics
        self.execution_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_execution_time": 0,
        }

    async def initialize(self):
        """Initialize the function registry"""
        logger.info("Initializing function registry")

        # Register built-in tools
        await self._register_built_in_tools()

        # TODO: Initialize MCP client if enabled (Phase 2)
        # if self.config.mcp_enabled:
        #     await self._initialize_mcp_integration()

        # TODO: Load user-defined tools (Phase 3)
        # await self._load_user_tools()

        logger.info(f"Function registry initialized with {len(self.tools)} tools")

    def refresh_tools_config(self):
        """Refresh tools configuration when active profile changes"""
        old_config = self.config
        self.config = self.nova_config.get_effective_tools_config()

        # Update permission manager if permission mode changed
        if old_config.permission_mode != self.config.permission_mode:
            self.permission_manager = ToolPermissionManager(self.config.permission_mode)
            logger.info(f"Updated permission mode to: {self.config.permission_mode}")

        # Re-register built-in tools if enabled modules changed
        if old_config.enabled_built_in_modules != self.config.enabled_built_in_modules:
            logger.info("Enabled modules changed, re-registering built-in tools")
            # Clear existing tools and re-register
            self.tools.clear()
            self.handlers.clear()
            # Re-initialize with new config
            import asyncio

            asyncio.create_task(self._register_built_in_tools())

    def register_tool(self, tool: ToolDefinition, handler: ToolHandler) -> None:
        """Register a tool with its handler"""

        if tool.name in self.tools:
            logger.warning(f"Overriding existing tool: {tool.name}")

        self.tools[tool.name] = tool
        self.handlers[tool.name] = handler

        logger.debug(f"Registered tool: {tool.name} ({tool.source_type})")

    async def execute_tool(
        self, tool_name: str, arguments: dict, context: ExecutionContext = None
    ) -> ToolResult:
        """Execute a tool with permission checking and error handling"""

        if tool_name not in self.tools:
            error_msg = f"Tool '{tool_name}' not found"
            logger.error(error_msg)
            raise ToolNotFoundError(error_msg)

        tool = self.tools[tool_name]
        handler = self.handlers[tool_name]

        # Update stats
        self.execution_stats["total_calls"] += 1

        # Permission check
        try:
            if not await self.permission_manager.check_permission(
                tool, arguments, context
            ):
                error_msg = f"Permission denied for tool '{tool_name}'"
                logger.warning(error_msg)
                raise PermissionDeniedError(error_msg)
        except Exception as e:
            if isinstance(e, PermissionDeniedError):
                raise
            logger.error(f"Permission check failed for tool '{tool_name}': {e}")
            raise PermissionDeniedError(f"Permission check failed: {e}")

        # Validate arguments if handler supports it
        if hasattr(handler, "validate_arguments"):
            try:
                if not handler.validate_arguments(arguments):
                    raise ToolExecutionError(tool_name, "Invalid arguments provided")
            except Exception as e:
                raise ToolExecutionError(tool_name, f"Argument validation failed: {e}")

        # Execute with timeout and error handling
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                handler.execute(arguments, context),
                timeout=self.config.execution_timeout,
            )

            execution_time = int((time.time() - start_time) * 1000)
            self.execution_stats["successful_calls"] += 1
            self.execution_stats["total_execution_time"] += execution_time

            logger.debug(
                f"Tool '{tool_name}' executed successfully in {execution_time}ms"
            )

            return ToolResult(
                success=True,
                result=result,
                tool_name=tool_name,
                execution_time_ms=execution_time,
            )

        except TimeoutError:
            execution_time = int((time.time() - start_time) * 1000)
            self.execution_stats["failed_calls"] += 1
            error_msg = (
                f"Tool execution timed out after {self.config.execution_timeout}s"
            )
            logger.error(f"Tool '{tool_name}' timed out after {execution_time}ms")

            raise ToolTimeoutError(error_msg)

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            self.execution_stats["failed_calls"] += 1

            if isinstance(e, ToolError):
                raise

            error_msg = str(e)
            logger.error(
                f"Tool '{tool_name}' failed after {execution_time}ms: {error_msg}"
            )

            # Create helpful error with recovery suggestions
            recovery_suggestions = self._get_recovery_suggestions(tool_name, error_msg)
            raise ToolExecutionError(tool_name, error_msg, recovery_suggestions)

        finally:
            # Cleanup if handler supports it
            if hasattr(handler, "cleanup"):
                try:
                    await handler.cleanup()
                except Exception as e:
                    logger.warning(f"Cleanup failed for tool '{tool_name}': {e}")

    def get_available_tools(
        self, context: ExecutionContext | None = None
    ) -> list[ToolDefinition]:
        """Get all available tools for current context"""

        available = []
        for tool in self.tools.values():
            if self.permission_manager.is_tool_available(tool, context):
                available.append(tool)

        return available

    def get_tools_by_category(
        self, category: str, context: ExecutionContext | None = None
    ) -> list[ToolDefinition]:
        """Get tools filtered by category"""

        available_tools = self.get_available_tools(context)
        return [tool for tool in available_tools if tool.category.value == category]

    def get_tools_by_source(
        self, source_type: ToolSourceType, context: ExecutionContext | None = None
    ) -> list[ToolDefinition]:
        """Get tools filtered by source type"""

        available_tools = self.get_available_tools(context)
        return [tool for tool in available_tools if tool.source_type == source_type]

    def search_tools(
        self, query: str, context: ExecutionContext | None = None
    ) -> list[ToolDefinition]:
        """Search tools by name, description, or tags"""

        query_lower = query.lower()
        available_tools = self.get_available_tools(context)

        matching_tools = []
        for tool in available_tools:
            # Check name
            if query_lower in tool.name.lower():
                matching_tools.append(tool)
                continue

            # Check description
            if query_lower in tool.description.lower():
                matching_tools.append(tool)
                continue

            # Check tags
            if any(query_lower in tag.lower() for tag in tool.tags):
                matching_tools.append(tool)
                continue

        return matching_tools

    def get_openai_tools_schema(
        self, context: ExecutionContext | None = None
    ) -> list[dict]:
        """Get OpenAI-compatible tools schema"""

        available_tools = self.get_available_tools(context)
        return [tool.to_openai_schema() for tool in available_tools]

    def get_tool_info(self, tool_name: str) -> ToolDefinition | None:
        """Get information about a specific tool"""
        return self.tools.get(tool_name)

    def list_tool_names(self, context: ExecutionContext | None = None) -> list[str]:
        """Get list of available tool names"""
        available_tools = self.get_available_tools(context)
        return [tool.name for tool in available_tools]

    def get_execution_stats(self) -> dict:
        """Get execution statistics"""
        stats = self.execution_stats.copy()

        # Calculate success rate
        total_calls = stats["total_calls"]
        if total_calls > 0:
            stats["success_rate"] = stats["successful_calls"] / total_calls
            stats["average_execution_time"] = (
                stats["total_execution_time"] / total_calls
            )
        else:
            stats["success_rate"] = 0
            stats["average_execution_time"] = 0

        stats["registered_tools"] = len(self.tools)
        return stats

    async def _register_built_in_tools(self):
        """Register all built-in tools using automatic discovery"""

        try:
            # Use automatic tool discovery
            from nova.tools.registry import discover_built_in_tools

            # Discover all built-in tools
            discovered_tools = discover_built_in_tools()

            # Get enabled modules configuration
            enabled_modules = getattr(
                self.config,
                "enabled_built_in_modules",
                ["file_ops", "web_search", "conversation", "network_tools"],
            )

            # Register tools from enabled modules
            registered_count = 0
            for tool_name, (tool_def, handler) in discovered_tools.items():
                # Check if tool's module is enabled
                tool_module = self._get_tool_module_name(tool_def)

                if tool_module in enabled_modules:
                    try:
                        self.register_tool(tool_def, handler)
                        registered_count += 1
                        logger.debug(f"Registered tool: {tool_name} from {tool_module}")
                    except Exception as e:
                        logger.error(f"Failed to register tool '{tool_name}': {e}")
                        continue
                else:
                    logger.debug(
                        f"Skipping disabled tool: {tool_name} from {tool_module}"
                    )

            logger.info(
                f"Registered {registered_count} built-in tools from {len(enabled_modules)} enabled modules"
            )

        except Exception as e:
            logger.error(f"Failed to register built-in tools: {e}")

    def _get_tool_module_name(self, tool_def: ToolDefinition) -> str:
        """Extract module name from tool definition"""
        # Get the module name from the handler's source
        if hasattr(tool_def, "handler") and hasattr(tool_def.handler, "func"):
            module = getattr(tool_def.handler.func, "__module__", "")
            if "nova.tools.built_in." in module:
                return module.split("nova.tools.built_in.")[1]

        # Fallback: try to infer from tool name or tags
        if "file" in tool_def.tags or "directory" in tool_def.tags:
            return "file_ops"
        elif (
            "web" in tool_def.tags
            or "search" in tool_def.tags
            or "time" in tool_def.tags
        ):
            return "web_search"
        elif "conversation" in tool_def.tags or "history" in tool_def.tags:
            return "conversation"
        elif "network" in tool_def.tags or "ip" in tool_def.tags:
            return "network_tools"

        # Default fallback
        return "unknown"

    def _get_recovery_suggestions(self, tool_name: str, error_msg: str) -> list[str]:
        """Get helpful recovery suggestions for tool errors"""

        suggestions = []
        error_lower = error_msg.lower()

        # File-related errors
        if "file not found" in error_lower or "no such file" in error_lower:
            suggestions.extend(
                [
                    "Check if the file path is correct",
                    "Verify the file exists using list_directory tool",
                    "Use absolute path instead of relative path",
                ]
            )

        # Permission errors
        if "permission denied" in error_lower or "access denied" in error_lower:
            suggestions.extend(
                [
                    "Check file permissions",
                    "Try running with elevated privileges",
                    "Verify you have access to the directory",
                ]
            )

        # Network errors
        if (
            "network" in error_lower
            or "connection" in error_lower
            or "timeout" in error_lower
        ):
            suggestions.extend(
                [
                    "Check your internet connection",
                    "Try again in a few moments",
                    "Verify the URL or service is accessible",
                ]
            )

        # Invalid arguments
        if "argument" in error_lower or "parameter" in error_lower:
            suggestions.extend(
                [
                    "Check the tool's parameter requirements",
                    "Verify argument types match the expected schema",
                    "Use /tool info <tool_name> to see usage examples",
                ]
            )

        return suggestions

    async def cleanup(self):
        """Cleanup all registered tools and handlers"""

        logger.info("Cleaning up function registry")

        # Clear registries
        self.tools.clear()
        self.handlers.clear()

        logger.info("Function registry cleanup completed")
