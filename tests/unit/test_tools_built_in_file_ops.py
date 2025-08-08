"""Tests for built-in file operations tools"""

import tempfile
from pathlib import Path

import pytest

from nova.tools.built_in.file_ops import (
    get_file_info,
    list_directory,
    read_file,
    write_file,
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


class TestReadFile:
    """Test read_file function"""

    def test_read_existing_file(self, sample_file):
        """Test reading an existing file"""
        content = read_file(str(sample_file))
        assert content == "Hello, World!\nThis is a test file."

    def test_read_nonexistent_file(self):
        """Test reading a non-existent file"""
        with pytest.raises(FileNotFoundError):
            read_file("nonexistent.txt")

    def test_read_with_encoding(self, temp_dir):
        """Test reading with different encoding"""
        file_path = temp_dir / "encoded.txt"
        content = "Hello, ñoño!"
        file_path.write_text(content, encoding="utf-8")

        result = read_file(str(file_path), encoding="utf-8")
        assert result == content

    def test_read_file_too_large(self, temp_dir):
        """Test reading file that exceeds max size"""
        file_path = temp_dir / "large.txt"
        file_path.write_text("x" * 100)

        with pytest.raises(ValueError, match="File too large"):
            read_file(str(file_path), max_size=50)


class TestWriteFile:
    """Test write_file function"""

    def test_write_new_file(self, temp_dir):
        """Test writing to a new file"""
        file_path = temp_dir / "new.txt"
        content = "New content"

        result = write_file(str(file_path), content)
        assert "Successfully wrote" in result
        assert file_path.read_text() == content

    def test_write_with_create_dirs(self, temp_dir):
        """Test writing with directory creation"""
        file_path = temp_dir / "subdir" / "new.txt"
        content = "New content"

        result = write_file(str(file_path), content, create_dirs=True)
        assert "Successfully wrote" in result
        assert file_path.read_text() == content

    def test_write_without_create_dirs_fails(self, temp_dir):
        """Test writing without directory creation fails"""
        file_path = temp_dir / "nonexistent_subdir" / "new.txt"
        content = "New content"

        with pytest.raises(FileNotFoundError):
            write_file(str(file_path), content, create_dirs=False)


class TestListDirectory:
    """Test list_directory function"""

    def test_list_directory(self, temp_dir, sample_file):
        """Test listing directory contents"""
        # Create additional test files
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "subdir").mkdir()

        items = list_directory(str(temp_dir))

        # Should have 4 items (sample.txt, file1.txt, file2.txt, subdir)
        assert len(items) == 4

        # Check that directories come first
        assert items[0]["type"] == "directory"
        assert items[0]["name"] == "subdir"

    def test_list_directory_with_hidden(self, temp_dir):
        """Test listing directory with hidden files"""
        (temp_dir / "visible.txt").write_text("visible")
        (temp_dir / ".hidden.txt").write_text("hidden")

        # Without hidden files
        items = list_directory(str(temp_dir), include_hidden=False)
        assert len(items) == 1
        assert items[0]["name"] == "visible.txt"

        # With hidden files
        items = list_directory(str(temp_dir), include_hidden=True)
        assert len(items) == 2

    def test_list_directory_with_details(self, temp_dir, sample_file):
        """Test listing directory with detailed information"""
        items = list_directory(str(temp_dir), show_details=True)

        assert len(items) == 1
        item = items[0]
        assert "size" in item
        assert "modified" in item
        assert "permissions" in item

    def test_list_nonexistent_directory(self):
        """Test listing non-existent directory"""
        with pytest.raises(FileNotFoundError):
            list_directory("nonexistent")


class TestGetFileInfo:
    """Test get_file_info function"""

    def test_get_file_info(self, sample_file):
        """Test getting file information"""
        info = get_file_info(str(sample_file))

        assert info["name"] == "sample.txt"
        assert info["type"] == "file"
        assert "size" in info
        assert "created" in info
        assert "modified" in info
        assert "permissions" in info
        assert info["extension"] == ".txt"

    def test_get_directory_info(self, temp_dir):
        """Test getting directory information"""
        info = get_file_info(str(temp_dir))

        assert info["type"] == "directory"
        assert "size" in info
        assert "extension" not in info  # Directories don't have extensions

    def test_get_info_nonexistent(self):
        """Test getting info for non-existent file"""
        with pytest.raises(FileNotFoundError):
            get_file_info("nonexistent")
