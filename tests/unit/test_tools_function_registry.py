"""Tests for the function registry system"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from nova.core.tools.handler import AsyncToolHandler, BuiltInToolModule
from nova.core.tools.registry import FunctionRegistry
from nova.models.config import NovaConfig, ToolsConfig
from nova.models.tools import (
    ExecutionContext,
    PermissionDeniedError,
    PermissionLevel,
    ToolCategory,
    ToolDefinition,
    ToolNotFoundError,
    ToolSourceType,
    ToolTimeoutError,
)


class MockToolHandler(AsyncToolHandler):
    """Mock tool handler for testing"""

    def __init__(self, result="success", should_fail=False, execution_time=0.1):
        super().__init__()
        self.result = result
        self.should_fail = should_fail
        self.execution_time = execution_time

    async def execute(self, arguments, context=None):
        await asyncio.sleep(self.execution_time)
        if self.should_fail:
            raise RuntimeError("Mock tool failure")
        return self.result


class MockToolModule(BuiltInToolModule):
    """Mock tool module for testing"""

    def __init__(self, tools=None):
        self.test_tools = tools or []

    async def get_tools(self):
        return self.test_tools


@pytest.fixture
def tools_config():
    """Create tools configuration for testing"""
    return ToolsConfig(
        enabled=True,
        permission_mode="auto",
        execution_timeout=30,
        enabled_built_in_modules=["test_module"],
    )


@pytest.fixture
def nova_config(tools_config):
    """Create nova configuration for testing"""
    return NovaConfig(tools=tools_config)


@pytest.fixture
def function_registry(nova_config):
    """Create function registry for testing"""
    return FunctionRegistry(nova_config)


@pytest.fixture
def sample_tool_definition():
    """Create sample tool definition"""
    return ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {"input": {"type": "string", "description": "Input text"}},
            "required": ["input"],
        },
        source_type=ToolSourceType.BUILT_IN,
        permission_level=PermissionLevel.SAFE,
    )


class TestFunctionRegistry:
    """Test function registry functionality"""

    def test_registry_initialization(self, function_registry, tools_config):
        """Test registry initialization"""
        assert function_registry.config == tools_config
        assert len(function_registry.tools) == 0
        assert len(function_registry.handlers) == 0
        assert function_registry.permission_manager is not None

    def test_register_tool(self, function_registry, sample_tool_definition):
        """Test tool registration"""
        handler = MockToolHandler()
        function_registry.register_tool(sample_tool_definition, handler)

        assert "test_tool" in function_registry.tools
        assert "test_tool" in function_registry.handlers
        assert function_registry.tools["test_tool"] == sample_tool_definition
        assert function_registry.handlers["test_tool"] == handler

    def test_register_duplicate_tool_warning(
        self, function_registry, sample_tool_definition
    ):
        """Test warning when registering duplicate tool"""
        handler1 = MockToolHandler()
        handler2 = MockToolHandler()

        with patch("nova.core.tools.registry.logger") as mock_logger:
            function_registry.register_tool(sample_tool_definition, handler1)
            function_registry.register_tool(sample_tool_definition, handler2)

            mock_logger.warning.assert_called_with(
                "Overriding existing tool: test_tool"
            )

    @pytest.mark.asyncio
    async def test_execute_tool_success(
        self, function_registry, sample_tool_definition
    ):
        """Test successful tool execution"""
        handler = MockToolHandler(result="test_output")
        function_registry.register_tool(sample_tool_definition, handler)

        context = ExecutionContext(conversation_id="test")
        result = await function_registry.execute_tool(
            "test_tool", {"input": "test"}, context
        )

        assert result.success is True
        assert result.result == "test_output"
        assert result.tool_name == "test_tool"
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, function_registry):
        """Test tool not found error"""
        context = ExecutionContext(conversation_id="test")

        with pytest.raises(
            ToolNotFoundError, match="Tool 'nonexistent_tool' not found"
        ):
            await function_registry.execute_tool("nonexistent_tool", {}, context)

    @pytest.mark.asyncio
    async def test_execute_tool_failure(
        self, function_registry, sample_tool_definition
    ):
        """Test tool execution failure"""
        handler = MockToolHandler(should_fail=True)
        function_registry.register_tool(sample_tool_definition, handler)

        context = ExecutionContext(conversation_id="test")

        with pytest.raises(Exception) as exc_info:  # Should raise ToolExecutionError
            await function_registry.execute_tool(
                "test_tool", {"input": "test"}, context
            )

        # Verify we got an exception
        assert exc_info.value is not None

    @pytest.mark.asyncio
    async def test_execute_tool_timeout(
        self, function_registry, sample_tool_definition
    ):
        """Test tool execution timeout"""
        # Create registry with very short timeout
        tools_config = ToolsConfig(execution_timeout=1)
        nova_config = NovaConfig(tools=tools_config)
        registry = FunctionRegistry(nova_config)

        # Create handler that takes longer than timeout
        handler = MockToolHandler(execution_time=2)
        registry.register_tool(sample_tool_definition, handler)

        context = ExecutionContext(conversation_id="test")

        with pytest.raises(ToolTimeoutError):
            await registry.execute_tool("test_tool", {"input": "test"}, context)

    def test_get_available_tools(self, function_registry, sample_tool_definition):
        """Test getting available tools"""
        handler = MockToolHandler()
        function_registry.register_tool(sample_tool_definition, handler)

        context = ExecutionContext(conversation_id="test")
        available = function_registry.get_available_tools(context)

        assert len(available) == 1
        assert available[0] == sample_tool_definition

    def test_get_tools_by_category(self, function_registry):
        """Test getting tools by category"""
        # Create tools in different categories
        file_tool = ToolDefinition(
            name="file_tool",
            description="File tool",
            parameters={"type": "object", "properties": {}},
            source_type=ToolSourceType.BUILT_IN,
            category=ToolCategory.FILE_SYSTEM,
        )

        net_tool = ToolDefinition(
            name="net_tool",
            description="Information tool",
            parameters={"type": "object", "properties": {}},
            source_type=ToolSourceType.BUILT_IN,
            category=ToolCategory.INFORMATION,
        )

        function_registry.register_tool(file_tool, MockToolHandler())
        function_registry.register_tool(net_tool, MockToolHandler())

        context = ExecutionContext(conversation_id="test")
        file_tools = function_registry.get_tools_by_category("file_system", context)
        info_tools = function_registry.get_tools_by_category("information", context)

        assert len(file_tools) == 1
        assert file_tools[0].name == "file_tool"
        assert len(info_tools) == 1
        assert info_tools[0].name == "net_tool"

    def test_search_tools(self, function_registry):
        """Test searching tools"""
        # Create tools with different names and descriptions
        read_tool = ToolDefinition(
            name="read_file",
            description="Read file contents",
            parameters={"type": "object", "properties": {}},
            source_type=ToolSourceType.BUILT_IN,
            tags=["file", "read"],
        )

        write_tool = ToolDefinition(
            name="write_file",
            description="Write file contents",
            parameters={"type": "object", "properties": {}},
            source_type=ToolSourceType.BUILT_IN,
            tags=["file", "write"],
        )

        search_tool = ToolDefinition(
            name="web_search",
            description="Search the web",
            parameters={"type": "object", "properties": {}},
            source_type=ToolSourceType.BUILT_IN,
            tags=["web", "search"],
        )

        for tool in [read_tool, write_tool, search_tool]:
            function_registry.register_tool(tool, MockToolHandler())

        context = ExecutionContext(conversation_id="test")

        # Search by name
        file_tools = function_registry.search_tools("file", context)
        assert len(file_tools) == 2

        # Search by description
        web_tools = function_registry.search_tools("web", context)
        assert len(web_tools) == 1
        assert web_tools[0].name == "web_search"

        # Search by tag
        read_tools = function_registry.search_tools("read", context)
        assert len(read_tools) == 1
        assert read_tools[0].name == "read_file"

    def test_get_openai_tools_schema(self, function_registry, sample_tool_definition):
        """Test OpenAI tools schema generation"""
        handler = MockToolHandler()
        function_registry.register_tool(sample_tool_definition, handler)

        context = ExecutionContext(conversation_id="test")
        schema = function_registry.get_openai_tools_schema(context)

        assert len(schema) == 1
        assert schema[0]["type"] == "function"
        assert schema[0]["function"]["name"] == "test_tool"
        assert schema[0]["function"]["description"] == "A test tool"

    def test_get_tool_info(self, function_registry, sample_tool_definition):
        """Test getting tool information"""
        handler = MockToolHandler()
        function_registry.register_tool(sample_tool_definition, handler)

        tool_info = function_registry.get_tool_info("test_tool")
        assert tool_info == sample_tool_definition

        missing_info = function_registry.get_tool_info("missing_tool")
        assert missing_info is None

    def test_list_tool_names(self, function_registry, sample_tool_definition):
        """Test listing tool names"""
        handler = MockToolHandler()
        function_registry.register_tool(sample_tool_definition, handler)

        context = ExecutionContext(conversation_id="test")
        names = function_registry.list_tool_names(context)

        assert names == ["test_tool"]

    @pytest.mark.asyncio
    async def test_execution_stats(self, function_registry, sample_tool_definition):
        """Test execution statistics"""
        handler = MockToolHandler()
        function_registry.register_tool(sample_tool_definition, handler)

        context = ExecutionContext(conversation_id="test")

        # Initial stats
        stats = function_registry.get_execution_stats()
        assert stats["total_calls"] == 0
        assert stats["successful_calls"] == 0
        assert stats["success_rate"] == 0

        # Execute tool successfully
        await function_registry.execute_tool("test_tool", {"input": "test"}, context)

        # Check updated stats
        stats = function_registry.get_execution_stats()
        assert stats["total_calls"] == 1
        assert stats["successful_calls"] == 1
        assert stats["success_rate"] == 1.0
        assert stats["registered_tools"] == 1

    @pytest.mark.asyncio
    async def test_cleanup(self, function_registry):
        """Test cleanup functionality"""
        # Add some tools
        tool = ToolDefinition(
            name="cleanup_test",
            description="Test cleanup",
            parameters={"type": "object", "properties": {}},
            source_type=ToolSourceType.BUILT_IN,
        )
        function_registry.register_tool(tool, MockToolHandler())

        await function_registry.cleanup()

        # Check registries were cleared (built_in_modules no longer exists)
        assert len(function_registry.tools) == 0
        assert len(function_registry.handlers) == 0

    def test_get_recovery_suggestions(self, function_registry):
        """Test recovery suggestions for errors"""
        suggestions = function_registry._get_recovery_suggestions(
            "test_tool", "file not found"
        )

        assert "Check if the file path is correct" in suggestions
        assert len(suggestions) > 0

    @pytest.mark.asyncio
    async def test_permission_denied(self, function_registry, sample_tool_definition):
        """Test permission denied during tool execution"""
        handler = MockToolHandler()
        function_registry.register_tool(sample_tool_definition, handler)

        # Mock permission manager to deny permission
        function_registry.permission_manager.check_permission = AsyncMock(
            return_value=False
        )

        context = ExecutionContext(conversation_id="test")

        with pytest.raises(PermissionDeniedError):
            await function_registry.execute_tool(
                "test_tool", {"input": "test"}, context
            )
