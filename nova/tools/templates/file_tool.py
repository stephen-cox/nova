"""Template for creating file operation tools

This template shows how to create tools that work with files safely.
"""

from pathlib import Path

from nova.models.tools import PermissionLevel, ToolCategory, ToolExample
from nova.tools import tool


@tool(
    description="Template for reading and processing files",
    permission_level=PermissionLevel.SAFE,  # Reading is generally safe
    category=ToolCategory.FILE_SYSTEM,
    tags=["template", "file", "read"],
    examples=[
        ToolExample(
            description="Read a text file and count lines",
            arguments={"file_path": "README.md"},
            expected_result="File has 42 lines",
        )
    ],
)
def read_file_template(file_path: str, encoding: str = "utf-8") -> str:
    """
    Template for safe file reading operations.

    Args:
        file_path: Path to the file to read
        encoding: File encoding (default: utf-8)

    Returns:
        Information about the file contents
    """
    try:
        path = Path(file_path).expanduser().resolve()

        # Security checks
        if not path.exists():
            return f"File not found: {path}"

        if not path.is_file():
            return f"Path is not a file: {path}"

        # Size check (limit to 1MB)
        if path.stat().st_size > 1024 * 1024:
            return f"File too large: {path.stat().st_size} bytes"

        # Read and analyze
        with open(path, encoding=encoding) as f:
            content = f.read()

        lines = len(content.splitlines())
        chars = len(content)
        words = len(content.split())

        return f"File analysis: {lines} lines, {words} words, {chars} characters"

    except Exception as e:
        return f"Error reading file: {e}"


@tool(
    description="Template for writing files safely",
    permission_level=PermissionLevel.ELEVATED,  # Writing requires elevation
    category=ToolCategory.FILE_SYSTEM,
    tags=["template", "file", "write"],
    examples=[
        ToolExample(
            description="Write text to a file",
            arguments={"file_path": "output.txt", "content": "Hello World"},
            expected_result="File written successfully: output.txt",
        )
    ],
)
def write_file_template(
    file_path: str, content: str, encoding: str = "utf-8", create_dirs: bool = False
) -> str:
    """
    Template for safe file writing operations.

    Args:
        file_path: Path where to write the file
        content: Content to write
        encoding: File encoding (default: utf-8)
        create_dirs: Create parent directories if they don't exist

    Returns:
        Success message or error description
    """
    try:
        path = Path(file_path).expanduser().resolve()

        # Security checks - prevent writing to system directories
        system_paths = ["/bin", "/usr", "/etc", "/sys", "/proc"]
        if any(str(path).startswith(sys_path) for sys_path in system_paths):
            return f"Cannot write to system directory: {path}"

        # Create parent directories if requested
        if create_dirs and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        # Check if parent directory exists
        if not path.parent.exists():
            return f"Parent directory does not exist: {path.parent}"

        # Write file
        with open(path, "w", encoding=encoding) as f:
            f.write(content)

        return f"File written successfully: {path} ({len(content)} characters)"

    except Exception as e:
        return f"Error writing file: {e}"


@tool(
    description="Template for listing directory contents",
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.FILE_SYSTEM,
    tags=["template", "directory", "list"],
    examples=[
        ToolExample(
            description="List files in current directory",
            arguments={"directory_path": "."},
            expected_result="Found 5 files and 2 directories",
        )
    ],
)
def list_directory_template(
    directory_path: str,
    include_hidden: bool = False,
    file_types_only: list[str] | None = None,
) -> str:
    """
    Template for listing directory contents safely.

    Args:
        directory_path: Path to directory to list
        include_hidden: Include hidden files/directories
        file_types_only: List of file extensions to include (e.g., ['.txt', '.py'])

    Returns:
        Summary of directory contents
    """
    try:
        path = Path(directory_path).expanduser().resolve()

        if not path.exists():
            return f"Directory not found: {path}"

        if not path.is_dir():
            return f"Path is not a directory: {path}"

        # List contents
        files = []
        directories = []

        for item in path.iterdir():
            # Skip hidden files if not requested
            if not include_hidden and item.name.startswith("."):
                continue

            if item.is_file():
                # Filter by file types if specified
                if file_types_only and item.suffix not in file_types_only:
                    continue
                files.append(item.name)
            elif item.is_dir():
                directories.append(item.name)

        result_parts = [
            f"Directory: {path}",
            f"Files: {len(files)}",
            f"Directories: {len(directories)}",
        ]

        if files:
            result_parts.append(f"Sample files: {', '.join(files[:5])}")
        if directories:
            result_parts.append(f"Sample directories: {', '.join(directories[:3])}")

        return " | ".join(result_parts)

    except Exception as e:
        return f"Error listing directory: {e}"
