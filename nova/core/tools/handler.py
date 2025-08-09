"""Base tool handler interface"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from nova.models.tools import ExecutionContext


class ToolHandler(ABC):
    """Abstract base class for tool handlers"""

    @abstractmethod
    async def execute(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> Any:
        """Execute the tool with given arguments"""
        pass

    def validate_arguments(self, arguments: dict[str, Any]) -> bool:
        """Validate tool arguments (override in subclasses if needed)"""
        return True

    async def cleanup(self) -> None:  # noqa: B027
        """Cleanup resources after tool execution (override if needed)"""
        pass


class BuiltInToolModule(ABC):
    """Base class for built-in tool modules"""

    @abstractmethod
    async def get_tools(self) -> list[tuple[Any, Any]]:
        """Get all tools provided by this module"""
        pass

    async def initialize(self) -> None:  # noqa: B027
        """Initialize the tool module (override if needed)"""
        pass

    async def cleanup(self) -> None:  # noqa: B027
        """Cleanup module resources (override if needed)"""
        pass


class AsyncToolHandler(ToolHandler):
    """Base class for async tool handlers with timeout support"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def execute_with_timeout(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> Any:
        """Execute tool with timeout protection"""
        try:
            return await asyncio.wait_for(
                self.execute(arguments, context), timeout=self.timeout
            )
        except TimeoutError:
            raise TimeoutError(f"Tool execution timed out after {self.timeout}s")


class SyncToolHandler(ToolHandler):
    """Base class for synchronous tool handlers that need async wrapper"""

    @abstractmethod
    def execute_sync(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> Any:
        """Execute the tool synchronously"""
        pass

    async def execute(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> Any:
        """Async wrapper for sync execution"""
        # Run sync code in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute_sync, arguments, context)
