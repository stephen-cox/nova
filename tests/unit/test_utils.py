"""Unit tests for utility functions"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from nova.utils.files import (
    ensure_dir,
    get_user_config_dir,
    get_user_data_dir,
    safe_filename,
)
from nova.utils.formatting import (
    format_file_size,
    print_error,
    print_info,
    print_message,
    print_success,
    print_warning,
)


class TestFileUtils:
    """Test file utility functions"""

    def test_ensure_dir_creates_directory(self):
        """Test that ensure_dir creates directories"""
        with TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "test" / "nested" / "dir"
            assert not test_path.exists()

            result = ensure_dir(test_path)

            assert test_path.exists()
            assert test_path.is_dir()
            assert result == test_path

    def test_ensure_dir_existing_directory(self):
        """Test that ensure_dir works with existing directories"""
        with TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir)
            assert test_path.exists()

            result = ensure_dir(test_path)

            assert test_path.exists()
            assert result == test_path

    def test_ensure_dir_expands_user_path(self):
        """Test that ensure_dir expands ~ in paths"""
        with patch("pathlib.Path.expanduser") as mock_expand:
            mock_path = MagicMock()
            mock_expand.return_value = mock_path

            ensure_dir("~/test")

            mock_expand.assert_called_once()
            mock_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_safe_filename_basic(self):
        """Test basic filename sanitization"""
        result = safe_filename("hello world")
        assert result == "hello_world"

    def test_safe_filename_special_characters(self):
        """Test filename sanitization with special characters"""
        result = safe_filename('file/with\\bad:chars<>|"*?')
        # The function strips trailing underscores, so result will be clean
        assert result == "file_with_bad_chars"

    def test_safe_filename_multiple_spaces(self):
        """Test filename sanitization with multiple spaces"""
        result = safe_filename("file   with    spaces")
        assert result == "file_with_spaces"

    def test_safe_filename_leading_trailing_underscores(self):
        """Test filename sanitization removes leading/trailing underscores"""
        result = safe_filename("___file___")
        assert result == "file"

    def test_safe_filename_truncation(self):
        """Test filename truncation"""
        long_name = "a" * 100
        result = safe_filename(long_name, max_length=10)
        assert len(result) == 10
        assert result == "a" * 10

    def test_safe_filename_empty_fallback(self):
        """Test filename fallback for empty/invalid input"""
        result = safe_filename("!!!@@@###")
        assert result == "untitled"

        result = safe_filename("")
        assert result == "untitled"

    @pytest.mark.skip(
        reason="Cross-platform path testing complex - Windows paths on Linux"
    )
    def test_get_user_data_dir_windows(self):
        """Test user data directory on Windows"""
        pass

    @patch.dict(os.environ, {"XDG_DATA_HOME": "/home/user/.local/share"})
    @patch("os.name", "posix")
    def test_get_user_data_dir_linux_with_xdg(self):
        """Test user data directory on Linux with XDG_DATA_HOME"""
        with patch("nova.utils.files.ensure_dir") as mock_ensure:
            mock_ensure.return_value = Path("/home/user/.local/share/nova")

            result = get_user_data_dir()

            mock_ensure.assert_called_once_with(Path("/home/user/.local/share/nova"))
            assert result == Path("/home/user/.local/share/nova")

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.name", "posix")
    def test_get_user_data_dir_linux_default(self):
        """Test user data directory on Linux with default path"""
        with patch("nova.utils.files.ensure_dir") as mock_ensure:
            mock_ensure.return_value = Path("~/.local/share/nova").expanduser()

            get_user_data_dir()

            # Should use default ~/.local/share when XDG_DATA_HOME not set
            expected_path = Path("~/.local/share") / "nova"
            mock_ensure.assert_called_once_with(expected_path)

    @pytest.mark.skip(
        reason="Cross-platform path testing complex - Windows paths on Linux"
    )
    def test_get_user_config_dir_windows(self):
        """Test user config directory on Windows"""
        pass

    @patch.dict(os.environ, {"XDG_CONFIG_HOME": "/home/user/.config"})
    @patch("os.name", "posix")
    def test_get_user_config_dir_linux_with_xdg(self):
        """Test user config directory on Linux with XDG_CONFIG_HOME"""
        with patch("nova.utils.files.ensure_dir") as mock_ensure:
            mock_ensure.return_value = Path("/home/user/.config/nova")

            result = get_user_config_dir()

            mock_ensure.assert_called_once_with(Path("/home/user/.config/nova"))
            assert result == Path("/home/user/.config/nova")


class TestFormattingUtils:
    """Test formatting utility functions"""

    @patch("nova.utils.formatting.console")
    def test_print_message_user(self, mock_console):
        """Test printing user message"""
        print_message("user", "Hello world", "12:34:56")

        mock_console.print.assert_called_once()
        # Verify the panel was created with correct styling
        panel_arg = mock_console.print.call_args[0][0]
        assert "👤 User (12:34:56)" in str(panel_arg.title)
        assert panel_arg.border_style == "blue"

    @patch("nova.utils.formatting.console")
    def test_print_message_assistant(self, mock_console):
        """Test printing assistant message"""
        print_message("assistant", "Hello back!", "12:34:57")

        mock_console.print.assert_called_once()
        panel_arg = mock_console.print.call_args[0][0]
        assert "🤖 Nova (12:34:57)" in str(panel_arg.title)
        assert panel_arg.border_style == "green"

    @patch("nova.utils.formatting.console")
    def test_print_message_system(self, mock_console):
        """Test printing system message"""
        print_message("system", "System message", "12:34:58")

        mock_console.print.assert_called_once()
        panel_arg = mock_console.print.call_args[0][0]
        assert "ℹ️ System (12:34:58)" in str(panel_arg.title)
        assert panel_arg.border_style == "yellow"

    @patch("nova.utils.formatting.console")
    def test_print_message_no_timestamp(self, mock_console):
        """Test printing message without timestamp"""
        print_message("user", "Hello world")

        mock_console.print.assert_called_once()
        panel_arg = mock_console.print.call_args[0][0]
        assert "👤 User" in str(panel_arg.title)
        assert "(" not in str(panel_arg.title)  # No timestamp

    @patch("nova.utils.formatting.console")
    def test_print_error(self, mock_console):
        """Test printing error message"""
        print_error("Something went wrong")

        mock_console.print.assert_called_once_with(
            "[red bold]Error:[/red bold] Something went wrong"
        )

    @patch("nova.utils.formatting.console")
    def test_print_success(self, mock_console):
        """Test printing success message"""
        print_success("Operation completed")

        mock_console.print.assert_called_once_with(
            "[green]✓[/green] Operation completed"
        )

    @patch("nova.utils.formatting.console")
    def test_print_warning(self, mock_console):
        """Test printing warning message"""
        print_warning("This is a warning")

        mock_console.print.assert_called_once_with(
            "[yellow]⚠[/yellow] This is a warning"
        )

    @patch("nova.utils.formatting.console")
    def test_print_info(self, mock_console):
        """Test printing info message"""
        print_info("This is information")

        mock_console.print.assert_called_once_with("[blue]ℹ[/blue] This is information")

    def test_format_file_size_bytes(self):
        """Test file size formatting for bytes"""
        assert format_file_size(100) == "100.0 B"
        assert format_file_size(512) == "512.0 B"

    def test_format_file_size_kilobytes(self):
        """Test file size formatting for kilobytes"""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"
        assert format_file_size(2048) == "2.0 KB"

    def test_format_file_size_megabytes(self):
        """Test file size formatting for megabytes"""
        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(1024 * 1024 * 2.5) == "2.5 MB"

    def test_format_file_size_gigabytes(self):
        """Test file size formatting for gigabytes"""
        assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"
        assert format_file_size(1024 * 1024 * 1024 * 1.5) == "1.5 GB"

    def test_format_file_size_terabytes(self):
        """Test file size formatting for terabytes"""
        assert format_file_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"
        assert format_file_size(1024 * 1024 * 1024 * 1024 * 2.5) == "2.5 TB"

    def test_format_file_size_zero(self):
        """Test file size formatting for zero bytes"""
        assert format_file_size(0) == "0.0 B"
