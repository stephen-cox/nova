"""Tool decorator system for easy tool creation and registration"""

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from nova.core.tools.handler import SyncToolHandler, ToolHandler
from nova.models.tools import (
    PermissionLevel,
    ToolCategory,
    ToolDefinition,
    ToolExample,
    ToolSourceType,
)


class DecoratedToolHandler(SyncToolHandler):
    """Handler for decorator-defined tools"""

    def __init__(self, func: Callable, metadata: dict):
        self.func = func
        self.metadata = metadata

    def execute_sync(self, arguments: dict[str, Any], context=None) -> Any:
        """Execute the decorated function with arguments"""
        try:
            # Filter arguments to match function signature
            sig = inspect.signature(self.func)
            filtered_args = {}

            for param_name, param in sig.parameters.items():
                if param_name in arguments:
                    filtered_args[param_name] = arguments[param_name]
                elif param.default is not param.empty:
                    # Use default value if not provided
                    pass
                else:
                    raise ValueError(f"Missing required argument: {param_name}")

            return self.func(**filtered_args)
        except Exception as e:
            raise RuntimeError(f"Tool execution failed: {e}") from e


def _generate_json_schema(func: Callable) -> dict:
    """Generate JSON schema from function signature and type hints"""
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        param_type = type_hints.get(param_name, Any)

        # Convert Python types to JSON schema types
        json_type = _python_type_to_json_type(param_type)

        param_schema = {"type": json_type}

        # Add description from docstring if available
        if func.__doc__:
            # Try to extract parameter descriptions from docstring
            param_desc = _extract_param_description(func.__doc__, param_name)
            if param_desc:
                param_schema["description"] = param_desc

        # Handle default values
        if param.default is not param.empty:
            param_schema["default"] = param.default
        else:
            required.append(param_name)

        properties[param_name] = param_schema

    return {"type": "object", "properties": properties, "required": required}


def _python_type_to_json_type(python_type) -> str:
    """Convert Python type to JSON schema type"""
    type_mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    # Handle Union types (e.g., Optional[str])
    if hasattr(python_type, "__origin__"):
        if python_type.__origin__ is list:
            return "array"
        elif python_type.__origin__ is dict:
            return "object"
        elif python_type.__origin__ is type(None):
            return "null"

    return type_mapping.get(python_type, "string")


def _extract_param_description(docstring: str, param_name: str) -> str | None:
    """Extract parameter description from docstring"""
    lines = docstring.split("\n")
    in_args_section = False

    for line in lines:
        line = line.strip()

        if line.lower().startswith("args:") or line.lower().startswith("parameters:"):
            in_args_section = True
            continue

        if in_args_section:
            if line.lower().startswith("returns:") or line.lower().startswith(
                "yields:"
            ):
                break

            if line.startswith(f"{param_name}:"):
                return line[len(param_name) + 1 :].strip()
            elif line.startswith(f"{param_name} "):
                # Handle format like "param_name (type): description"
                colon_pos = line.find(":")
                if colon_pos != -1:
                    return line[colon_pos + 1 :].strip()

    return None


def tool(
    name: str = None,
    description: str = None,
    permission_level: PermissionLevel = PermissionLevel.SAFE,
    category: ToolCategory = ToolCategory.GENERAL,
    tags: list[str] | None = None,
    examples: list[ToolExample] | None = None,
) -> Callable:
    """
    Decorator to register a function as a tool.

    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to function docstring)
        permission_level: Required permission level for the tool
        category: Tool category for organization
        tags: List of tags for searching/filtering
        examples: List of usage examples

    Returns:
        The decorated function, unchanged but registered as a tool

    Example:
        @tool(
            description="Add two numbers",
            permission_level=PermissionLevel.SAFE,
            category=ToolCategory.UTILITY,
            tags=["math", "calculation"]
        )
        def add_numbers(a: int, b: int) -> int:
            '''Add two numbers together.

            Args:
                a: First number
                b: Second number

            Returns:
                Sum of a and b
            '''
            return a + b
    """

    def decorator(func: Callable) -> Callable:
        # Get metadata from function and decorator args
        tool_name = name or func.__name__
        tool_description = description or (
            func.__doc__.split("\n")[0] if func.__doc__ else f"Execute {func.__name__}"
        )
        tool_tags = tags or []
        tool_examples = examples or []

        # Generate JSON schema from function signature
        parameters = _generate_json_schema(func)

        # Create tool definition
        tool_def = ToolDefinition(
            name=tool_name,
            description=tool_description,
            parameters=parameters,
            source_type=ToolSourceType.BUILT_IN,
            permission_level=permission_level,
            category=category,
            tags=tool_tags,
            examples=tool_examples,
        )

        # Create handler
        handler = DecoratedToolHandler(
            func,
            {
                "name": tool_name,
                "description": tool_description,
                "permission_level": permission_level,
                "category": category,
                "tags": tool_tags,
            },
        )

        # Store metadata on function for auto-discovery
        func._tool_definition = tool_def
        func._tool_handler = handler
        func._is_tool = True

        return func

    return decorator


def get_tool_metadata(func: Callable) -> tuple[ToolDefinition, ToolHandler]:
    """Get tool definition and handler from a decorated function"""
    if not hasattr(func, "_is_tool") or not func._is_tool:
        raise ValueError(f"Function {func.__name__} is not decorated with @tool")

    return func._tool_definition, func._tool_handler


def is_tool_function(func: Callable) -> bool:
    """Check if a function is decorated with @tool"""
    return hasattr(func, "_is_tool") and func._is_tool
