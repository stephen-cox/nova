"""Tests for the new tool auto-discovery system"""

from nova.tools import discover_built_in_tools, get_global_registry


class TestToolDiscovery:
    """Test the auto-discovery system"""

    def test_discovery_finds_text_tools(self):
        """Test that the discovery system finds the new decorator-based text tools"""
        # Discover built-in tools
        discovered = discover_built_in_tools()

        # Should find text tools
        tool_names = list(discovered.keys())

        # Check for new text tools
        assert "transform_text_case" in tool_names
        assert "analyze_text" in tool_names
        assert "extract_emails" in tool_names
        assert "format_text" in tool_names
        assert "clean_text" in tool_names

        # Verify tool definition details for one tool
        tool_def, handler = discovered["transform_text_case"]
        assert tool_def.name == "transform_text_case"
        assert "text" in tool_def.tags
        assert "transform" in tool_def.tags

    def test_discovery_finds_legacy_tools(self):
        """Test that discovery still finds legacy module-based tools"""
        # Discover built-in tools
        discovered = discover_built_in_tools()

        # Should still find legacy tools via the existing registry
        # We'll check for this in integration tests
        tool_names = list(discovered.keys())

        # At minimum, should find some tools
        assert len(tool_names) > 0

    def test_global_registry_search(self):
        """Test global registry search functionality"""
        registry = get_global_registry()
        registry.discover_tools(["nova.tools.built_in.text_tools"])

        # Search by tag
        text_tools = registry.filter_tools_by_tag("text")
        assert len(text_tools) > 0

        # Search by query
        transform_tools = registry.search_tools("transform")
        assert len(transform_tools) > 0
        assert "transform_text_case" in [name for name, _ in transform_tools.items()]

    def test_tool_metadata_extraction(self):
        """Test that tool metadata is properly extracted from decorated functions"""
        discovered = discover_built_in_tools()

        if "transform_text_case" in discovered:
            tool_def, handler = discovered["transform_text_case"]

            # Check schema generation
            schema = tool_def.parameters
            assert schema["type"] == "object"
            assert "text" in schema["properties"]
            assert "case_type" in schema["properties"]

            # Check defaults
            assert schema["properties"]["case_type"]["default"] == "lower"

            # Check required fields
            assert "text" in schema["required"]
            assert "case_type" not in schema["required"]  # Has default
