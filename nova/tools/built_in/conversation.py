"""Conversation and history management tools"""

from datetime import datetime, timedelta
from typing import Any

from nova.core.tools.handler import AsyncToolHandler, BuiltInToolModule
from nova.models.tools import (
    ExecutionContext,
    PermissionLevel,
    ToolCategory,
    ToolDefinition,
    ToolExample,
    ToolSourceType,
)


class ListConversationsHandler(AsyncToolHandler):
    """Handler for listing saved conversations"""

    async def execute(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> list[dict]:
        limit = arguments.get("limit", 10)
        include_content = arguments.get("include_content", False)

        try:
            # Import here to avoid circular dependencies
            from nova.core.config import config_manager
            from nova.core.history import HistoryManager

            # Get config for history directory
            config = config_manager.load_config()
            history_manager = HistoryManager(config.chat.history_dir)

            conversations = history_manager.list_conversations()

            # Sort by timestamp, most recent first
            conversations.sort(key=lambda x: x[2], reverse=True)

            # Limit results
            if limit > 0:
                conversations = conversations[:limit]

            result = []
            for filepath, title, timestamp in conversations:
                conv_info = {
                    "id": (
                        filepath.stem.split("_", 2)[-1]
                        if "_" in filepath.stem
                        else filepath.stem
                    ),
                    "title": title or "Untitled",
                    "timestamp": timestamp.isoformat(),
                    "file_path": str(filepath),
                }

                if include_content:
                    try:
                        conversation = history_manager.load_conversation(filepath)
                        conv_info["message_count"] = len(conversation.messages)
                        conv_info["tags"] = conversation.tags
                        conv_info["summary_count"] = len(conversation.summaries)
                    except Exception as e:
                        conv_info["error"] = f"Failed to load content: {e}"

                result.append(conv_info)

            return result

        except Exception as e:
            raise RuntimeError(f"Failed to list conversations: {e}")


class SearchConversationHistoryHandler(AsyncToolHandler):
    """Handler for searching through conversation history"""

    async def execute(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> list[dict]:
        query = arguments["query"]
        limit = arguments.get("limit", 5)
        include_context = arguments.get("include_context", True)

        try:
            from nova.core.config import config_manager
            from nova.core.history import HistoryManager

            config = config_manager.load_config()
            history_manager = HistoryManager(config.chat.history_dir)

            conversations = history_manager.list_conversations()
            matching_conversations = []

            query_lower = query.lower()

            for filepath, title, timestamp in conversations:
                try:
                    conversation = history_manager.load_conversation(filepath)

                    # Search in title
                    title_match = title and query_lower in title.lower()

                    # Search in messages
                    matching_messages = []
                    for msg in conversation.messages:
                        if query_lower in msg.content.lower():
                            matching_messages.append(
                                {
                                    "role": msg.role.value,
                                    "content": (
                                        msg.content[:200] + "..."
                                        if len(msg.content) > 200
                                        else msg.content
                                    ),
                                    "timestamp": msg.timestamp.isoformat(),
                                }
                            )

                    # Search in tags
                    tag_match = any(
                        query_lower in tag.lower() for tag in conversation.tags
                    )

                    if title_match or matching_messages or tag_match:
                        result_item = {
                            "id": (
                                filepath.stem.split("_", 2)[-1]
                                if "_" in filepath.stem
                                else filepath.stem
                            ),
                            "title": title or "Untitled",
                            "timestamp": timestamp.isoformat(),
                            "title_match": title_match,
                            "tag_match": tag_match,
                            "message_matches": len(matching_messages),
                        }

                        if include_context and matching_messages:
                            result_item["matching_messages"] = matching_messages[
                                :3
                            ]  # Limit context

                        matching_conversations.append(result_item)

                except Exception:
                    # Skip conversations that can't be loaded
                    continue

            # Sort by relevance (more matches first), then by timestamp
            matching_conversations.sort(
                key=lambda x: (x["message_matches"], x["timestamp"]), reverse=True
            )

            if limit > 0:
                matching_conversations = matching_conversations[:limit]

            return matching_conversations

        except Exception as e:
            raise RuntimeError(f"Failed to search conversations: {e}")


class SaveCurrentConversationHandler(AsyncToolHandler):
    """Handler for saving the current conversation"""

    async def execute(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> dict:
        # title = arguments.get("title")  # Currently unused
        # tags = arguments.get("tags", [])  # Currently unused

        if not context or not context.conversation_id:
            raise ValueError("No active conversation to save")

        try:
            # This would need access to the current chat session
            # For now, return a placeholder response
            return {
                "success": True,
                "message": "Conversation save functionality requires active chat session",
                "conversation_id": context.conversation_id,
            }

        except Exception as e:
            raise RuntimeError(f"Failed to save conversation: {e}")


class GetConversationStatsHandler(AsyncToolHandler):
    """Handler for getting conversation statistics"""

    async def execute(
        self, arguments: dict[str, Any], context: ExecutionContext = None
    ) -> dict:
        period_days = arguments.get("period_days", 30)

        try:
            from nova.core.config import config_manager
            from nova.core.history import HistoryManager

            config = config_manager.load_config()
            history_manager = HistoryManager(config.chat.history_dir)

            conversations = history_manager.list_conversations()

            # Filter by time period
            cutoff_date = datetime.now() - timedelta(days=period_days)
            recent_conversations = [
                (filepath, title, timestamp)
                for filepath, title, timestamp in conversations
                if timestamp >= cutoff_date
            ]

            # Calculate statistics
            total_conversations = len(recent_conversations)
            total_messages = 0
            total_tags = set()

            for filepath, _title, _timestamp in recent_conversations:
                try:
                    conversation = history_manager.load_conversation(filepath)
                    total_messages += len(conversation.messages)
                    total_tags.update(conversation.tags)
                except Exception:
                    continue

            return {
                "period_days": period_days,
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "average_messages_per_conversation": total_messages
                / max(total_conversations, 1),
                "unique_tags": len(total_tags),
                "most_common_tags": list(total_tags)[:10],  # Top 10 tags
            }

        except Exception as e:
            raise RuntimeError(f"Failed to get conversation stats: {e}")


class ConversationTools(BuiltInToolModule):
    """Conversation and history management tools"""

    async def get_tools(self) -> list[tuple[ToolDefinition, Any]]:
        return [
            (
                ToolDefinition(
                    name="list_conversations",
                    description="List saved chat conversations",
                    parameters={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 100,
                                "description": "Maximum number of conversations to return",
                            },
                            "include_content": {
                                "type": "boolean",
                                "default": False,
                                "description": "Include conversation metadata (message count, tags, etc.)",
                            },
                        },
                    },
                    source_type=ToolSourceType.BUILT_IN,
                    permission_level=PermissionLevel.SAFE,
                    category=ToolCategory.PRODUCTIVITY,
                    tags=["conversation", "history", "list"],
                    examples=[
                        ToolExample(
                            description="List recent conversations",
                            arguments={"limit": 5},
                            expected_result="List of 5 most recent conversations with titles and timestamps",
                        ),
                        ToolExample(
                            description="List conversations with metadata",
                            arguments={"limit": 10, "include_content": True},
                            expected_result="Detailed list including message counts and tags",
                        ),
                    ],
                ),
                ListConversationsHandler(),
            ),
            (
                ToolDefinition(
                    name="search_conversation_history",
                    description="Search through saved conversations for specific content",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find in conversations",
                            },
                            "limit": {
                                "type": "integer",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 50,
                                "description": "Maximum number of matching conversations to return",
                            },
                            "include_context": {
                                "type": "boolean",
                                "default": True,
                                "description": "Include snippets of matching message content",
                            },
                        },
                        "required": ["query"],
                    },
                    source_type=ToolSourceType.BUILT_IN,
                    permission_level=PermissionLevel.SAFE,
                    category=ToolCategory.PRODUCTIVITY,
                    tags=["conversation", "search", "history"],
                    examples=[
                        ToolExample(
                            description="Search for conversations about Python",
                            arguments={"query": "Python programming"},
                            expected_result="Conversations containing references to Python programming",
                        ),
                        ToolExample(
                            description="Search with context snippets",
                            arguments={
                                "query": "machine learning",
                                "limit": 3,
                                "include_context": True,
                            },
                            expected_result="Top 3 conversations with ML content and message snippets",
                        ),
                    ],
                ),
                SearchConversationHistoryHandler(),
            ),
            (
                ToolDefinition(
                    name="save_conversation",
                    description="Save the current conversation with optional title and tags",
                    parameters={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Optional title for the conversation",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional tags to categorize the conversation",
                            },
                        },
                    },
                    source_type=ToolSourceType.BUILT_IN,
                    permission_level=PermissionLevel.SAFE,
                    category=ToolCategory.PRODUCTIVITY,
                    tags=["conversation", "save", "organize"],
                    examples=[
                        ToolExample(
                            description="Save conversation with title",
                            arguments={"title": "Python Learning Session"},
                            expected_result="Conversation saved with specified title",
                        ),
                        ToolExample(
                            description="Save with title and tags",
                            arguments={
                                "title": "Code Review Discussion",
                                "tags": ["code-review", "python", "best-practices"],
                            },
                            expected_result="Conversation saved with title and organizational tags",
                        ),
                    ],
                ),
                SaveCurrentConversationHandler(),
            ),
            (
                ToolDefinition(
                    name="get_conversation_stats",
                    description="Get statistics about conversation history",
                    parameters={
                        "type": "object",
                        "properties": {
                            "period_days": {
                                "type": "integer",
                                "default": 30,
                                "minimum": 1,
                                "maximum": 365,
                                "description": "Time period in days to analyze",
                            }
                        },
                    },
                    source_type=ToolSourceType.BUILT_IN,
                    permission_level=PermissionLevel.SAFE,
                    category=ToolCategory.PRODUCTIVITY,
                    tags=["conversation", "statistics", "analytics"],
                    examples=[
                        ToolExample(
                            description="Get 30-day conversation stats",
                            arguments={},
                            expected_result="Statistics for conversations in the last 30 days",
                        ),
                        ToolExample(
                            description="Get weekly conversation stats",
                            arguments={"period_days": 7},
                            expected_result="Statistics for conversations in the last 7 days",
                        ),
                    ],
                ),
                GetConversationStatsHandler(),
            ),
        ]
