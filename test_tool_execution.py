#!/usr/bin/env python3
"""Test script for direct tool execution functionality"""

import asyncio

from nova.core.tools.registry import FunctionRegistry
from nova.models.config import NovaConfig
from nova.models.tools import ExecutionContext


async def test_direct_tool_execution():
    """Test the direct tool execution functionality"""

    # Create configuration and registry
    config = NovaConfig()
    registry = FunctionRegistry(config)
    await registry.initialize()

    print("Testing direct tool execution...")

    # Test 1: Execute get_current_time tool (no arguments required)
    print("\n1. Testing get_current_time tool:")
    try:
        context = ExecutionContext(conversation_id="test")
        result = await registry.execute_tool("get_current_time", {}, context)

        if result.success:
            print(f"   ✓ Success! Current time: {result.result.get('current_time')}")
        else:
            print(f"   ✗ Failed: {result.error}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 2: Execute web_search tool with arguments
    print("\n2. Testing web_search tool:")
    try:
        arguments = {"query": "python programming", "max_results": 2}
        result = await registry.execute_tool("web_search", arguments, context)

        if result.success:
            results_count = len(result.result.get("results", []))
            print(f"   ✓ Success! Found {results_count} search results")
            print(f"   Provider: {result.result.get('provider')}")
        else:
            print(f"   ✗ Failed: {result.error}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 3: List available tools
    print("\n3. Available tools:")
    tools = registry.get_available_tools()
    for tool in tools[:5]:  # Show first 5 tools
        print(f"   - {tool.name}: {tool.description}")

    await registry.cleanup()
    print(f"\nTest completed! Found {len(tools)} available tools.")


if __name__ == "__main__":
    asyncio.run(test_direct_tool_execution())
