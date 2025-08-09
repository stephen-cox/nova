"""Core chat session management"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from nova.core.ai_client import AIError, create_ai_client, generate_sync_response
from nova.core.config import config_manager
from nova.core.history import HistoryManager
from nova.core.input_handler import ChatInputHandler
from nova.core.memory import MemoryManager
from nova.core.prompts import PromptManager
from nova.core.search import SearchError, search_web
from nova.core.tools import FunctionRegistry
from nova.models.config import NovaConfig
from nova.models.message import Conversation, MessageRole
from nova.models.tools import ExecutionContext
from nova.utils.formatting import (
    print_error,
    print_info,
    print_message,
    print_search_results,
    print_success,
    print_warning,
)

logger = logging.getLogger(__name__)


class ChatSession:
    """Manages a single chat conversation"""

    def __init__(self, config: NovaConfig, conversation_id: str | None = None):
        self.config = config
        self.history_manager = HistoryManager(config.chat.history_dir)
        self.memory_manager = MemoryManager(config.get_active_ai_config())

        # Initialize function registry if tools are enabled
        self.function_registry = None
        if (
            getattr(config, "tools", None)
            and config.get_effective_tools_config().enabled
        ):
            self.function_registry = FunctionRegistry(config)
            # Initialize asynchronously - we'll handle this in the chat manager

        # Create AI client with function registry
        self.ai_client = create_ai_client(
            config.get_active_ai_config(), self.function_registry
        )

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
            print_message(msg.role.value, msg.content)


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
        self.prompt_manager = (
            PromptManager(self.config.prompts) if self.config.prompts.enabled else None
        )
        self.input_handler = ChatInputHandler()

    async def _initialize_session_tools(self, session: ChatSession) -> None:
        """Initialize tools for a chat session"""
        if session.function_registry:
            try:
                await session.function_registry.initialize()
                tool_count = len(session.function_registry.list_tool_names())
                if tool_count > 0:
                    print_info(f"🔧 Initialized {tool_count} tools")
            except Exception as e:
                print_warning(f"Failed to initialize tools: {e}")
                session.function_registry = None

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

        print_info("Type '/q', '/quit', or press Ctrl+C to end the session")
        print_info("Type '/help' for available commands")
        print_info("Use arrow keys: ←→ to move cursor, ↑↓ to navigate message history")
        print()

        # Create or load session
        session = ChatSession(self.config, session_name)

        # Initialize tools asynchronously
        if session.function_registry:
            asyncio.run(self._initialize_session_tools(session))

        if session_name:
            print_info(f"Loaded session: {session_name}")
            session.print_conversation_history()
            # Load previous user messages into input history
            self._load_session_history_to_input(session)
        else:
            print_info(f"Started new session: {session.conversation.id}")

        print()

        try:
            while True:
                # Get user input with enhanced navigation
                user_input = self.input_handler.get_input("You: ")

                # Handle interruption (Ctrl+C or EOF)
                if user_input is None:
                    print("\nGoodbye!")
                    break

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    # Handle /q and /quit commands
                    if user_input.lower() in ["/q", "/quit"]:
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
            print("  /search, /s <query> - Search the web and get AI-powered answers")
            print(
                "  /search <query> --provider <provider> - Search with specific provider"
            )
            print("  /search <query> --max <number> - Limit number of results")
            print("  /prompt <name> - Apply a prompt template")
            print("  /prompts  - List available prompt templates")
            print("  /prompts search <query> - Search prompt templates")
            print("  /tools    - List available tools")
            print("  /tool <name> [args] - Execute a specific tool")
            print("  /tool info <name> - Get information about a tool")
            print("  /permissions - Manage tool permissions")
            print("  /q, /quit - End session")

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
            self.input_handler.clear_history()
            print_success("Conversation history and input history cleared")

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
            self._handle_search_command(command[8:].strip(), session)

        elif cmd.startswith("/s "):
            self._handle_search_command(command[3:].strip(), session)

        elif cmd.startswith("/prompt "):
            self._handle_prompt_command(command[8:].strip(), session)

        elif cmd == "/prompts":
            self._handle_prompts_list_command(session)

        elif cmd.startswith("/prompts "):
            self._handle_prompts_search_command(command[9:].strip(), session)

        elif cmd == "/tools":
            self._handle_tools_list_command(session)

        elif cmd.startswith("/tool "):
            self._handle_tool_command(command[6:].strip(), session)

        elif cmd == "/permissions":
            self._handle_permissions_command(session)

        else:
            print_error(f"Unknown command: {command}")
            print_info("Type '/help' for available commands")

    def _handle_search_command(self, search_args: str, session: ChatSession) -> None:
        """Handle web search command and generate AI response"""
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

            # Get AI client for content summarization if available
            ai_client = None
            if self.config.search.use_ai_answers:
                try:
                    from nova.core.ai_client import create_ai_client

                    active_config = self.config.get_active_ai_config()
                    ai_client = create_ai_client(active_config)
                except Exception as e:
                    print_warning(f"AI client unavailable for summarization: {e}")

            # Perform the search with content extraction if AI answers are enabled
            search_response = search_web(
                config=search_config,
                query=query,
                provider=provider,
                max_results=max_results,
                extract_content=self.config.search.use_ai_answers,  # Extract content only if AI answers are enabled
                ai_client=ai_client,
            )

            # Check if AI answers are enabled
            if self.config.search.use_ai_answers:
                # Generate comprehensive synthesis if we have enhanced results
                if any(
                    hasattr(r, "content_summary") and r.content_summary
                    for r in search_response.results
                ):
                    print_info(
                        "Generating comprehensive analysis from extracted content..."
                    )
                    ai_response = self._generate_enhanced_search_response(
                        query, search_response, session, ai_client
                    )
                else:
                    # Fallback to standard search response
                    ai_response = self._generate_search_response(
                        query, search_response, session
                    )

                # Print the AI response
                print_message("Nova", ai_response)

                # Add search query and AI response to session
                session.add_user_message(f"/search {query}")
                session.add_assistant_message(ai_response)
            else:
                # Display raw search results
                print_search_results(search_response)

        except SearchError as e:
            print_error(f"Search failed: {e}")
            print_info("Try using a different provider with --provider <provider>")
        except Exception as e:
            print_error(f"Unexpected search error: {e}")

    def _generate_ai_response(self, session: ChatSession) -> str:
        """Generate AI response using configured provider with tool support"""

        # Get optimized conversation context using memory management
        context_messages = session.get_context_messages()

        # Create execution context for tools
        execution_context = ExecutionContext(
            conversation_id=str(session.conversation.id),
            working_directory=os.getcwd(),
            session_data={},
        )

        # Add system message if needed
        messages = []
        active_config = self.config.get_active_ai_config()

        # Get available tools if function registry is enabled
        available_tools = None
        if session.function_registry:
            try:
                available_tools = session.function_registry.get_openai_tools_schema(
                    execution_context
                )
            except Exception as e:
                logger.warning(f"Failed to get tools schema: {e}")

        # Add a system message to set context
        if active_config.provider in ["openai", "ollama"]:
            system_message = self._build_system_prompt(session)

            # Add tool information to system message
            if available_tools:
                system_message += f"\n\nYou have access to {len(available_tools)} tools that you can use to help the user. Use them when appropriate to provide better assistance."

            if system_message:
                messages.append({"role": "system", "content": system_message})

        # Add conversation history (already optimized by memory manager)
        messages.extend(context_messages)

        # Generate response using AI client with tool support
        try:
            if available_tools and hasattr(
                session.ai_client, "generate_response_with_tools"
            ):
                # Use the async tool-aware method
                try:
                    response_coro = session.ai_client.generate_response_with_tools(
                        messages=messages,
                        available_tools=available_tools,
                        context=execution_context,
                    )

                    # Check if it's actually a coroutine (for test compatibility)
                    if hasattr(response_coro, "__await__"):
                        tool_response = asyncio.run(response_coro)
                    else:
                        # Handle mock objects in tests
                        tool_response = response_coro

                    # Format the response with tool information if tools were used
                    return self._format_tool_aware_response(tool_response)
                except Exception as e:
                    logger.warning(
                        f"Tool-aware response failed: {e}, falling back to regular response"
                    )
                    # Fall through to regular response

            # Fallback to regular response
            response = generate_sync_response(config=active_config, messages=messages)
            return (
                response.strip()
                if response
                else "I apologize, but I didn't generate a response. Please try again."
            )

        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            raise AIError(f"Failed to generate response: {e}")

    def _format_tool_aware_response(self, tool_response) -> str:
        """Format response that may include tool usage"""

        response_parts = [tool_response.content]

        # Add subtle indicators for tool usage (don't overwhelm the user)
        successful_tools = [r for r in tool_response.tool_results if r.success]
        if successful_tools and len(successful_tools) > 1:
            # Only mention tools if multiple were used
            response_parts.append(
                f"\n*Used {len(successful_tools)} tools to help with this response*"
            )

        # Show failed tools as warnings
        failed_tools = [r for r in tool_response.tool_results if not r.success]
        if failed_tools:
            response_parts.append(
                f"\n*Note: {len(failed_tools)} tool(s) failed to execute*"
            )
            for failed_tool in failed_tools:
                if failed_tool.error:
                    response_parts.append(
                        f"  - {failed_tool.tool_name}: {failed_tool.error}"
                    )

        return "\n".join(response_parts)

    def _generate_search_response(
        self, query: str, search_response, session: ChatSession = None
    ) -> str:
        """Generate AI response using search results as context"""

        # Get active AI config
        active_config = self.config.get_active_ai_config()

        # Format search results for AI context
        search_context = self._format_search_results_for_ai(search_response)

        # Create messages for AI
        messages = []

        # Add system message with search context
        if active_config.provider in ["openai", "ollama"]:
            # Get list of sources for citation
            sources_list = self._extract_sources_from_results(search_response)

            system_message = f"""You are Nova, a helpful AI research assistant. The user has asked a question that required web search. Use the following search results to provide a comprehensive, accurate answer to their query.

