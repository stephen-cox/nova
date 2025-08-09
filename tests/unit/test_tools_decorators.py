"""Tests for the new decorator-based tool system"""

import pytest

from nova.models.tools import (
    PermissionLevel,
    ToolCategory,
)
from nova.tools.decorators import (
    get_tool_metadata,
    is_tool_function,
    tool,
)


# Test functions with decorators
@tool(
    description="Test tool for unit tests",
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.GENERAL,
    tags=["test", "demo"],
)
def simple_tool(input_text: str, multiplier: int = 1) -> str:
    """A simple test tool.

    Args:
        input_text: Text to process
        multiplier: How many times to repeat

    Returns:
        Processed text
    """
    return input_text * multiplier


@tool()
def minimal_tool(value: str) -> str:
    """Minimal tool with defaults."""
    return f"processed: {value}"


class TestToolDecorator:
    """Test the @tool decorator functionality"""

    def test_tool_decorator_creates_metadata(self):
        """Test that @tool decorator creates proper metadata"""
        assert is_tool_function(simple_tool)
        assert hasattr(simple_tool, "_tool_definition")
        assert hasattr(simple_tool, "_tool_handler")

        tool_def, handler = get_tool_metadata(simple_tool)

        assert tool_def.name == "simple_tool"
        assert tool_def.description == "Test tool for unit tests"
        assert tool_def.permission_level == PermissionLevel.SAFE
        assert tool_def.category == ToolCategory.GENERAL
        assert "test" in tool_def.tags
        assert "demo" in tool_def.tags

    def test_minimal_tool_defaults(self):
        """Test tool with minimal configuration uses defaults"""
        tool_def, handler = get_tool_metadata(minimal_tool)

        assert tool_def.name == "minimal_tool"
        assert tool_def.description == "Minimal tool with defaults."
        assert tool_def.permission_level == PermissionLevel.SAFE
        assert tool_def.category == ToolCategory.GENERAL
        assert tool_def.tags == []

    def test_schema_generation(self):
        """Test JSON schema generation from function signature"""
        tool_def, handler = get_tool_metadata(simple_tool)

        schema = tool_def.parameters
        assert schema["type"] == "object"
        assert "input_text" in schema["properties"]
        assert "multiplier" in schema["properties"]
        assert schema["properties"]["input_text"]["type"] == "string"
        assert schema["properties"]["multiplier"]["type"] == "integer"
        assert schema["properties"]["multiplier"]["default"] == 1
        assert "input_text" in schema["required"]
        assert "multiplier" not in schema["required"]  # Has default

    def test_non_tool_function_raises_error(self):
        """Test that non-tool functions raise error when getting metadata"""

        def regular_function():
            pass

        assert not is_tool_function(regular_function)

        with pytest.raises(ValueError, match="is not decorated with @tool"):
            get_tool_metadata(regular_function)


class TestDecoratedToolHandler:
    """Test the DecoratedToolHandler execution"""

    @pytest.mark.asyncio
    async def test_handler_execution(self):
        """Test that handler executes the decorated function correctly"""
        tool_def, handler = get_tool_metadata(simple_tool)

        result = await handler.execute({"input_text": "hello", "multiplier": 3}, None)
        assert result == "hellohellohello"

    @pytest.mark.asyncio
    async def test_handler_with_defaults(self):
        """Test handler uses defaults when arguments not provided"""
        tool_def, handler = get_tool_metadata(simple_tool)

        result = await handler.execute({"input_text": "test"}, None)
        assert result == "test"  # multiplier defaults to 1

    @pytest.mark.asyncio
    async def test_handler_missing_required_arg(self):
        """Test handler raises error for missing required arguments"""
        tool_def, handler = get_tool_metadata(simple_tool)

        with pytest.raises(
            RuntimeError,
            match="Tool execution failed: Missing required argument: input_text",
        ):
            await handler.execute({"multiplier": 2}, None)

    @pytest.mark.asyncio
    async def test_handler_filters_extra_args(self):
        """Test handler ignores extra arguments not in function signature"""
        tool_def, handler = get_tool_metadata(simple_tool)

        # Should work fine even with extra arguments
        result = await handler.execute(
            {"input_text": "test", "multiplier": 2, "extra_arg": "ignored"}, None
        )
        assert result == "testtest"


class TestSchemaGeneration:
    """Test schema generation from various function signatures"""

    def test_complex_types(self):
        """Test schema generation for complex types"""

        @tool()
        def complex_tool(
            text: str, count: int, active: bool, items: list, config: dict
        ) -> dict:
            pass

        tool_def, handler = get_tool_metadata(complex_tool)
        props = tool_def.parameters["properties"]

        assert props["text"]["type"] == "string"
        assert props["count"]["type"] == "integer"
        assert props["active"]["type"] == "boolean"
        assert props["items"]["type"] == "array"
        assert props["config"]["type"] == "object"

    def test_optional_parameters(self):
        """Test handling of optional parameters with defaults"""

        @tool()
        def optional_tool(
            required: str,
            optional_str: str = "default",
            optional_int: int = 42,
            optional_bool: bool = True,
        ) -> str:
            pass

        tool_def, handler = get_tool_metadata(optional_tool)
        schema = tool_def.parameters

        assert schema["required"] == ["required"]
        assert "optional_str" not in schema["required"]
        assert schema["properties"]["optional_str"]["default"] == "default"
        assert schema["properties"]["optional_int"]["default"] == 42
        assert schema["properties"]["optional_bool"]["default"] is True
