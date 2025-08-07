"""Tests for tools permission system"""

from unittest.mock import patch

import pytest

from nova.core.tools.permissions import ToolPermissionManager
from nova.models.tools import (
    ExecutionContext,
    PermissionLevel,
    ToolDefinition,
    ToolSourceType,
)


@pytest.fixture
def permission_manager():
    """Create permission manager for testing"""
    return ToolPermissionManager("prompt")


@pytest.fixture
def safe_tool():
    """Create a safe tool for testing"""
    return ToolDefinition(
        name="safe_tool",
        description="A safe tool",
        parameters={"type": "object", "properties": {}},
        source_type=ToolSourceType.BUILT_IN,
        permission_level=PermissionLevel.SAFE,
    )


@pytest.fixture
def elevated_tool():
    """Create an elevated tool for testing"""
    return ToolDefinition(
        name="elevated_tool",
        description="An elevated tool",
        parameters={"type": "object", "properties": {}},
        source_type=ToolSourceType.BUILT_IN,
        permission_level=PermissionLevel.ELEVATED,
    )


@pytest.fixture
def dangerous_tool():
    """Create a dangerous tool for testing"""
    return ToolDefinition(
        name="dangerous_tool",
        description="A dangerous tool",
        parameters={"type": "object", "properties": {}},
        source_type=ToolSourceType.BUILT_IN,
        permission_level=PermissionLevel.DANGEROUS,
    )


@pytest.fixture
def execution_context():
    """Create execution context for testing"""
    return ExecutionContext(conversation_id="test-123")


class TestToolPermissionManager:
    """Test tool permission management"""

    def test_init_auto_mode(self):
        """Test initialization with auto mode"""
        manager = ToolPermissionManager("auto")
        assert manager.permission_mode == "auto"
        assert len(manager.user_permissions) == 4  # Should have 4 permission levels

    def test_init_prompt_mode(self):
        """Test initialization with prompt mode"""
        manager = ToolPermissionManager("prompt")
        assert manager.permission_mode == "prompt"

    def test_init_deny_mode(self):
        """Test initialization with deny mode"""
        manager = ToolPermissionManager("deny")
        assert manager.permission_mode == "deny"

    @pytest.mark.asyncio
    async def test_check_permission_safe_tool(
        self, permission_manager, safe_tool, execution_context
    ):
        """Test permission check for safe tool"""
        result = await permission_manager.check_permission(
            safe_tool, {}, execution_context
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_elevated_auto_mode(
        self, elevated_tool, execution_context
    ):
        """Test elevated tool permission in auto mode"""
        manager = ToolPermissionManager("auto")
        result = await manager.check_permission(elevated_tool, {}, execution_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_elevated_deny_mode(
        self, elevated_tool, execution_context
    ):
        """Test elevated tool permission in deny mode"""
        manager = ToolPermissionManager("deny")
        result = await manager.check_permission(elevated_tool, {}, execution_context)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_permission_dangerous_always_denied(
        self, dangerous_tool, execution_context
    ):
        """Test dangerous tools are always denied"""
        # Test in auto mode
        auto_manager = ToolPermissionManager("auto")
        result = await auto_manager.check_permission(
            dangerous_tool, {}, execution_context
        )
        assert result is False

        # Test in prompt mode
        prompt_manager = ToolPermissionManager("prompt")
        result = await prompt_manager.check_permission(
            dangerous_tool, {}, execution_context
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_check_permission_with_granted_permission(
        self, permission_manager, elevated_tool, execution_context
    ):
        """Test permission check with granted permission"""
        # Grant permission for the tool
        permission_manager.grant_permission("elevated_tool", PermissionLevel.ELEVATED)

        result = await permission_manager.check_permission(
            elevated_tool, {}, execution_context
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_prompt_user_approval(
        self, permission_manager, elevated_tool, execution_context
    ):
        """Test permission check with user prompt"""
        # Mock the _request_user_permission method instead
        with patch.object(
            permission_manager, "_request_user_permission", return_value=True
        ):
            result = await permission_manager.check_permission(
                elevated_tool, {}, execution_context
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_prompt_user_denied(
        self, permission_manager, elevated_tool, execution_context
    ):
        """Test permission check with user denial"""
        # Mock the _request_user_permission method instead
        with patch.object(
            permission_manager, "_request_user_permission", return_value=False
        ):
            result = await permission_manager.check_permission(
                elevated_tool, {}, execution_context
            )
            assert result is False

    def test_grant_permission(self, permission_manager):
        """Test granting permission for a tool"""
        permission_manager.grant_permission("test_tool", PermissionLevel.ELEVATED)

        # Check permission was granted by verifying it's in the user_permissions
        assert (
            "test_tool" in permission_manager.user_permissions[PermissionLevel.ELEVATED]
        )

    def test_revoke_permission(self, permission_manager):
        """Test revoking permission for a tool"""
        # First grant permission
        permission_manager.grant_permission("test_tool", PermissionLevel.ELEVATED)

        # Then revoke it
        permission_manager.revoke_permission("test_tool", PermissionLevel.ELEVATED)

        # Check it was removed
        assert (
            "test_tool"
            not in permission_manager.user_permissions[PermissionLevel.ELEVATED]
        )