Search Query: {query}

Search Results:
{search_context}

Sources Consulted:
{sources_list}

Instructions:
- Look for results with title "Instant Answer" - these contain direct answers to the query
- If there's an instant answer, present that information prominently and clearly
- For direct factual queries (like IP addresses, definitions), present the answer directly
- Cite specific sources when referencing information
- Be conversational and helpful while being accurate
- Synthesize information from multiple sources when appropriate
- IMPORTANT: Always end your response with a "Sources:" section
- Copy ALL the markdown-formatted links from the "Sources Consulted" section above
- Each source should be formatted as: - [Page Title](full-url)
- Include all sources provided, do not summarize or omit any"""

            messages.append({"role": "system", "content": system_message})

        # Add conversation context if we have a session
        if session:
            context_messages = session.get_context_messages()
            messages.extend(context_messages)

        # Add the user's search query
        messages.append({"role": "user", "content": query})

        # Generate response using AI client
        try:
            response = generate_sync_response(config=active_config, messages=messages)
            return (
                response.strip()
                if response
                else "I apologize, but I couldn't generate a response using the search results. Please try again."
            )
        except Exception as e:
            raise AIError(f"Failed to generate search response: {e}")

    def _format_search_results_for_ai(self, search_response) -> str:
        """Format search results for AI context, using enhanced content when available"""
        if not search_response.results:
            return "No search results found."

        formatted_results = []
        for i, result in enumerate(
            search_response.results[:5], 1
        ):  # Limit to top 5 results
            # Use content summary if available, otherwise fall back to snippet
            content = result.content_summary or result.snippet

            # Add extraction status info if content extraction was attempted
            extraction_info = ""
            if hasattr(result, "extraction_success"):
                if result.extraction_success and result.content_summary:
                    extraction_info = " (Enhanced with full content summary)"
                elif not result.extraction_success:
                    extraction_info = " (Content extraction failed, using snippet)"

            formatted_result = f"""Result {i}:
