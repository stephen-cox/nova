"""Core chat session management"""

import uuid
from datetime import datetime
from pathlib import Path

from nova.core.ai_client import AIError, generate_sync_response
from nova.core.config import config_manager
from nova.core.history import HistoryManager
from nova.core.memory import MemoryManager
from nova.core.search import SearchError, search_web
from nova.models.config import NovaConfig
from nova.models.message import Conversation, MessageRole
from nova.utils.formatting import (
    print_error,
    print_info,
    print_message,
    print_search_results,
    print_success,
)


class ChatSession:
    """Manages a single chat conversation"""

    def __init__(self, config: NovaConfig, conversation_id: str | None = None):
        self.config = config
        self.history_manager = HistoryManager(config.chat.history_dir)
        self.memory_manager = MemoryManager(config.get_active_ai_config())

        if conversation_id:
            # Try to load existing conversation
            try:
                history_files = self.history_manager.list_conversations()
                for filepath, _, _ in history_files:
                    if conversation_id in filepath.stem:
                        self.conversation = self.history_manager.load_conversation(
                            filepath
                        )
                        break
                else:
                    raise FileNotFoundError(f"Conversation {conversation_id} not found")
            except Exception as e:
                print_error(f"Could not load conversation: {e}")
                self.conversation = self._create_new_conversation()
        else:
            self.conversation = self._create_new_conversation()

    def _create_new_conversation(self) -> Conversation:
        """Create a new conversation"""
        return Conversation(
            id=str(uuid.uuid4())[:8], title=None, created_at=datetime.now()
        )

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation"""
        self.conversation.add_message(MessageRole.USER, content)

        # Auto-save if enabled
        if self.config.chat.auto_save:
            self.save_conversation()

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the conversation"""
        self.conversation.add_message(MessageRole.ASSISTANT, content)

        # Auto-save if enabled
        if self.config.chat.auto_save:
            self.save_conversation()

    def add_system_message(self, content: str) -> None:
        """Add a system message to the conversation"""
        self.conversation.add_message(MessageRole.SYSTEM, content)

    def save_conversation(self, filepath: Path | None = None) -> Path | None:
        """Save the conversation to disk (only if it has messages)"""
        if not self.conversation.messages:
            # Don't save empty conversations
            return None
        saved_path = self.history_manager.save_conversation(self.conversation, filepath)
        return saved_path

    def get_context_messages(self) -> list:
        """Get optimized context messages for AI using memory management"""
        # Use memory manager for intelligent context optimization
        context_data = self.memory_manager.optimize_conversation_context(
            self.conversation
        )
        return context_data["messages"]

    def print_conversation_history(self) -> None:
        """Print the conversation history"""
        print_info(f"Conversation: {self.conversation.id}")
        if self.conversation.title:
            print_info(f"Title: {self.conversation.title}")

        print_info(f"Messages: {len(self.conversation.messages)}")
        print()

        for msg in self.conversation.messages:
            timestamp = msg.timestamp.strftime("%H:%M:%S")
            print_message(msg.role.value, msg.content, timestamp)


