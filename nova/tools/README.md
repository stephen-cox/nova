# Nova Tools System

The Nova tools system provides a powerful and flexible framework for creating and managing tools that can be used by the AI assistant. Tools are functions that extend Nova's capabilities, allowing it to perform specific tasks like file operations, web searches, data processing, and more.

## Quick Start

### Creating a Simple Tool

```python
from nova.tools import tool
from nova.models.tools import PermissionLevel, ToolCategory

@tool(
    description="Convert text to uppercase",
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.UTILITY,
    tags=["text", "transform"]
)
def uppercase_text(text: str) -> str:
    """Convert input text to uppercase.

    Args:
        text: The text to convert

    Returns:
        The text in uppercase
    """
    return text.upper()
```

That's it! The function is automatically:
- Registered as a tool
- Schema generated from type hints
- Available for discovery and execution

## Directory Structure

```
nova/tools/
├── __init__.py              # Main package with discovery functions
├── decorators.py            # @tool decorator implementation
├── registry.py              # Auto-discovery system
├── templates/               # Tool templates
│   ├── basic_tool.py        # Basic tool examples
│   └── file_tool.py         # File operation examples
├── built_in/               # Built-in tools (shipped with Nova)
│   ├── file_ops.py         # File system operations
│   ├── web_search.py       # Web search tools
│   └── conversation.py     # Chat/conversation tools
├── user/                   # User-defined tools
│   └── __init__.py         # (Your custom tools go here)
└── mcp/                    # MCP protocol tools
    └── __init__.py         # (MCP integrations)
```

## Tool Categories

Tools are organized into categories for better discovery and organization:

- **`GENERAL`** - General-purpose tools
- **`FILE_SYSTEM`** - File and directory operations
- **`WEB`** - Web-related functionality (search, scraping, APIs)
- **`UTILITY`** - Utility functions (text processing, calculations)
- **`DEVELOPMENT`** - Development and coding tools
- **`SYSTEM`** - System-level operations
- **`NETWORK`** - Network operations
- **`DATA`** - Data processing and analysis

## Permission Levels

Tools require appropriate permissions based on their potential impact:

- **`SAFE`** - Read-only operations, no side effects (default)
- **`ELEVATED`** - Can modify files, make network requests
- **`SYSTEM`** - System-level access, dangerous operations
- **`DANGEROUS`** - Potentially harmful, requires explicit approval

## Creating Tools

### 1. Using the @tool Decorator

The simplest way to create tools:

```python
from nova.tools import tool
from nova.models.tools import PermissionLevel, ToolCategory, ToolExample

@tool(
    name="add_numbers",  # Optional, defaults to function name
    description="Add two numbers together",  # Optional, uses docstring
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.UTILITY,
    tags=["math", "calculation"],
    examples=[
        ToolExample(
            description="Add 5 and 3",
            arguments={"a": 5, "b": 3},
            expected_result="8"
        )
    ]
)
def add_numbers(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b
```

### 2. Type Hints and Schema Generation

The decorator automatically generates JSON schema from your function signature:

```python
@tool(description="Process user data")
def process_data(
    name: str,                    # Required string
    age: int = 25,               # Optional integer with default
    active: bool = True,         # Optional boolean with default
    tags: list[str] = None,      # Optional list of strings
    metadata: dict = None        # Optional dictionary
) -> dict:
    """Function signature becomes the tool schema automatically"""
    pass
```

### 3. Parameter Documentation

Parameter descriptions are extracted from docstrings:

```python
@tool(description="File processor")
def process_file(file_path: str, encoding: str = "utf-8") -> str:
    """Process a file.

    Args:
        file_path: Path to the file to process
        encoding: File encoding (default: utf-8)

    Returns:
        Processing result summary
    """
    pass
```

## Tool Discovery

Tools are automatically discovered and registered:

```python
from nova.tools import discover_all_tools, get_global_registry

# Discover all tools
tools = discover_all_tools()

# Get specific tool
registry = get_global_registry()
tool_def, handler = registry.get_tool("add_numbers")

# Search tools
math_tools = registry.search_tools("math")
file_tools = registry.filter_tools_by_category("file_system")
```

## Best Practices

### Security Guidelines

1. **Use appropriate permission levels**:
   - `SAFE` for read-only operations
   - `ELEVATED` for file modifications, network requests
   - `SYSTEM` for system operations
   - `DANGEROUS` for potentially harmful operations

2. **Validate inputs**:
   ```python
   @tool(permission_level=PermissionLevel.ELEVATED)
   def write_file(file_path: str, content: str) -> str:
       path = Path(file_path).expanduser().resolve()

       # Security checks
       if str(path).startswith("/etc/"):
           raise ValueError("Cannot write to system directories")

       # Proceed with operation
   ```

3. **Handle errors gracefully**:
   ```python
   @tool()
   def safe_operation(input_data: str) -> str:
       try:
           # Tool operation
           return process_data(input_data)
       except Exception as e:
           return f"Error: {e}"
   ```

### Performance Guidelines

1. **Avoid blocking operations** in tool functions
2. **Limit resource usage** (file sizes, memory, network requests)
3. **Provide progress feedback** for long-running operations
4. **Use caching** for expensive computations

### Documentation Guidelines

1. **Write clear docstrings** with parameter descriptions
2. **Provide usage examples** in the `examples` parameter
3. **Use descriptive function names** and parameter names
4. **Add relevant tags** for discoverability

## Built-in Tools

Nova comes with several built-in tools:

### File Operations (`nova.tools.built_in.file_ops`)
- `read_file` - Read file contents
- `write_file` - Write content to files
- `list_directory` - List directory contents
- `get_file_info` - Get file metadata

### Web Search (`nova.tools.built_in.web_search`)
- `search_web` - Search the web for information
- `fetch_webpage` - Retrieve webpage content

### Conversation (`nova.tools.built_in.conversation`)
- `save_conversation` - Save chat history
- `load_conversation` - Load previous conversations
- `search_conversations` - Search chat history

## Adding Custom Tools

### For Built-in Tools

1. Create your tool in `nova/tools/built_in/your_module.py`
2. Use the `@tool` decorator
3. Tools are automatically discovered

### For User Tools

1. Create tools in `nova/tools/user/your_module.py`
2. Use the `@tool` decorator
3. Tools are automatically discovered

### For MCP Tools

MCP (Model Context Protocol) tools will be supported in a future version.

## Testing Tools

Create tests for your tools:

```python
import pytest
from nova.tools.decorators import get_tool_metadata
from nova.models.tools import ExecutionContext

def test_my_tool():
    # Test the decorated function directly
    result = my_tool("test input")
    assert result == "expected output"

    # Test via tool system
    tool_def, handler = get_tool_metadata(my_tool)
    context = ExecutionContext(conversation_id="test")
    result = await handler.execute({"input": "test input"}, context)
    assert result == "expected output"
```

## Configuration

Tools can be enabled/disabled via configuration:

```yaml
# nova-config.yaml
tools:
  enabled: true
  enabled_built_in_modules:
    - "file_ops"
    - "web_search"
    - "conversation"
  permission_mode: "prompt"  # "auto", "prompt", "deny"
  execution_timeout: 30
```

## Migration from Legacy Tools

If you have existing tools using the old `BuiltInToolModule` system:

1. Convert handler classes to simple functions
2. Add `@tool` decorator
3. Remove manual registration code
4. Tools will be auto-discovered

See templates in `nova/tools/templates/` for examples.
