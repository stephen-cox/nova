"""Tests for tools models and data structures"""

from nova.models.tools import (
    ExecutionContext,
    PermissionDeniedError,
    PermissionLevel,
    ToolCategory,
    ToolDefinition,
    ToolExample,
    ToolExecutionError,
    ToolNotFoundError,
    ToolResult,
    ToolSourceType,
    ToolTimeoutError,
)


class TestExecutionContext:
    """Test execution context model"""

    def test_create_basic_context(self):
        """Test basic context creation"""
        context = ExecutionContext(conversation_id="test-123")

        assert context.conversation_id == "test-123"
        assert context.working_directory is None
        assert context.session_data == {}

    def test_create_full_context(self):
        """Test full context creation"""
        session_data = {"user": "alice", "preferences": {"theme": "dark"}}
        context = ExecutionContext(
            conversation_id="chat-456",
            working_directory="/home/user/project",
            session_data=session_data,
        )

        assert context.conversation_id == "chat-456"
        assert context.working_directory == "/home/user/project"
        assert context.session_data == session_data


class TestToolDefinition:
    """Test tool definition model"""

    def test_create_minimal_tool(self):
        """Test minimal tool definition"""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            source_type=ToolSourceType.BUILT_IN,
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.source_type == ToolSourceType.BUILT_IN
        assert tool.permission_level == PermissionLevel.SAFE
        assert tool.category == ToolCategory.GENERAL
        assert tool.tags == []
        assert tool.examples == []

    def test_create_full_tool(self):
        """Test full tool definition with all fields"""
        parameters = {
            "type": "object",
            "properties": {"input": {"type": "string", "description": "Input text"}},
            "required": ["input"],
        }

        examples = [
            ToolExample(
                description="Example usage",
                arguments={"input": "test"},
                expected_result="Success",
            )
        ]

        tool = ToolDefinition(
            name="advanced_tool",
            description="An advanced tool with all features",
            parameters=parameters,
            source_type=ToolSourceType.MCP_SERVER,
            permission_level=PermissionLevel.ELEVATED,
            category=ToolCategory.FILE_SYSTEM,
            tags=["file", "advanced"],
            examples=examples,
        )

        assert tool.name == "advanced_tool"
        assert tool.description == "An advanced tool with all features"
        assert tool.parameters == parameters
        assert tool.source_type == ToolSourceType.MCP_SERVER
        assert tool.permission_level == PermissionLevel.ELEVATED
        assert tool.category == ToolCategory.FILE_SYSTEM
        assert tool.tags == ["file", "advanced"]
        assert len(tool.examples) == 1
        assert tool.examples[0].description == "Example usage"

    def test_to_openai_schema(self):
        """Test OpenAI schema conversion"""
        tool = ToolDefinition(
            name="format_text",
            description="Format text with style",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to format"},
                    "style": {
                        "type": "string",
                        "enum": ["bold", "italic"],
                        "description": "Formatting style",
                    },
                },
                "required": ["text"],
            },
            source_type=ToolSourceType.BUILT_IN,
        )

        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "format_text"
        assert schema["function"]["description"] == "Format text with style"
        assert schema["function"]["parameters"] == tool.parameters


class TestToolResult:
    """Test tool execution result model"""

    def test_successful_result(self):
        """Test successful tool result"""
        result = ToolResult(
            success=True,
            result="Operation completed successfully",
            tool_name="test_tool",
            execution_time_ms=150,
        )

        assert result.success is True
        assert result.result == "Operation completed successfully"
        assert result.tool_name == "test_tool"
        assert result.execution_time_ms == 150
        assert result.error is None

    def test_failed_result(self):
        """Test failed tool result"""
        result = ToolResult(
            success=False,
            result=None,
            tool_name="failing_tool",
            execution_time_ms=50,
            error="Permission denied",
        )

        assert result.success is False
        assert result.result is None
        assert result.tool_name == "failing_tool"
        assert result.execution_time_ms == 50
        assert result.error == "Permission denied"


class TestToolExample:
    """Test tool example model"""

    def test_create_example(self):
        """Test example creation"""
        example = ToolExample(
            description="Calculate sum of two numbers",
            arguments={"a": 5, "b": 3},
            expected_result="8",
        )

        assert example.description == "Calculate sum of two numbers"
        assert example.arguments == {"a": 5, "b": 3}
        assert example.expected_result == "8"


class TestToolExceptions:
    """Test tool-specific exceptions"""

    def test_tool_not_found_error(self):
        """Test ToolNotFoundError"""
        error = ToolNotFoundError("Tool 'missing_tool' not found")
        assert str(error) == "Tool 'missing_tool' not found"
        assert isinstance(error, Exception)

    def test_tool_execution_error(self):
        """Test ToolExecutionError"""
        suggestions = ["Check input parameters", "Verify permissions"]
        error = ToolExecutionError(
            tool_name="broken_tool",
            error="Execution failed",
            recovery_suggestions=suggestions,
        )

        assert error.tool_name == "broken_tool"
        assert error.error == "Execution failed"
        assert error.recovery_suggestions == suggestions

    def test_tool_timeout_error(self):
        """Test ToolTimeoutError"""
        error = ToolTimeoutError("Tool execution timed out after 30s")
        assert str(error) == "Tool execution timed out after 30s"

    def test_permission_denied_error(self):
        """Test PermissionDeniedError"""
        error = PermissionDeniedError("Permission denied for tool execution")
        assert str(error) == "Permission denied for tool execution"


class TestEnums:
    """Test tool enums"""

    def test_permission_levels(self):
        """Test permission level enum"""
        assert PermissionLevel.SAFE.value == "safe"
        assert PermissionLevel.ELEVATED.value == "elevated"
        assert PermissionLevel.SYSTEM.value == "system"
        assert PermissionLevel.DANGEROUS.value == "dangerous"

    def test_tool_categories(self):
        """Test tool category enum"""
        assert ToolCategory.FILE_SYSTEM.value == "file_system"
        assert ToolCategory.INFORMATION.value == "information"
        assert ToolCategory.PRODUCTIVITY.value == "productivity"
        assert ToolCategory.COMMUNICATION.value == "communication"
        assert ToolCategory.DEVELOPMENT.value == "development"
        assert ToolCategory.SYSTEM.value == "system"
        assert ToolCategory.GENERAL.value == "general"

    def test_tool_source_types(self):
        """Test tool source type enum"""
        assert ToolSourceType.BUILT_IN.value == "built_in"
        assert ToolSourceType.MCP_SERVER.value == "mcp_server"
        assert ToolSourceType.USER_DEFINED.value == "user_defined"
