"""Tool permission management system"""

import hashlib
import logging

from nova.models.tools import ExecutionContext, PermissionLevel, ToolDefinition
from nova.utils.formatting import print_info, print_warning

logger = logging.getLogger(__name__)


class ToolPermissionManager:
    """Manage tool execution permissions and security"""

    def __init__(self, permission_mode: str = "prompt"):
        self.permission_mode = permission_mode  # "auto", "prompt", "deny"
        self.user_permissions: dict[str, set[str]] = {
            PermissionLevel.SAFE: set(),
            PermissionLevel.ELEVATED: set(),
            PermissionLevel.SYSTEM: set(),
            PermissionLevel.DANGEROUS: set(),
        }
        self.session_grants: set[str] = set()
        self.permanent_grants: set[str] = set()

    async def check_permission(
        self, tool: ToolDefinition, arguments: dict, context: ExecutionContext = None
    ) -> bool:
        """Check if tool execution is permitted"""

        # Always allow safe tools
        if tool.permission_level == PermissionLevel.SAFE:
            return True

        # Block dangerous tools unless explicitly allowed
        if tool.permission_level == PermissionLevel.DANGEROUS:
            return tool.name in self.user_permissions.get(
                PermissionLevel.DANGEROUS, set()
            )

        # Handle elevated permissions based on mode
        if tool.permission_level == PermissionLevel.ELEVATED:
            return await self._check_elevated_permission(tool, arguments, context)

        # System tools require explicit permission
        if tool.permission_level == PermissionLevel.SYSTEM:
            return await self._check_system_permission(tool, arguments, context)

        return False

    async def _check_elevated_permission(
        self, tool: ToolDefinition, arguments: dict, context: ExecutionContext
    ) -> bool:
        """Check elevated permission based on mode"""

        # Check if permission has been explicitly granted
        if tool.name in self.user_permissions.get(PermissionLevel.ELEVATED, set()):
            return True

        if self.permission_mode == "auto":
            return True
        elif self.permission_mode == "prompt":
            return await self._request_user_permission(tool, arguments, context)
        else:  # "deny"
            return False

    async def _check_system_permission(
        self, tool: ToolDefinition, arguments: dict, context: ExecutionContext
    ) -> bool:
        """Check system permission - always requires explicit approval"""

        # Check if permanently granted
        if tool.name in self.permanent_grants:
            return True

        return await self._request_admin_permission(tool, arguments, context)

    async def _request_user_permission(
        self, tool: ToolDefinition, arguments: dict, context: ExecutionContext
    ) -> bool:
        """Request user permission for tool execution"""

        # Create permission key for this specific request
        permission_key = self._create_permission_key(tool.name, arguments)

        # Check if already granted for this session
        if permission_key in self.session_grants:
            return True

        # Show permission request to user
        print_warning(f"🔐 Permission requested for tool: {tool.name}")
        print_info(f"Description: {tool.description}")
        print_info(f"Arguments: {self._format_arguments(arguments)}")

        if self._is_potentially_destructive(tool, arguments):
            print_warning("⚠️  This operation may modify files or system state")

        try:
            response = (
                input("Allow this tool execution? [y/N/always]: ").strip().lower()
            )

            if response in ["y", "yes"]:
                return True
            elif response == "always":
                self.session_grants.add(permission_key)
                return True
            else:
                return False
        except (KeyboardInterrupt, EOFError):
            return False

    async def _request_admin_permission(
        self, tool: ToolDefinition, arguments: dict, context: ExecutionContext
    ) -> bool:
        """Request admin permission for system tools"""

        print_warning(f"🚨 SYSTEM TOOL: {tool.name}")
        print_info(f"Description: {tool.description}")
        print_info(f"Arguments: {self._format_arguments(arguments)}")
        print_warning(
            "⚠️  This is a system-level operation that may affect your computer"
        )

        try:
            response = (
                input("Allow this system tool? [y/N/permanent]: ").strip().lower()
            )

            if response in ["y", "yes"]:
                return True
            elif response == "permanent":
                self.permanent_grants.add(tool.name)
                return True
            else:
                return False
        except (KeyboardInterrupt, EOFError):
            return False

    def _is_potentially_destructive(
        self, tool: ToolDefinition, arguments: dict
    ) -> bool:
        """Check if tool operation is potentially destructive"""

        destructive_patterns = [
            ("write_file", lambda args: True),
            ("delete_file", lambda args: True),
            (
                "run_command",
                lambda args: self._is_dangerous_command(args.get("command", "")),
            ),
            (
                "modify_database",
                lambda args: "DELETE" in args.get("query", "").upper()
                or "DROP" in args.get("query", "").upper(),
            ),
            ("create_task", lambda args: False),  # Task creation is generally safe
        ]

        for pattern_name, checker in destructive_patterns:
            if pattern_name in tool.name.lower():
                try:
                    return checker(arguments)
                except Exception:
                    # If we can't determine, err on the side of caution
                    return True

        return False

    def _is_dangerous_command(self, command: str) -> bool:
        """Check if a command is potentially dangerous"""

        dangerous_commands = [
            "rm",
            "del",
            "delete",
            "format",
            "shutdown",
            "reboot",
            "sudo",
            "chmod",
            "chown",
            "fdisk",
            "mkfs",
            "dd",
        ]

        command_lower = command.lower()
        return any(
            dangerous_cmd in command_lower for dangerous_cmd in dangerous_commands
        )

    def _create_permission_key(self, tool_name: str, arguments: dict) -> str:
        """Create a unique key for this permission request"""

        # Create a hash of tool name + arguments for uniqueness
        arg_str = str(sorted(arguments.items()))
        key_data = f"{tool_name}:{arg_str}"
        return hashlib.md5(key_data.encode()).hexdigest()[:12]

    def _format_arguments(self, arguments: dict) -> str:
        """Format arguments for display to user"""

        if not arguments:
            return "(no arguments)"

        # Truncate long arguments for readability
        formatted = {}
        for key, value in arguments.items():
            if isinstance(value, str) and len(value) > 50:
                formatted[key] = value[:47] + "..."
            else:
                formatted[key] = value

        return str(formatted)

    def is_tool_available(
        self, tool: ToolDefinition, context: ExecutionContext = None
    ) -> bool:
        """Check if a tool is available for the current context"""

        # Disabled tools are not available
        if not tool.enabled:
            return False

        # Dangerous tools are only available if explicitly granted
        if tool.permission_level == PermissionLevel.DANGEROUS:
            return tool.name in self.user_permissions.get(
                PermissionLevel.DANGEROUS, set()
            )

        # In deny mode, elevated and system tools are not available unless explicitly granted
        if self.permission_mode == "deny":
            if tool.permission_level == PermissionLevel.ELEVATED:
                return tool.name in self.user_permissions.get(
                    PermissionLevel.ELEVATED, set()
                )
            if tool.permission_level == PermissionLevel.SYSTEM:
                return tool.name in self.user_permissions.get(
                    PermissionLevel.SYSTEM, set()
                )

        # All other tools are available (permission will be checked at execution time)
        return True

    def grant_permission(
        self, tool_name: str, permission_level: PermissionLevel
    ) -> None:
        """Programmatically grant permission for a tool"""

        if permission_level not in self.user_permissions:
            self.user_permissions[permission_level] = set()

        self.user_permissions[permission_level].add(tool_name)

    def revoke_permission(
        self, tool_name: str, permission_level: PermissionLevel
    ) -> None:
        """Revoke permission for a tool"""

        if permission_level in self.user_permissions:
            self.user_permissions[permission_level].discard(tool_name)

        # Also remove from session and permanent grants
        permission_keys_to_remove = [
            key for key in self.session_grants if tool_name in key
        ]
        for key in permission_keys_to_remove:
            self.session_grants.discard(key)

        self.permanent_grants.discard(tool_name)

    def clear_session_grants(self) -> None:
        """Clear all session-based permission grants"""
        self.session_grants.clear()

    def get_granted_tools(self) -> dict[str, list[str]]:
        """Get all tools that have been granted permissions"""

        return {
            level.value: list(tools)
            for level, tools in self.user_permissions.items()
            if tools
        }
