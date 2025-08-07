"""Tests for direct tool execution functionality in chat interface"""

import pytest

from nova.core.chat import ChatManager
from nova.models.tools import (
    PermissionLevel,
    ToolCategory,
    ToolDefinition,
    ToolSourceType,
)


class TestDirectToolExecution:
    """Test direct tool execution functionality"""

    @pytest.fixture
    def chat_manager(self):
        """Create ChatManager for testing"""
        return ChatManager()

    @pytest.fixture
    def mock_tool_info(self):
        """Create mock tool info for testing"""
        return ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results",
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Whether to enable feature",
                    },
                    "tags": {"type": "array", "description": "List of tags"},
                },
                "required": ["query"],
            },
            source_type=ToolSourceType.BUILT_IN,
            permission_level=PermissionLevel.SAFE,
            category=ToolCategory.GENERAL,
        )

    def test_parse_tool_arguments_basic(self, chat_manager, mock_tool_info):
        """Test basic argument parsing"""
        args = ["query=test", "max_results=5"]

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        assert result == {"query": "test", "max_results": 5}

    def test_parse_tool_arguments_quoted_strings(self, chat_manager, mock_tool_info):
        """Test parsing quoted string arguments"""
        args = ['query="python programming"', "max_results=3"]

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        assert result == {"query": "python programming", "max_results": 3}

    def test_parse_tool_arguments_boolean(self, chat_manager, mock_tool_info):
        """Test parsing boolean arguments"""
        test_cases = [
            (["enabled=true"], {"enabled": True}),
            (["enabled=false"], {"enabled": False}),
            (["enabled=1"], {"enabled": True}),
            (["enabled=0"], {"enabled": False}),
            (["enabled=yes"], {"enabled": True}),
            (["enabled=no"], {"enabled": False}),
        ]

        for args, expected in test_cases:
            # Add required parameter
            args.append("query=test")
            expected["query"] = "test"

            result = chat_manager._parse_tool_arguments(
                "test_tool", args, mock_tool_info
            )
            assert result == expected

    def test_parse_tool_arguments_array(self, chat_manager, mock_tool_info):
        """Test parsing array arguments"""
        args = ["query=test", "tags=python,programming,tutorial"]

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        expected = {"query": "test", "tags": ["python", "programming", "tutorial"]}
        assert result == expected

    def test_parse_tool_arguments_missing_required(self, chat_manager, mock_tool_info):
        """Test error handling for missing required parameters"""
        args = ["max_results=5"]  # Missing required 'query'

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        assert result is None

    def test_parse_tool_arguments_invalid_format(self, chat_manager, mock_tool_info):
        """Test error handling for invalid argument format"""
        args = ["invalid_format"]  # Should be key=value

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        assert result is None

    def test_parse_tool_arguments_invalid_type(self, chat_manager, mock_tool_info):
        """Test error handling for invalid type conversion"""
        args = ["query=test", "max_results=invalid_number"]

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        assert result is None

    def test_parse_tool_arguments_unknown_parameter(self, chat_manager, mock_tool_info):
        """Test handling of unknown parameters"""
        args = ["query=test", "unknown_param=value"]

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        # Should include unknown parameter as string
        assert result == {"query": "test", "unknown_param": "value"}

    def test_parse_tool_arguments_complex_quotes(self, chat_manager, mock_tool_info):
        """Test parsing arguments with complex quoted strings"""
        args = ['query="search with \\"nested quotes\\""', "max_results=1"]

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        assert result == {"query": 'search with "nested quotes"', "max_results": 1}

    def test_parse_tool_arguments_empty_args(self, chat_manager, mock_tool_info):
        """Test parsing with empty argument list"""
        args = []

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        # Should fail due to missing required parameter
        assert result is None

    def test_parse_tool_arguments_spaces_in_values(self, chat_manager, mock_tool_info):
        """Test parsing with spaces in unquoted values (should fail)"""
        args = ["query=python programming"]  # Space without quotes

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        # Should fail due to invalid format
        assert result is None


class TestToolExecutionHelpers:
    """Test helper methods for tool execution"""

    @pytest.fixture
    def chat_manager(self):
        """Create ChatManager for testing"""
        return ChatManager()

    def test_tool_info_display_format(self, chat_manager):
        """Test that tool info is displayed in correct format"""
        # This test would need a mock session and registry
        # For now, we just test that the method exists and can be called
        assert hasattr(chat_manager, "_show_tool_info")
        assert hasattr(chat_manager, "_execute_tool_direct")
        assert hasattr(chat_manager, "_parse_tool_arguments")

    def test_execution_context_creation(self, chat_manager):
        """Test that execution context is created properly"""
        # This is tested implicitly in the execution method
        # The method should create ExecutionContext with conversation_id
        assert hasattr(chat_manager, "_execute_tool_direct")


class TestToolArgumentParsingSafety:
    """Test security and safety aspects of argument parsing"""

    @pytest.fixture
    def chat_manager(self):
        return ChatManager()

    @pytest.fixture
    def mock_tool_info(self):
        return ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {
                    "data": {"type": "object", "description": "JSON data"},
                    "query": {"type": "string", "description": "Query string"},
                },
                "required": ["query"],
            },
            source_type=ToolSourceType.BUILT_IN,
            permission_level=PermissionLevel.SAFE,
            category=ToolCategory.GENERAL,
        )

    def test_json_object_parsing(self, chat_manager, mock_tool_info):
        """Test parsing JSON object parameters safely"""
        args = ["query=test", 'data={"key": "value", "number": 42}']

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        expected = {"query": "test", "data": {"key": "value", "number": 42}}
        assert result == expected

    def test_invalid_json_handling(self, chat_manager, mock_tool_info):
        """Test handling of invalid JSON in object parameters"""
        args = ["query=test", "data={invalid json}"]

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        # Should fail due to invalid JSON
        assert result is None

    def test_large_string_handling(self, chat_manager, mock_tool_info):
        """Test handling of large string values"""
        large_value = "x" * 1000
        args = [f'query="{large_value}"']

        result = chat_manager._parse_tool_arguments("test_tool", args, mock_tool_info)

        assert result == {"query": large_value}
        assert len(result["query"]) == 1000
