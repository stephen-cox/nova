"""Tests for built-in file operations tools"""

import tempfile
from pathlib import Path

import pytest

from nova.models.tools import ExecutionContext, PermissionLevel, ToolSourceType
from nova.tools.built_in.file_ops import (
    FileOperationsTools,
    GetFileInfoHandler,
    ListDirectoryHandler,
    ReadFileHandler,
    WriteFileHandler,
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_file(temp_dir):
    """Create sample file for testing"""
    file_path = temp_dir / "sample.txt"
    file_path.write_text("Hello, World!\nThis is a test file.")
    return file_path


@pytest.fixture
def execution_context():
    """Create execution context for testing"""
    return ExecutionContext(conversation_id="test")


class TestReadFileHandler:
    """Test read file handler"""

    def test_read_file_success(self, sample_file, execution_context):
        """Test successful file reading"""
        handler = ReadFileHandler()

        result = handler.execute_sync(
            {"file_path": str(sample_file)}, execution_context
        )

        assert result == "Hello, World!\nThis is a test file."

    def test_read_file_with_encoding(self, temp_dir, execution_context):
        """Test reading file with specific encoding"""
        # Create file with specific encoding
        file_path = temp_dir / "encoded.txt"
        content = "Café with special chars: ñáéíóú"
        file_path.write_text(content, encoding="utf-8")

        handler = ReadFileHandler()
        result = handler.execute_sync(
            {"file_path": str(file_path), "encoding": "utf-8"}, execution_context
        )

        assert result == content

    def test_read_file_not_found(self, temp_dir, execution_context):
        """Test reading non-existent file"""
        handler = ReadFileHandler()
        nonexistent = temp_dir / "nonexistent.txt"

        with pytest.raises(FileNotFoundError, match="File not found"):
            handler.execute_sync({"file_path": str(nonexistent)}, execution_context)

    def test_read_directory_as_file(self, temp_dir, execution_context):
        """Test reading directory as file"""
        handler = ReadFileHandler()

        with pytest.raises(ValueError, match="Path is not a file"):
            handler.execute_sync({"file_path": str(temp_dir)}, execution_context)

    def test_read_file_size_limit(self, temp_dir, execution_context):
        """Test file size limit"""
        # Create large file
        large_file = temp_dir / "large.txt"
        large_content = "x" * 2000  # 2KB content
        large_file.write_text(large_content)

        handler = ReadFileHandler()

        # Test with small size limit
        with pytest.raises(ValueError, match="File too large"):
            handler.execute_sync(
                {"file_path": str(large_file), "max_size": 1000}, execution_context
            )

    def test_read_binary_file(self, temp_dir, execution_context):
        """Test reading binary file"""
        binary_file = temp_dir / "binary.dat"
        # Create content that will cause UnicodeDecodeError
        binary_content = b"\x80\x81\x82\x83\x84\xff\xfe\xfd"
        binary_file.write_bytes(binary_content)

        handler = ReadFileHandler()
        result = handler.execute_sync(
            {"file_path": str(binary_file)}, execution_context
        )

        assert "Binary file" in result
        assert "not displayable as text" in result


class TestWriteFileHandler:
    """Test write file handler"""

    def test_write_file_success(self, temp_dir, execution_context):
        """Test successful file writing"""
        handler = WriteFileHandler()
        file_path = temp_dir / "output.txt"
        content = "Test content for writing"

        result = handler.execute_sync(
            {"file_path": str(file_path), "content": content}, execution_context
        )

        assert "Successfully wrote" in result
        assert file_path.read_text() == content

    def test_write_file_create_dirs(self, temp_dir, execution_context):
        """Test writing file with directory creation"""
        handler = WriteFileHandler()
        nested_path = temp_dir / "nested" / "dirs" / "file.txt"
        content = "Content in nested directory"

        result = handler.execute_sync(
            {"file_path": str(nested_path), "content": content, "create_dirs": True},
            execution_context,
        )

        assert "Successfully wrote" in result
        assert nested_path.exists()
        assert nested_path.read_text() == content

    def test_write_file_no_parent_dir(self, temp_dir, execution_context):
        """Test writing file without parent directory"""
        handler = WriteFileHandler()
        nested_path = temp_dir / "nonexistent" / "file.txt"

        with pytest.raises(FileNotFoundError, match="Parent directory does not exist"):
            handler.execute_sync(
                {"file_path": str(nested_path), "content": "test"}, execution_context
            )

    def test_write_file_custom_encoding(self, temp_dir, execution_context):
        """Test writing file with custom encoding"""
        handler = WriteFileHandler()
        file_path = temp_dir / "encoded.txt"
        content = "Content with special chars: ñáéíóú"

        handler.execute_sync(
            {"file_path": str(file_path), "content": content, "encoding": "utf-8"},
            execution_context,
        )

        # Verify content was written correctly
        assert file_path.read_text(encoding="utf-8") == content


class TestListDirectoryHandler:
    """Test list directory handler"""

    def test_list_directory_basic(self, temp_dir, execution_context):
        """Test basic directory listing"""
        # Create test files and directories
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "subdir").mkdir()

        handler = ListDirectoryHandler()
        result = handler.execute_sync(
            {"directory_path": str(temp_dir)}, execution_context
        )

        assert len(result) == 3
        names = [item["name"] for item in result]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names

        # Check types
        subdir_item = next(item for item in result if item["name"] == "subdir")
        file_item = next(item for item in result if item["name"] == "file1.txt")

        assert subdir_item["type"] == "directory"
        assert file_item["type"] == "file"

    def test_list_directory_with_hidden(self, temp_dir, execution_context):
        """Test directory listing including hidden files"""
        # Create regular and hidden files
        (temp_dir / "visible.txt").write_text("visible")
        (temp_dir / ".hidden.txt").write_text("hidden")

        handler = ListDirectoryHandler()

        # Without hidden files
        result_no_hidden = handler.execute_sync(
            {"directory_path": str(temp_dir)}, execution_context
        )
        names_no_hidden = [item["name"] for item in result_no_hidden]
        assert ".hidden.txt" not in names_no_hidden

        # With hidden files
        result_with_hidden = handler.execute_sync(
            {"directory_path": str(temp_dir), "include_hidden": True}, execution_context
        )
        names_with_hidden = [item["name"] for item in result_with_hidden]
        assert ".hidden.txt" in names_with_hidden

    def test_list_directory_with_details(self, temp_dir, execution_context):
        """Test directory listing with details"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        handler = ListDirectoryHandler()
        result = handler.execute_sync(
            {"directory_path": str(temp_dir), "show_details": True}, execution_context
        )

        file_item = next(item for item in result if item["name"] == "test.txt")
        assert "size" in file_item
        assert "modified" in file_item
        assert "permissions" in file_item
        assert file_item["size"] > 0

    def test_list_directory_not_found(self, temp_dir, execution_context):
        """Test listing non-existent directory"""
        handler = ListDirectoryHandler()
        nonexistent = temp_dir / "nonexistent"

        with pytest.raises(FileNotFoundError, match="Directory not found"):
            handler.execute_sync(
                {"directory_path": str(nonexistent)}, execution_context
            )

    def test_list_file_as_directory(self, sample_file, execution_context):
        """Test listing file as directory"""
        handler = ListDirectoryHandler()

        with pytest.raises(ValueError, match="Path is not a directory"):
            handler.execute_sync(
                {"directory_path": str(sample_file)}, execution_context
            )


class TestGetFileInfoHandler:
    """Test get file info handler"""

    def test_get_file_info_file(self, sample_file, execution_context):
        """Test getting file information"""
        handler = GetFileInfoHandler()
        result = handler.execute_sync(
            {"file_path": str(sample_file)}, execution_context
        )

        assert result["name"] == "sample.txt"
        assert result["type"] == "file"
        assert result["size"] > 0
        assert "created" in result
        assert "modified" in result
        assert "permissions" in result
        assert result["extension"] == ".txt"

    def test_get_file_info_directory(self, temp_dir, execution_context):
        """Test getting directory information"""
        handler = GetFileInfoHandler()
        result = handler.execute_sync({"file_path": str(temp_dir)}, execution_context)

        assert result["type"] == "directory"
        assert "size" in result
        assert "created" in result
        assert "modified" in result

    def test_get_file_info_not_found(self, temp_dir, execution_context):
        """Test getting info for non-existent path"""
        handler = GetFileInfoHandler()
        nonexistent = temp_dir / "nonexistent"

        with pytest.raises(FileNotFoundError, match="Path not found"):
            handler.execute_sync({"file_path": str(nonexistent)}, execution_context)


class TestFileOperationsTools:
    """Test file operations tools module"""

    @pytest.mark.asyncio
    async def test_get_tools(self):
        """Test getting all file operation tools"""
        module = FileOperationsTools()
        tools = await module.get_tools()

        assert len(tools) == 4
        tool_names = [tool_def.name for tool_def, handler in tools]

        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "list_directory" in tool_names
        assert "get_file_info" in tool_names

    @pytest.mark.asyncio
    async def test_tool_definitions(self):
        """Test tool definitions are properly configured"""
        module = FileOperationsTools()
        tools = await module.get_tools()

        for tool_def, _handler in tools:
            assert tool_def.source_type == ToolSourceType.BUILT_IN
            assert tool_def.description is not None
            assert tool_def.parameters is not None
            assert "properties" in tool_def.parameters

            # Check permission levels
            if tool_def.name == "write_file":
                assert tool_def.permission_level == PermissionLevel.ELEVATED
            else:
                assert tool_def.permission_level == PermissionLevel.SAFE
