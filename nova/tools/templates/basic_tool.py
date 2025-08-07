"""Template for creating a basic tool

Copy this file and modify it to create your own tools.
"""

from typing import Any

from nova.models.tools import PermissionLevel, ToolCategory, ToolExample
from nova.tools import tool


@tool(
    description="Template tool that demonstrates the basic structure",
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.GENERAL,
    tags=["template", "example", "demo"],
    examples=[
        ToolExample(
            description="Basic usage example",
            arguments={"input_text": "Hello World", "multiplier": 3},
            expected_result="Hello World (repeated 3 times)",
        )
    ],
)
def template_tool(input_text: str, multiplier: int = 1, uppercase: bool = False) -> str:
    """
    Template tool that processes text input.

    This is a demonstration of how to create a tool using the @tool decorator.
    The function signature defines the tool's parameters automatically.

    Args:
        input_text: The text to process
        multiplier: How many times to repeat the text (default: 1)
        uppercase: Whether to convert to uppercase (default: False)

    Returns:
        The processed text result
    """
    # Tool implementation
    result = input_text

    if uppercase:
        result = result.upper()

    if multiplier > 1:
        result = " | ".join([result] * multiplier)

    return f"Processed: {result}"


@tool(
    name="advanced_template",
    description="Advanced template showing more complex parameter types",
    permission_level=PermissionLevel.ELEVATED,
    category=ToolCategory.DEVELOPMENT,
    tags=["template", "advanced", "demo"],
)
def advanced_template_tool(
    items: list[str], config: dict[str, Any] = None, dry_run: bool = True
) -> dict[str, Any]:
    """
    Advanced template showing complex parameter types.

    Args:
        items: List of items to process
        config: Configuration dictionary (optional)
        dry_run: If True, don't make actual changes (default: True)

    Returns:
        Dictionary with processing results
    """
    if config is None:
        config = {}

    results = {
        "processed_items": len(items),
        "config_used": config,
        "dry_run": dry_run,
        "items": items if not dry_run else items[:3],  # Limit in dry run
    }

    return results
