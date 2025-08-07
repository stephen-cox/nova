"""Tools and function calling models"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ToolSourceType(str, Enum):
    """Source type for tools"""

    BUILT_IN = "built_in"
    MCP_SERVER = "mcp_server"
    USER_DEFINED = "user_defined"
    PLUGIN = "plugin"


class PermissionLevel(str, Enum):
    """Permission levels for tool execution"""

    SAFE = "safe"  # No user confirmation needed
    ELEVATED = "elevated"  # User confirmation required
    SYSTEM = "system"  # Admin/explicit approval needed
    DANGEROUS = "dangerous"  # Blocked by default


class ToolCategory(str, Enum):
    """Categories for organizing tools"""

    FILE_SYSTEM = "file_system"
    INFORMATION = "information"
    PRODUCTIVITY = "productivity"
    COMMUNICATION = "communication"
    DEVELOPMENT = "development"
    SYSTEM = "system"
    GENERAL = "general"


class ToolExample(BaseModel):
    """Example usage of a tool"""

    description: str = Field(description="Description of the example")
    arguments: dict[str, Any] = Field(description="Example arguments")
    expected_result: str | None = Field(
        default=None, description="Expected result description"
    )


class ToolDefinition(BaseModel):
    """Universal tool definition"""

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    parameters: dict[str, Any] = Field(description="JSON Schema for parameters")
    source_type: ToolSourceType = Field(description="Tool source")
    source_id: str | None = Field(
        default=None, description="Source identifier (e.g., MCP server name)"
    )
    permission_level: PermissionLevel = Field(default=PermissionLevel.SAFE)
    category: ToolCategory = Field(default=ToolCategory.GENERAL)
    tags: list[str] = Field(default_factory=list)
    examples: list[ToolExample] = Field(default_factory=list)
    enabled: bool = Field(default=True, description="Whether tool is enabled")

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolCall(BaseModel):
    """Represents a tool call request"""

    id: str | None = Field(default=None, description="Tool call ID")
    tool_name: str = Field(description="Name of tool to call")
    arguments: dict[str, Any] = Field(description="Tool arguments")
    timestamp: datetime = Field(default_factory=datetime.now)


class ToolResult(BaseModel):
    """Tool execution result"""

    success: bool
    result: Any | None = None
    error: str | None = None
    tool_name: str
    execution_time_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "tool_name": self.tool_name,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


class ToolAwareResponse(BaseModel):
    """AI response that may include tool usage"""

    content: str
    tool_calls_made: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    suggested_tools: list[str] = Field(default_factory=list)


class ExecutionContext(BaseModel):
    """Context for tool execution"""

    conversation_id: str | None = None
    user_id: str | None = None
    session_data: dict[str, Any] = Field(default_factory=dict)
    working_directory: str | None = None
    environment_vars: dict[str, str] = Field(default_factory=dict)


# Exceptions
class ToolError(Exception):
    """Base exception for tool-related errors"""

    pass


class ToolNotFoundError(ToolError):
    """Raised when a tool is not found"""

    pass


class PermissionDeniedError(ToolError):
    """Raised when tool execution is not permitted"""

    pass


class ToolExecutionError(ToolError):
    """Raised when tool execution fails"""

    def __init__(
        self, tool_name: str, error: str, recovery_suggestions: list[str] = None
    ):
        self.tool_name = tool_name
        self.error = error
        self.recovery_suggestions = recovery_suggestions or []
        super().__init__(f"Tool '{tool_name}' failed: {error}")


class ToolTimeoutError(ToolError):
    """Raised when tool execution times out"""

    pass
