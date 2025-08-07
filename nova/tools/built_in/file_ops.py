"""File system operations tools"""

from pathlib import Path
from typing import Any

from nova.core.tools.handler import BuiltInToolModule, SyncToolHandler
from nova.models.tools import (
    ExecutionContext,
    PermissionLevel,
    ToolCategory,
    ToolDefinition,
    ToolExample,
    ToolSourceType,
)


class ReadFileHandler(SyncToolHandler):
    """Handler for reading file contents"""

    def execute_sync(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> str:
        file_path = arguments["file_path"]
        encoding = arguments.get("encoding", "utf-8")
        max_size = arguments.get("max_size", 1024 * 1024)  # 1MB limit

        path = Path(file_path).expanduser().resolve()

        # Security check
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        # Size check
        if path.stat().st_size > max_size:
            raise ValueError(
                f"File too large (max {max_size} bytes): {path.stat().st_size} bytes"
            )

        try:
            with open(path, encoding=encoding) as f:
                content = f.read()
            return content
        except UnicodeDecodeError:
            # Try binary mode for non-text files
            with open(path, "rb") as f:
                content = f.read()
            return (
                f"Binary file ({len(content)} bytes) - content not displayable as text"
            )
        except Exception as e:
            raise OSError(f"Failed to read file: {e}")


class WriteFileHandler(SyncToolHandler):
    """Handler for writing file contents"""

    def execute_sync(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> str:
        file_path = arguments["file_path"]
        content = arguments["content"]
        encoding = arguments.get("encoding", "utf-8")
        create_dirs = arguments.get("create_dirs", False)

        path = Path(file_path).expanduser().resolve()

        # Create parent directories if requested
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        elif not path.parent.exists():
            raise FileNotFoundError(f"Parent directory does not exist: {path.parent}")

        try:
            with open(path, "w", encoding=encoding) as f:
                f.write(content)

            return f"Successfully wrote {len(content)} characters to {path}"
        except Exception as e:
            raise OSError(f"Failed to write file: {e}")


class ListDirectoryHandler(SyncToolHandler):
    """Handler for listing directory contents"""

    def execute_sync(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> list[dict]:
        directory_path = arguments["directory_path"]
        include_hidden = arguments.get("include_hidden", False)
        show_details = arguments.get("show_details", False)

        path = Path(directory_path).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")

        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

        try:
            items = []
            for item in path.iterdir():
                # Skip hidden files unless requested
                if not include_hidden and item.name.startswith("."):
                    continue

                item_info = {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "path": str(item),
                }

                if show_details:
                    try:
                        stat = item.stat()
                        item_info.update(
                            {
                                "size": stat.st_size if item.is_file() else None,
                                "modified": stat.st_mtime,
                                "permissions": oct(stat.st_mode)[-3:],
                            }
                        )
                    except (OSError, PermissionError):
                        # Add placeholder if we can't get details
                        item_info.update(
                            {"size": None, "modified": None, "permissions": None}
                        )

                items.append(item_info)

            # Sort by name, directories first
            items.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))

            return items

        except PermissionError:
            raise PermissionError(f"Permission denied accessing directory: {path}")
        except Exception as e:
            raise OSError(f"Failed to list directory: {e}")


class GetFileInfoHandler(SyncToolHandler):
    """Handler for getting file information"""

    def execute_sync(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> dict:
        file_path = arguments["file_path"]

        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        try:
            stat = path.stat()

            info = {
                "name": path.name,
                "path": str(path),
                "type": "directory" if path.is_dir() else "file",
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "permissions": oct(stat.st_mode)[-3:],
                "owner": stat.st_uid,
                "group": stat.st_gid,
            }

            if path.is_file():
                # Add file-specific info
                info["extension"] = path.suffix
                try:
                    # Try to determine if it's a text file
                    with open(path, "rb") as f:
                        sample = f.read(1024)
                    info["is_text"] = not bool(
                        sample.translate(None, delete=bytes(range(32, 127)))
                    )
                except Exception:
                    info["is_text"] = None

            return info

        except PermissionError:
            raise PermissionError(f"Permission denied accessing: {path}")
        except Exception as e:
            raise OSError(f"Failed to get file info: {e}")


class FileOperationsTools(BuiltInToolModule):
    """File system operations"""

    async def get_tools(self) -> list[tuple[ToolDefinition, Any]]:
        return [
            (
                ToolDefinition(
                    name="read_file",
                    description="Read the contents of a text file",
                    parameters={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file to read",
                            },
                            "encoding": {
                                "type": "string",
                                "default": "utf-8",
                                "description": "File encoding (default: utf-8)",
                            },
                            "max_size": {
                                "type": "integer",
                                "default": 1048576,
                                "description": "Maximum file size to read in bytes (default: 1MB)",
                            },
                        },
                        "required": ["file_path"],
                    },
                    source_type=ToolSourceType.BUILT_IN,
                    permission_level=PermissionLevel.SAFE,
                    category=ToolCategory.FILE_SYSTEM,
                    tags=["file", "read", "io"],
                    examples=[
                        ToolExample(
                            description="Read a text file",
                            arguments={"file_path": "README.md"},
                            expected_result="File contents as string",
                        ),
                        ToolExample(
                            description="Read with specific encoding",
                            arguments={
                                "file_path": "document.txt",
                                "encoding": "latin1",
                            },
                            expected_result="File contents with latin1 encoding",
                        ),
                    ],
                ),
                ReadFileHandler(),
            ),
            (
                ToolDefinition(
                    name="write_file",
                    description="Write content to a file",
                    parameters={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path where to write the file",
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to write to the file",
                            },
                            "encoding": {
                                "type": "string",
                                "default": "utf-8",
                                "description": "File encoding (default: utf-8)",
                            },
                            "create_dirs": {
                                "type": "boolean",
                                "default": False,
                                "description": "Create parent directories if they don't exist",
                            },
                        },
                        "required": ["file_path", "content"],
                    },
                    source_type=ToolSourceType.BUILT_IN,
                    permission_level=PermissionLevel.ELEVATED,
                    category=ToolCategory.FILE_SYSTEM,
                    tags=["file", "write", "io"],
                    examples=[
                        ToolExample(
                            description="Write text to a file",
                            arguments={
                                "file_path": "output.txt",
                                "content": "Hello, world!",
                            },
                            expected_result="File written successfully",
                        )
                    ],
                ),
                WriteFileHandler(),
            ),
            (
                ToolDefinition(
                    name="list_directory",
                    description="List the contents of a directory",
                    parameters={
                        "type": "object",
                        "properties": {
                            "directory_path": {
                                "type": "string",
                                "description": "Path to the directory to list",
                            },
                            "include_hidden": {
                                "type": "boolean",
                                "default": False,
                                "description": "Include hidden files and directories",
                            },
                            "show_details": {
                                "type": "boolean",
                                "default": False,
                                "description": "Include detailed information (size, permissions, etc.)",
                            },
                        },
                        "required": ["directory_path"],
                    },
                    source_type=ToolSourceType.BUILT_IN,
                    permission_level=PermissionLevel.SAFE,
                    category=ToolCategory.FILE_SYSTEM,
                    tags=["directory", "list", "files"],
                    examples=[
                        ToolExample(
                            description="List files in current directory",
                            arguments={"directory_path": "."},
                            expected_result="List of files and directories",
                        ),
                        ToolExample(
                            description="List with hidden files and details",
                            arguments={
                                "directory_path": ".",
                                "include_hidden": True,
                                "show_details": True,
                            },
                            expected_result="Detailed list including hidden files",
                        ),
                    ],
                ),
                ListDirectoryHandler(),
            ),
            (
                ToolDefinition(
                    name="get_file_info",
                    description="Get detailed information about a file or directory",
                    parameters={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file or directory",
                            }
                        },
                        "required": ["file_path"],
                    },
                    source_type=ToolSourceType.BUILT_IN,
                    permission_level=PermissionLevel.SAFE,
                    category=ToolCategory.FILE_SYSTEM,
                    tags=["file", "info", "metadata"],
                    examples=[
                        ToolExample(
                            description="Get file information",
                            arguments={"file_path": "README.md"},
                            expected_result="File metadata including size, timestamps, permissions",
                        )
                    ],
                ),
                GetFileInfoHandler(),
            ),
        ]