Title: {result.title}
URL: {result.url}
Source: {result.source}{extraction_info}
Content: {content}
"""
            formatted_results.append(formatted_result)

        return "\n".join(formatted_results)

    def _extract_sources_from_results(self, search_response) -> str:
        """Extract and format sources as markdown links with page titles"""
        if not search_response.results:
            return "No sources found."

        sources = []
        seen_urls = set()  # Avoid duplicate URLs

        for result in search_response.results[:5]:  # Limit to top 5 results
            if (
                result.url
                and result.url.startswith("http")
                and result.url not in seen_urls
            ):
                if result.title and result.title != "Instant Answer":
                    # Use page title as the link text
                    source_entry = f"- [{result.title}]({result.url})"
                else:
                    # Fallback to domain name if no title
                    domain = (
                        result.source
                        if result.source != "Unknown source"
                        else result.url
                    )
                    source_entry = f"- [{domain}]({result.url})"

                sources.append(source_entry)
                seen_urls.add(result.url)
            elif (
                result.source
                and result.source != "Unknown source"
                and "duckduckgo" in result.source.lower()
            ):
                # For DuckDuckGo instant answers without URLs
                source_entry = f"- {result.source} (Instant Answer)"
                sources.append(source_entry)

        return "\n".join(sources) if sources else "No sources available."

    def _generate_enhanced_search_response(
        self, query: str, search_response, session: ChatSession = None, ai_client=None
    ) -> str:
        """Generate enhanced AI response using content extraction and synthesis"""

        # Try to use advanced synthesis if we have an AI client
        if ai_client:
            try:
                from nova.core.search import ContentSummarizer

                summarizer = ContentSummarizer(ai_client)

                # Generate comprehensive synthesis - need to handle async properly
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                    synthesis = loop.run_until_complete(
                        summarizer.synthesize_results(search_response.results, query)
                    )
                except RuntimeError:
                    # No event loop exists, create a new one
                    synthesis = asyncio.run(
                        summarizer.synthesize_results(search_response.results, query)
                    )

                if synthesis and len(synthesis.strip()) > 50:
                    # Format the synthesis with sources
                    sources_list = self._extract_sources_from_results(search_response)
                    return f"{synthesis}\n\n## Sources:\n{sources_list}"

            except Exception as e:
                logger.warning(f"Enhanced synthesis failed: {e}")

        # Fallback to standard search response
        return self._generate_search_response(query, search_response, session)

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

    def _load_session_history_to_input(self, session: ChatSession) -> None:
        """Load previous user messages from session into input history"""
        for message in session.conversation.messages:
            if message.role == MessageRole.USER and not message.content.startswith("/"):
                self.input_handler.add_to_history(message.content)

    def _build_system_prompt(self, session: ChatSession) -> str:
        """Build system prompt using prompt manager or fallback to default"""

        # Get active profile
        profile = None
        if (
            self.config.active_profile
            and self.config.active_profile in self.config.profiles
        ):
            profile = self.config.profiles[self.config.active_profile]

        # Try to use prompt manager for system prompt
        if self.prompt_manager and profile and profile.system_prompt:
            # Prepare context variables
            context = {
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "current_time": datetime.now().strftime("%H:%M:%S"),
                "user_name": os.getenv("USER", "User"),
                "conversation_id": session.conversation.id,
                "active_profile": self.config.active_profile or "default",
            }

            # Merge with profile variables
            if profile.prompt_variables:
                context.update(profile.prompt_variables)

            # Get system prompt from prompt manager
            system_prompt = self.prompt_manager.get_system_prompt(
                profile.system_prompt, context
            )
            if system_prompt:
                # Add conversation context info if we have summaries
                if session.conversation.summaries:
                    system_prompt += " You have access to conversation summaries to maintain context."

                # Add tag context if available
                if session.conversation.tags:
                    system_prompt += f" This conversation is tagged with: {', '.join(session.conversation.tags)}."

                return system_prompt

        # Fallback to default system prompt
        default_prompt = "You are Nova, a helpful AI research assistant. Provide clear, accurate, and helpful responses."

        # Add conversation context info if we have summaries
        if session.conversation.summaries:
            default_prompt += (
                " You have access to conversation summaries to maintain context."
            )

        # Add tag context if available
        if session.conversation.tags:
            default_prompt += f" This conversation is tagged with: {', '.join(session.conversation.tags)}."

        return default_prompt

    def _handle_prompt_command(self, args: str, session: ChatSession) -> None:
        """Handle /prompt command for applying templates"""

        if not self.prompt_manager:
            print_error("Prompt system is disabled")
            return

        if not args:
            print_error("Please provide a prompt name")
            print_info("Usage: /prompt <name>")
            print_info("Use '/prompts' to see available prompts")
            return

        # Parse prompt name (first word)
        parts = args.split()
        prompt_name = parts[0]

        # Get the template
        template = self.prompt_manager.get_template(prompt_name)
        if not template:
            print_error(f"Prompt template '{prompt_name}' not found")
            print_info("Use '/prompts' to see available prompts")
            return

        # Show template info
        print_info(f"Applying prompt: {template.title}")
        print_info(f"Description: {template.description}")

        # Collect variables interactively
        variables = {}
        for var in template.variables:
            if var.required:
                while True:
                    value = input(f"Enter {var.description} ({var.name}): ").strip()
                    if value:
                        variables[var.name] = value
                        break
                    print_warning("This field is required")
            else:
                default_text = f" [default: {var.default}]" if var.default else ""
                value = input(
                    f"Enter {var.description} ({var.name}){default_text}: "
                ).strip()
                if value:
                    variables[var.name] = value
                elif var.default is not None:
                    variables[var.name] = var.default

        # Render the template
        rendered = self.prompt_manager.render_template(prompt_name, variables)
        if rendered:
            # Add as system message to current session
            session.add_system_message(rendered)
            print_success("Prompt applied successfully!")
            print_info("The prompt has been added to your conversation context.")
        else:
            print_error("Failed to render prompt template")

    def _handle_prompts_list_command(self, session: ChatSession) -> None:
        """Handle /prompts command for listing templates"""

        if not self.prompt_manager:
            print_error("Prompt system is disabled")
            return

        templates = self.prompt_manager.list_templates()
        if not templates:
            print_info("No prompt templates available")
            return

        print_info(f"Available prompt templates ({len(templates)} total):")
        print()

        # Group by category
        by_category = {}
        for template in templates:
            category = template.category.value
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(template)

        # Display by category
        for category, templates_in_cat in sorted(by_category.items()):
            print_success(f"{category.title()}:")
            for template in sorted(templates_in_cat, key=lambda t: t.name):
                required_vars = len(template.get_required_variables())
                optional_vars = len(template.get_optional_variables())
                var_info = (
                    f"({required_vars} required, {optional_vars} optional vars)"
                    if template.variables
                    else "(no variables)"
                )

                print(f"  {template.name:<15} - {template.title}")
                print(f"    {template.description} {var_info}")
            print()

    def _handle_prompts_search_command(self, query: str, session: ChatSession) -> None:
        """Handle /prompts search command"""

        if not self.prompt_manager:
            print_error("Prompt system is disabled")
            return

        if not query:
            print_error("Please provide a search query")
            print_info("Usage: /prompts search <query>")
            return

        results = self.prompt_manager.search_templates(query)
        if not results:
            print_warning(f"No prompts found matching: {query}")
            return

        print_info(f"Found {len(results)} prompt(s) matching '{query}':")
        print()

        for template in results:
            required_vars = len(template.get_required_variables())
            optional_vars = len(template.get_optional_variables())
            var_info = (
                f"({required_vars} required, {optional_vars} optional vars)"
                if template.variables
                else "(no variables)"
            )

            print_success(f"{template.name} - {template.title}")
            print(f"  Category: {template.category.value}")
            print(f"  Description: {template.description}")
            print(f"  Variables: {var_info}")
            if template.tags:
                print(f"  Tags: {', '.join(template.tags)}")
            print()

    def _handle_tools_list_command(self, session: ChatSession) -> None:
        """Handle /tools command for listing available tools"""

        if not session.function_registry:
            print_info("Tools system is not enabled")
            return

        try:
            # Get execution context
            execution_context = ExecutionContext(
                conversation_id=session.conversation.id, working_directory=os.getcwd()
            )

            available_tools = session.function_registry.get_available_tools(
                execution_context
            )

            if not available_tools:
                print_info("No tools are currently available")
                return

            print_info(f"Available tools ({len(available_tools)} total):")
            print()

            # Group by category
            by_category = {}
            for tool in available_tools:
                category = tool.category.value
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(tool)

            # Display by category
            for category, tools_in_cat in sorted(by_category.items()):
                print_success(f"{category.title().replace('_', ' ')}:")
                for tool in sorted(tools_in_cat, key=lambda t: t.name):
                    permission_indicator = ""
                    if tool.permission_level.value == "elevated":
                        permission_indicator = " 🔐"
                    elif tool.permission_level.value == "system":
                        permission_indicator = " 🚨"

                    print(
                        f"  {tool.name:<20} - {tool.description}{permission_indicator}"
                    )
                    if tool.tags:
                        print(f"    Tags: {', '.join(tool.tags)}")
                print()

            print_info("Use '/tool info <name>' for detailed information about a tool")
            print_info("Use '/tool <name> --help' to see usage examples")

        except Exception as e:
            print_error(f"Failed to list tools: {e}")

    def _handle_tool_command(self, args: str, session: ChatSession) -> None:
        """Handle /tool command for executing or getting info about tools"""

        if not session.function_registry:
            print_error("Tools system is not enabled")
            return

        if not args:
            print_error("Please provide a tool name")
            print_info("Usage: /tool <name> [key=value ...] or /tool info <name>")
            print_info(
                'Example: /tool web_search query="python programming" max_results=3'
            )
            return

        parts = args.split()
        if not parts:
            print_error("Please provide a tool name")
            return

        # Handle info subcommand
        if parts[0] == "info" and len(parts) > 1:
            self._show_tool_info(parts[1], session)
            return

        tool_name = parts[0]

        # Check if tool exists
        tool_info = session.function_registry.get_tool_info(tool_name)
        if not tool_info:
            print_error(f"Tool '{tool_name}' not found")
            print_info("Use '/tools' to see available tools")
            return

        # Handle help request
        if len(parts) > 1 and parts[1] == "--help":
            self._show_tool_info(tool_name, session)
            return

        # Parse arguments and execute tool
        if len(parts) > 1:
            try:
                # Parse arguments from command line
                arguments = self._parse_tool_arguments(tool_name, parts[1:], tool_info)
                if arguments is None:
                    return  # Error already reported

                # Execute the tool
                print_info(f"Executing tool: {tool_name}")
                asyncio.run(self._execute_tool_direct(tool_name, arguments, session))

            except Exception as e:
                print_error(f"Failed to parse arguments: {e}")
                self._show_tool_info(tool_name, session)
                return
        else:
            # Check if tool requires arguments
            properties = tool_info.parameters.get("properties", {})
            required = tool_info.parameters.get("required", [])

            if required or properties:
                print_error("This tool requires arguments")
                self._show_tool_info(tool_name, session)
            else:
                # Tool doesn't need arguments, execute it
                print_info(f"Executing tool: {tool_name}")
                asyncio.run(self._execute_tool_direct(tool_name, {}, session))

    def _show_tool_info(self, tool_name: str, session: ChatSession) -> None:
        """Show detailed information about a tool"""

        tool_info = session.function_registry.get_tool_info(tool_name)
        if not tool_info:
            print_error(f"Tool '{tool_name}' not found")
            return

        print_info(f"Tool: {tool_info.name}")
        print(f"  Description: {tool_info.description}")
        print(f"  Category: {tool_info.category.value}")
        print(f"  Source: {tool_info.source_type.value}")
        print(f"  Permission Level: {tool_info.permission_level.value}")

        if tool_info.tags:
            print(f"  Tags: {', '.join(tool_info.tags)}")

        # Show parameters
        if tool_info.parameters.get("properties"):
            print("  Parameters:")
            required = tool_info.parameters.get("required", [])
            for param_name, param_info in tool_info.parameters["properties"].items():
                required_marker = " (required)" if param_name in required else ""
                param_type = param_info.get("type", "unknown")
                param_desc = param_info.get("description", "No description")
                print(
                    f"    - {param_name} ({param_type}){required_marker}: {param_desc}"
                )

        # Show examples
        if tool_info.examples:
            print("  Examples:")
            for i, example in enumerate(
                tool_info.examples[:2], 1
            ):  # Show max 2 examples
                print(f"    {i}. {example.description}")
                if example.arguments:
                    print(f"       Arguments: {example.arguments}")

    def _parse_tool_arguments(
        self, tool_name: str, args: list[str], tool_info
    ) -> dict | None:
        """Parse command line arguments for a tool"""
        import json
        import shlex

        properties = tool_info.parameters.get("properties", {})
        required = tool_info.parameters.get("required", [])

        # Simple argument parsing: support key=value format
        arguments = {}

        try:
            # Use a hybrid approach: handle JSON objects specially, use shlex for others
            parsed_args = []

            # First, try to identify JSON objects and preserve them
            for arg in args:
                if "=" in arg and "{" in arg and "}" in arg:
                    # Likely contains JSON object, don't use shlex
                    parsed_args.append(arg)
                else:
                    # Use shlex for proper quote handling of non-JSON strings
                    try:
                        parsed_args.extend(shlex.split(arg))
                    except ValueError:
                        # Fallback if shlex fails
                        parsed_args.append(arg)

            for arg in parsed_args:
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Try to convert value to appropriate type based on schema
                    if key in properties:
                        prop_type = properties[key].get("type", "string")
                        try:
                            if prop_type == "integer":
                                arguments[key] = int(value)
                            elif prop_type == "number":
                                arguments[key] = float(value)
                            elif prop_type == "boolean":
                                arguments[key] = value.lower() in (
                                    "true",
                                    "1",
                                    "yes",
                                    "on",
                                )
                            elif prop_type == "array":
                                # Simple array parsing: comma-separated values
                                arguments[key] = [v.strip() for v in value.split(",")]
                            elif prop_type == "object":
                                # Try to parse as JSON
                                arguments[key] = json.loads(value)
                            else:
                                arguments[key] = value
                        except (ValueError, json.JSONDecodeError) as e:
                            print_error(f"Invalid value for {key}: {value} ({e})")
                            return None
                    else:
                        # Unknown parameter, treat as string
                        arguments[key] = value
                else:
                    print_error(f"Invalid argument format: {arg}")
                    print_info(
                        "Use key=value format with quotes for strings containing spaces"
                    )
                    print_info(
                        'Examples: query="python programming" max_results=5 enabled=true'
                    )
                    return None

            # Check required parameters
            for req_param in required:
                if req_param not in arguments:
                    print_error(f"Missing required parameter: {req_param}")
                    return None

            return arguments

        except Exception as e:
            print_error(f"Failed to parse arguments: {e}")
            print_info("Use key=value format with quotes for strings containing spaces")
            print_info(
                'Examples: query="python programming" max_results=5 enabled=true'
            )
            return None

    async def _execute_tool_direct(
        self, tool_name: str, arguments: dict, session: ChatSession
    ) -> None:
        """Execute a tool directly and display results"""
        from nova.models.tools import ExecutionContext

        try:
            context = ExecutionContext(conversation_id=session.conversation.id)
            result = await session.function_registry.execute_tool(
                tool_name, arguments, context
            )

            if result.success:
                print_success(
                    f"Tool executed successfully in {result.execution_time_ms}ms"
                )

                # Format and display the result
                if isinstance(result.result, dict):
                    print("Result:")
                    for key, value in result.result.items():
                        if isinstance(value, str) and len(value) > 200:
                            # Truncate long strings
                            print(f"  {key}: {value[:200]}...")
                        elif isinstance(value, list) and len(value) > 5:
                            # Truncate long lists
                            print(
                                f"  {key}: [{', '.join(map(str, value[:5]))}, ... ({len(value)} total)]"
                            )
                        else:
                            print(f"  {key}: {value}")
                elif isinstance(result.result, str):
                    if len(result.result) > 500:
                        print(f"Result:\n{result.result[:500]}...")
                    else:
                        print(f"Result:\n{result.result}")
                else:
                    print(f"Result: {result.result}")

            else:
                print_error(f"Tool execution failed: {result.error}")

        except Exception as e:
            print_error(f"Error executing tool: {e}")
            logger.error(f"Tool execution error: {e}", exc_info=True)

    def _handle_permissions_command(self, session: ChatSession) -> None:
        """Handle /permissions command for managing tool permissions"""

        if not session.function_registry:
            print_error("Tools system is not enabled")
            return

        permission_manager = session.function_registry.permission_manager
        granted_tools = permission_manager.get_granted_tools()

        print_info("Tool Permission Management")
        print(f"Current permission mode: {permission_manager.permission_mode}")
        print()

        if granted_tools:
            print_info("Tools with granted permissions:")
            for level, tools in granted_tools.items():
                if tools:
                    print(f"  {level}: {', '.join(tools)}")
        else:
            print_info("No permanent tool permissions granted")

        print()
        print_info("Permission levels:")
        print("  • safe - No confirmation needed")
        print("  • elevated - User confirmation required")
        print("  • system - Admin approval needed")
        print("  • dangerous - Blocked by default")
        print()
        print_info("Permission modes:")
        print("  • auto - Allow elevated tools automatically")
        print("  • prompt - Ask for permission (current)")
        print("  • deny - Block all elevated tools")
        print()
        print_info("Note: Permissions are managed interactively during tool execution")
