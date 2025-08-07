"""Tests for profile-based tools configuration"""

from nova.models.config import AIProfile, NovaConfig, ToolsConfig


class TestProfileToolsConfiguration:
    """Test profile-based tools configuration"""

    def test_profile_without_tools_config_uses_global(self):
        """Test that profiles without tools config use global settings"""
        global_tools = ToolsConfig(
            enabled=True,
            permission_mode="prompt",
            enabled_built_in_modules=["file_ops", "web_search"],
            execution_timeout=30,
        )

        profile = AIProfile(
            name="test_profile",
            provider="openai",
            model_name="gpt-4",
            tools=None,  # No custom tools config
        )

        config = NovaConfig(
            tools=global_tools,
            profiles={"test_profile": profile},
            active_profile="test_profile",
        )

        effective_tools = config.get_effective_tools_config()

        # Should return global config
        assert effective_tools == global_tools
        assert effective_tools.permission_mode == "prompt"
        assert effective_tools.enabled_built_in_modules == ["file_ops", "web_search"]

    def test_profile_with_custom_tools_config(self):
        """Test that profiles with custom tools config override global"""
        global_tools = ToolsConfig(
            enabled=True,
            permission_mode="prompt",
            enabled_built_in_modules=["file_ops", "web_search"],
            execution_timeout=30,
        )

        profile_tools = ToolsConfig(
            enabled=False,
            permission_mode="deny",
            enabled_built_in_modules=["conversation"],
            execution_timeout=60,
        )

        profile = AIProfile(
            name="restricted_profile",
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            tools=profile_tools,
        )

        config = NovaConfig(
            tools=global_tools,
            profiles={"restricted_profile": profile},
            active_profile="restricted_profile",
        )

        effective_tools = config.get_effective_tools_config()

        # Should return profile-specific config
        assert effective_tools == profile_tools
        assert effective_tools.permission_mode == "deny"
        assert effective_tools.enabled_built_in_modules == ["conversation"]
        assert effective_tools.execution_timeout == 60

    def test_fallback_to_default_profile(self):
        """Test fallback to default profile when active profile not found"""
        global_tools = ToolsConfig(enabled=True, permission_mode="auto")

        default_tools = ToolsConfig(
            enabled=True,
            permission_mode="prompt",
            enabled_built_in_modules=["file_ops"],
        )

        default_profile = AIProfile(
            name="default",
            provider="openai",
            model_name="gpt-3.5-turbo",
            tools=default_tools,
        )

        config = NovaConfig(
            tools=global_tools,
            profiles={"default": default_profile},
            active_profile="nonexistent_profile",
        )

        effective_tools = config.get_effective_tools_config()

        # Should fall back to default profile's tools config
        assert effective_tools == default_tools
        assert effective_tools.permission_mode == "prompt"

    def test_fallback_to_global_when_no_profiles(self):
        """Test fallback to global config when no profiles exist"""
        global_tools = ToolsConfig(
            enabled=True,
            permission_mode="auto",
            enabled_built_in_modules=["file_ops", "web_search", "conversation"],
        )

        config = NovaConfig(
            tools=global_tools,
            profiles={},
            active_profile="any_profile",  # No profiles
        )

        effective_tools = config.get_effective_tools_config()

        # Should return global config
        assert effective_tools == global_tools
        assert effective_tools.permission_mode == "auto"

    def test_profile_tools_inheritance_pattern(self):
        """Test the inheritance pattern: profile -> default -> global"""
        global_tools = ToolsConfig(
            enabled=True,
            permission_mode="auto",
            enabled_built_in_modules=["file_ops"],
            execution_timeout=30,
        )

        # Default profile has partial override
        default_profile = AIProfile(
            name="default",
            provider="openai",
            model_name="gpt-3.5-turbo",
            tools=ToolsConfig(
                enabled=True,
                permission_mode="prompt",  # Override
                enabled_built_in_modules=["file_ops", "web_search"],  # Override
                execution_timeout=30,
            ),
        )

        # Active profile has no tools config
        active_profile = AIProfile(
            name="active",
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            tools=None,  # Should fall back to default
        )

        config = NovaConfig(
            tools=global_tools,
            profiles={"default": default_profile, "active": active_profile},
            active_profile="active",
        )

        effective_tools = config.get_effective_tools_config()

        # Should use default profile's config since active has none
        assert effective_tools.permission_mode == "prompt"
        assert effective_tools.enabled_built_in_modules == ["file_ops", "web_search"]

    def test_multiple_profiles_different_configs(self):
        """Test multiple profiles with different tools configurations"""
        global_tools = ToolsConfig(enabled=True, permission_mode="auto")

        dev_profile = AIProfile(
            name="development",
            provider="openai",
            model_name="gpt-4",
            tools=ToolsConfig(
                enabled=True,
                permission_mode="auto",
                enabled_built_in_modules=["file_ops", "web_search", "conversation"],
            ),
        )

        prod_profile = AIProfile(
            name="production",
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            tools=ToolsConfig(
                enabled=True,
                permission_mode="prompt",
                enabled_built_in_modules=["conversation"],  # Limited set
            ),
        )

        config = NovaConfig(
            tools=global_tools,
            profiles={"development": dev_profile, "production": prod_profile},
        )

        # Test development profile
        config.active_profile = "development"
        dev_tools = config.get_effective_tools_config()
        assert dev_tools.permission_mode == "auto"
        assert len(dev_tools.enabled_built_in_modules) == 3

        # Test production profile
        config.active_profile = "production"
        prod_tools = config.get_effective_tools_config()
        assert prod_tools.permission_mode == "prompt"
        assert prod_tools.enabled_built_in_modules == ["conversation"]

    def test_tools_config_serialization(self):
        """Test that tools config can be properly serialized/deserialized"""
        tools_config = ToolsConfig(
            enabled=False,
            permission_mode="deny",
            enabled_built_in_modules=["conversation"],
            execution_timeout=45,
            max_concurrent_tools=2,
            tool_suggestions=False,
            execution_logging=False,
            mcp_enabled=True,
        )

        profile = AIProfile(
            name="test", provider="ollama", model_name="llama2", tools=tools_config
        )

        # Test serialization
        profile_dict = profile.model_dump()
        assert profile_dict["tools"]["enabled"] is False
        assert profile_dict["tools"]["permission_mode"] == "deny"
        assert profile_dict["tools"]["enabled_built_in_modules"] == ["conversation"]

        # Test deserialization
        restored_profile = AIProfile(**profile_dict)
        assert restored_profile.tools.enabled is False
        assert restored_profile.tools.permission_mode == "deny"
        assert restored_profile.tools.execution_timeout == 45