class ChatManager:
    """Manages chat sessions and history"""

    def __init__(
        self, config_path: Path | None = None, profile_override: str | None = None
    ):
        try:
            self.config = config_manager.load_config(config_path)
        except Exception as e:
            print_error(f"Configuration error: {e}")
            print_info("Using default configuration")
            self.config = config_manager._load_default_config()

        # Apply profile override if specified
        if profile_override:
            if profile_override in self.config.profiles:
                self.config.active_profile = profile_override
                print_info(f"Using profile: {profile_override}")
            else:
                print_error(f"Profile '{profile_override}' not found")
                print_info("Available profiles:")
                for name in self.config.profiles.keys():
                    print_info(f"  - {name}")
                raise ValueError(f"Profile '{profile_override}' not found")

        self.history_manager = HistoryManager(self.config.chat.history_dir)
        self.memory_manager = MemoryManager(self.config.get_active_ai_config())

    def start_interactive_chat(self, session_name: str | None = None) -> None:
        """Start an interactive chat session"""

        print_success("Nova AI Research Assistant")

        # Show active AI configuration
        active_config = self.config.get_active_ai_config()
        if self.config.active_profile:
            print_info(
                f"Active profile: {self.config.active_profile} ({active_config.provider}/{active_config.model_name})"
            )
        else:
            print_info(
                f"Using direct config: {active_config.provider}/{active_config.model_name}"
            )

        print_info("Type '/exit', '/quit', or press Ctrl+C to end the session")
        print_info("Type '/help' for available commands")
        print()

        # Create or load session
        session = ChatSession(self.config, session_name)

        if session_name:
            print_info(f"Loaded session: {session_name}")
            session.print_conversation_history()
        else:
            print_info(f"Started new session: {session.conversation.id}")

        print()

        try:
            while True:
                # Get user input
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nGoodbye!")
                    break

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    # Handle /exit and /quit commands
                    if user_input.lower() in ["/exit", "/quit"]:
                        print("Goodbye!")
                        break
                    self._handle_command(user_input, session)
                    continue

                # Add user message
                session.add_user_message(user_input)

                # Generate AI response
                try:
                    print_info("Thinking...")
                    assistant_response = self._generate_ai_response(session)
                    session.add_assistant_message(assistant_response)

                    # Display response
                    print_message("assistant", assistant_response)
                    print()

                    # Check if conversation should be summarized
                    if self.memory_manager.should_summarize_conversation(
                        session.conversation
                    ):
                        print_info(
                            "💡 Tip: This conversation is getting long. Consider using '/summarize' to create a summary for better memory management."
                        )

                except AIError as e:
                    print_error(f"AI Error: {e}")
                    # Remove the user message since we couldn't process it
                    if session.conversation.messages:
                        session.conversation.messages.pop()
                except Exception as e:
                    print_error(f"Unexpected error: {e}")
                    if session.conversation.messages:
                        session.conversation.messages.pop()

        except Exception as e:
            print_error(f"Chat session error: {e}")

        finally:
            # Save conversation (only if it has messages)
            try:
                saved_path = session.save_conversation()
                if saved_path:
                    print_success(f"Conversation saved to: {saved_path}")
            except Exception as e:
                print_error(f"Could not save conversation: {e}")

    def _handle_command(self, command: str, session: ChatSession) -> None:
        """Handle special commands during chat"""

        cmd = command.lower().strip()

        if cmd == "/help":
            print_info("Available commands:")
            print("  /help     - Show this help")
            print("  /history  - Show conversation history")
            print("  /save     - Save conversation")
            print("  /clear    - Clear conversation history")
            print("  /title <title> - Set conversation title")
            print("  /summarize - Create conversation summary")
            print("  /stats    - Show memory and conversation statistics")
            print("  /tag <tag> - Add tag to conversation")
            print("  /tags     - Show conversation tags")
            print("  /search <query> - Search the web")
            print(
                "  /search <query> --provider <provider> - Search with specific provider"
            )
            print("  /search <query> --max <number> - Limit number of results")
            print("  /exit, /quit - End session")

        elif cmd == "/history":
            session.print_conversation_history()

        elif cmd == "/save":
            try:
                saved_path = session.save_conversation()
                if saved_path:
                    print_success(f"Saved to: {saved_path}")
                else:
                    print_info("No messages to save - conversation is empty")
            except Exception as e:
                print_error(f"Save failed: {e}")

        elif cmd == "/clear":
            session.conversation.messages = []
            print_success("Conversation history cleared")

        elif cmd.startswith("/title "):
            title = command[7:].strip()
            session.conversation.title = title
            print_success(f"Title set to: {title}")

        elif cmd == "/summarize":
            try:
                if len(session.conversation.messages) < 3:
                    print_error("Need at least 3 messages to create a summary")
                    return

                print_info("Creating conversation summary...")
                summary = self.memory_manager.create_conversation_summary(
                    session.conversation
                )
                print_success("Summary created:")
                print(f"  Topics: {', '.join(summary.key_topics)}")
                print(f"  Summary: {summary.summary_text}")

            except Exception as e:
                print_error(f"Failed to create summary: {e}")

        elif cmd == "/stats":
            try:
                stats = self.memory_manager.get_memory_stats(session.conversation)
                print_info("Conversation Statistics:")
                print(f"  Messages: {stats['message_count']}")
                print(f"  Duration: {stats['duration']}")
                print(f"  Summaries: {stats['summaries_count']}")
                print(
                    f"  High importance messages: {stats['high_importance_messages']}"
                )
                print(f"  Recent activity (24h): {stats['recent_activity_24h']}")
                print(f"  Context efficiency: {stats['context_efficiency']:.2%}")
                print(
                    f"  Estimated context tokens: {stats['estimated_context_tokens']}"
                )
                print(
                    f"  Tags: {', '.join(stats['tags']) if stats['tags'] else 'None'}"
                )
                if stats["needs_summarization"]:
                    print_info(
                        "  💡 This conversation could benefit from summarization (/summarize)"
                    )
                if stats["suggested_tags"]:
                    print_info(
                        f"  💡 Suggested tags: {', '.join(stats['suggested_tags'])}"
                    )

            except Exception as e:
                print_error(f"Failed to get stats: {e}")

        elif cmd.startswith("/tag "):
            tag = command[5:].strip()
            if tag:
                session.conversation.add_tag(tag)
                print_success(f"Added tag: {tag}")
            else:
                print_error("Please specify a tag name")

        elif cmd == "/tags":
            if session.conversation.tags:
                print_info(f"Tags: {', '.join(session.conversation.tags)}")
            else:
                print_info("No tags set for this conversation")

            # Show suggested tags
            suggested = self.memory_manager.suggest_conversation_tags(
                session.conversation
            )
            if suggested:
                print_info(f"Suggested tags: {', '.join(suggested)}")

        elif cmd.startswith("/search "):
            self._handle_search_command(command[8:].strip())

        else:
            print_error(f"Unknown command: {command}")
            print_info("Type '/help' for available commands")

    def _handle_search_command(self, search_args: str) -> None:
        """Handle web search command"""
        if not search_args:
            print_error("Please provide a search query")
            print_info(
                "Usage: /search <query> [--provider <provider>] [--max <number>]"
            )
            return

        # Check if search is enabled
        if not self.config.search.enabled:
            print_error("Web search is disabled in configuration")
            return

        # Parse search arguments
        parts = search_args.split()
        query_parts = []
        provider = None
        max_results = self.config.search.max_results

        i = 0
        while i < len(parts):
            if parts[i] == "--provider" and i + 1 < len(parts):
                provider = parts[i + 1]
                i += 2
            elif parts[i] == "--max" and i + 1 < len(parts):
                try:
                    max_results = min(int(parts[i + 1]), 50)  # Cap at 50 results
                except ValueError:
                    print_error("Invalid number for --max parameter")
                    return
                i += 2
            else:
                query_parts.append(parts[i])
                i += 1

        if not query_parts:
            print_error("Please provide a search query")
            return

        query = " ".join(query_parts)

        # Use configured provider if none specified
        if not provider:
            provider = self.config.search.default_provider

        try:
            print_info(f"Searching for: {query}")
            if provider != self.config.search.default_provider:
                print_info(f"Using provider: {provider}")

            # Convert config to dict for search_web function
            search_config = {
                "search": {
                    "google": dict(self.config.search.google),
                    "bing": dict(self.config.search.bing),
                }
            }

            # Perform the search
            search_response = search_web(
                config=search_config,
                query=query,
                provider=provider,
                max_results=max_results,
            )

            # Display the results
            print_search_results(search_response)

        except SearchError as e:
            print_error(f"Search failed: {e}")
            print_info("Try using a different provider with --provider <provider>")
        except Exception as e:
            print_error(f"Unexpected search error: {e}")

    def _generate_ai_response(self, session: ChatSession) -> str:
        """Generate AI response using configured provider"""

        # Get optimized conversation context using memory management
        context_messages = session.get_context_messages()

        # Add system message if needed
        messages = []

        # Get active AI config
        active_config = self.config.get_active_ai_config()

        # Add a system message to set context
        if active_config.provider in ["openai", "ollama"]:
            system_message = "You are Nova, a helpful AI research assistant. Provide clear, accurate, and helpful responses."

            # Add conversation context info if we have summaries
            if session.conversation.summaries:
                system_message += (
                    " You have access to conversation summaries to maintain context."
                )

            # Add tag context if available
            if session.conversation.tags:
                system_message += f" This conversation is tagged with: {', '.join(session.conversation.tags)}."

            messages.append({"role": "system", "content": system_message})

        # Add conversation history (already optimized by memory manager)
        messages.extend(context_messages)

        # Generate response using AI client
        try:
            response = generate_sync_response(config=active_config, messages=messages)
            return (
                response.strip()
                if response
                else "I apologize, but I didn't generate a response. Please try again."
            )

        except Exception as e:
            raise AIError(f"Failed to generate response: {e}")

    def list_conversations(self) -> None:
        """List all saved conversations"""
        conversations = self.history_manager.list_conversations()

        if not conversations:
            print_info("No saved conversations found")
            return

        print_info(f"Found {len(conversations)} conversations:")
        print()

        for filepath, title, timestamp in conversations:
            session_id = (
                filepath.stem.split("_", 2)[-1]
                if "_" in filepath.stem
                else filepath.stem
            )
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M")
            print(f"  {session_id:<12} {timestamp_str:<16} {title}")

        print()
        print_info("Use 'nova chat start <session_id>' to continue a conversation")

    def resume_last_conversation(self) -> None:
        """Resume the most recently saved conversation"""
        # Find the most recent conversation
        recent_conversation = self.history_manager.get_most_recent_conversation()

        if not recent_conversation:
            print_error("No saved conversations found to resume")
            print_info("Start a new chat with 'nova chat start'")
            return

        filepath, title, timestamp = recent_conversation

        # Extract session ID from filename for consistency with existing logic
        session_id = (
            filepath.stem.split("_", 2)[-1] if "_" in filepath.stem else filepath.stem
        )

        print_success("Resuming most recent conversation")
        print_info(f"Session: {session_id}")
        print_info(f"Title: {title}")
        print_info(f"Last updated: {timestamp.strftime('%Y-%m-%d %H:%M')}")
        print()

        # Start the interactive chat with the found session
        self.start_interactive_chat(session_id)
