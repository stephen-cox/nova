"""Integration tests for tools system"""

import asyncio

import pytest
import pytest_asyncio

from nova.core.ai_client import create_ai_client
from nova.core.tools.registry import FunctionRegistry
from nova.models.config import AIModelConfig, NovaConfig, ToolsConfig
from nova.models.tools import ExecutionContext


@pytest.fixture
def tools_config():
    """Create tools configuration"""
    return ToolsConfig(
        enabled=True,
        permission_mode="auto",
        execution_timeout=30,
        enabled_built_in_modules=["file_ops"],
    )


@pytest.fixture
def ai_config():
    """Create AI configuration"""
    return AIModelConfig(provider="openai", model_name="gpt-4", api_key="test-key")


@pytest.fixture
def nova_config(tools_config):
    """Create nova configuration"""
    return NovaConfig(tools=tools_config)


@pytest_asyncio.fixture
async def function_registry(nova_config):
    """Create initialized function registry"""
    registry = FunctionRegistry(nova_config)
    await registry.initialize()
    yield registry
    await registry.cleanup()


class TestToolsSystemIntegration:
    """Test complete tools system integration"""

    @pytest.mark.asyncio
    async def test_registry_initialization_with_built_in_tools(self, function_registry):
        """Test registry initializes with built-in tools"""
        assert len(function_registry.tools) > 0
        assert "read_file" in function_registry.tools
        assert "write_file" in function_registry.tools
        assert "list_directory" in function_registry.tools
        assert "get_file_info" in function_registry.tools

    @pytest.mark.asyncio
    async def test_ai_client_with_tools(self, ai_config, function_registry):
        """Test AI client integration with tools"""
        ai_client = create_ai_client(ai_config, function_registry)

        assert hasattr(ai_client, "function_registry")
        assert ai_client.function_registry == function_registry
        assert hasattr(ai_client, "generate_response_with_tools")

    @pytest.mark.asyncio
    async def test_tools_schema_generation(self, function_registry):
        """Test OpenAI tools schema generation"""
        context = ExecutionContext(conversation_id="test")
        schema = function_registry.get_openai_tools_schema(context)

        assert len(schema) > 0
        for tool_schema in schema:
            assert tool_schema["type"] == "function"
            assert "function" in tool_schema
            assert "name" in tool_schema["function"]
            assert "description" in tool_schema["function"]
            assert "parameters" in tool_schema["function"]

    @pytest.mark.asyncio
    async def test_tool_execution_flow(self, function_registry):
        """Test complete tool execution flow"""
        import tempfile
        from pathlib import Path

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Test content for tool execution")
            temp_file = Path(f.name)

        try:
            context = ExecutionContext(conversation_id="test")

            # Execute read_file tool
            result = await function_registry.execute_tool(
                "read_file", {"file_path": str(temp_file)}, context
            )

            assert result.success is True
            assert result.result == "Test content for tool execution"
            assert result.tool_name == "read_file"
            assert result.execution_time_ms > 0

        finally:
            # Cleanup
            temp_file.unlink()

    @pytest.mark.asyncio
    async def test_tool_search_and_filtering(self, function_registry):
        """Test tool search and filtering functionality"""
        context = ExecutionContext(conversation_id="test")

        # Search for file-related tools
        file_tools = function_registry.search_tools("file", context)
        assert len(file_tools) > 0

        # Get tools by category
        file_system_tools = function_registry.get_tools_by_category(
            "file_system", context
        )
        assert len(file_system_tools) > 0

        # Verify all file system tools are in the file search results
        file_names = [tool.name for tool in file_tools]
        for tool in file_system_tools:
            assert tool.name in file_names

    @pytest.mark.asyncio
    async def test_permission_system_integration(self, tools_config):
        """Test permission system integration"""
        # Test with different permission modes
        for mode in ["auto", "prompt", "deny"]:
            tools_config = ToolsConfig(
                enabled=True,
                permission_mode=mode,
                enabled_built_in_modules=["file_ops"],
            )

            nova_config = NovaConfig(tools=tools_config)
            registry = FunctionRegistry(nova_config)
            await registry.initialize()

            context = ExecutionContext(conversation_id="test")
            available_tools = registry.get_available_tools(context)

            if mode == "deny":
                # In deny mode, elevated tools should not be available
                elevated_tools = [
                    tool
                    for tool in available_tools
                    if tool.permission_level.value == "elevated"
                ]
                assert len(elevated_tools) == 0
            else:
                # In auto/prompt mode, all safe tools should be available
                safe_tools = [
                    tool
                    for tool in available_tools
                    if tool.permission_level.value == "safe"
                ]
                assert len(safe_tools) > 0

    @pytest.mark.asyncio
    async def test_execution_statistics_tracking(self, function_registry):
        """Test execution statistics are properly tracked"""
        import tempfile
        from pathlib import Path

        initial_stats = function_registry.get_execution_stats()
        initial_calls = initial_stats["total_calls"]

        # Execute a tool
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Stats test content")
            temp_file = Path(f.name)

        try:
            context = ExecutionContext(conversation_id="test")
            await function_registry.execute_tool(
                "read_file", {"file_path": str(temp_file)}, context
            )

            # Check updated stats
            updated_stats = function_registry.get_execution_stats()
            assert updated_stats["total_calls"] == initial_calls + 1
            assert updated_stats["successful_calls"] > initial_stats["successful_calls"]
            assert updated_stats["success_rate"] > 0

        finally:
            temp_file.unlink()

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, function_registry):
        """Test error handling and recovery suggestions"""
        context = ExecutionContext(conversation_id="test")

        # Try to read non-existent file
        with pytest.raises(Exception) as exc_info:
            await function_registry.execute_tool(
                "read_file", {"file_path": "/nonexistent/path/file.txt"}, context
            )

        # The actual error handling may vary, but we can check it doesn't crash
        # Verify we got an exception
        assert exc_info.value is not None

    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self, function_registry):
        """Test concurrent tool execution"""
        import tempfile
        from pathlib import Path

        # Create multiple temporary files
        temp_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".txt"
            ) as f:
                f.write(f"Content {i}")
                temp_files.append(Path(f.name))

        try:
            context = ExecutionContext(conversation_id="test")

            # Execute multiple tools concurrently
            tasks = []
            for temp_file in temp_files:
                task = function_registry.execute_tool(
                    "read_file", {"file_path": str(temp_file)}, context
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            # Verify all executions succeeded
            for i, result in enumerate(results):
                assert result.success is True
                assert result.result == f"Content {i}"

        finally:
            # Cleanup
            for temp_file in temp_files:
                temp_file.unlink()

    @pytest.mark.asyncio
    async def test_registry_cleanup(self, function_registry):
        """Test registry cleanup functionality"""
        # Verify registry has tools
        assert len(function_registry.tools) > 0
        assert len(function_registry.handlers) > 0

        # Cleanup
        await function_registry.cleanup()

        # Verify cleanup (built_in_modules no longer exists)
        assert len(function_registry.tools) == 0
        assert len(function_registry.handlers) == 0

    @pytest.mark.asyncio
    async def test_tools_config_validation(self):
        """Test tools configuration validation"""
        # Valid config
        valid_tools_config = ToolsConfig(
            enabled=True,
            permission_mode="auto",
            execution_timeout=30,
            enabled_built_in_modules=["file_ops"],
        )

        nova_config = NovaConfig(tools=valid_tools_config)
        registry = FunctionRegistry(nova_config)
        await registry.initialize()
        assert len(registry.tools) > 0

        # Test with invalid permission mode
        with pytest.raises(ValueError, match="Permission mode must be one of"):
            ToolsConfig(permission_mode="invalid_mode")

    @pytest.mark.asyncio
    async def test_tool_info_retrieval(self, function_registry):
        """Test tool information retrieval"""
        # Get tool info
        tool_info = function_registry.get_tool_info("read_file")
        assert tool_info is not None
        assert tool_info.name == "read_file"
        assert tool_info.description is not None
        assert tool_info.parameters is not None

        # Test non-existent tool
        missing_info = function_registry.get_tool_info("nonexistent_tool")
        assert missing_info is None

        # Test tool names listing
        context = ExecutionContext(conversation_id="test")
        tool_names = function_registry.list_tool_names(context)
        assert "read_file" in tool_names
        assert len(tool_names) > 0
