"""Chat history management with markdown save/load"""

import re
from datetime import datetime
from pathlib import Path

from nova.models.message import Conversation, Message, MessageRole


class HistoryError(Exception):
    """History-related errors"""

    pass


class HistoryManager:
    """Manages chat history persistence in markdown format"""

    def __init__(self, history_dir: Path):
        self.history_dir = Path(history_dir).expanduser()
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_conversation(
        self, conversation: Conversation, filename: str | None = None
    ) -> Path:
        """Save conversation to markdown file"""

        # Generate intelligent title if none exists
        if not conversation.title and conversation.messages:
            conversation.title = self._generate_content_based_title(conversation)

        if not filename:
            # Generate filename from conversation ID and timestamp
            timestamp = conversation.created_at.strftime("%Y%m%d_%H%M%S")
            safe_id = re.sub(r"[^\w\-]", "_", conversation.id)
            filename = f"{timestamp}_{safe_id}.md"

        if not filename.endswith(".md"):
            filename += ".md"

        filepath = self.history_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self._conversation_to_markdown(conversation))
            return filepath
        except Exception as e:
            raise HistoryError(f"Error saving conversation to {filepath}: {e}")

    def load_conversation(self, filepath: Path) -> Conversation:
        """Load conversation from markdown file"""

        if not filepath.exists():
            raise HistoryError(f"History file not found: {filepath}")

        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            return self._markdown_to_conversation(content, filepath.stem)
        except Exception as e:
            raise HistoryError(f"Error loading conversation from {filepath}: {e}")

    def list_conversations(self) -> list[tuple[Path, str, datetime]]:
        """List all conversation files with metadata"""
        conversations = []

        for filepath in self.history_dir.glob("*.md"):
            try:
                # Extract timestamp from filename or file modification time
                timestamp_match = re.match(r"^(\d{8}_\d{6})", filepath.stem)
                if timestamp_match:
                    timestamp = datetime.strptime(
                        timestamp_match.group(1), "%Y%m%d_%H%M%S"
                    )
                else:
                    timestamp = datetime.fromtimestamp(filepath.stat().st_mtime)

                # Extract title from file (first non-metadata line)
                with open(filepath, encoding="utf-8") as f:
                    lines = f.readlines()

                title = "Untitled"
                for line in lines:
                    line = line.strip()
                    if (
                        line
                        and not line.startswith("<!--")
                        and not line.startswith("##")
                    ):
                        # Extract title from first user message or use first content
                        if line.startswith("**User:**"):
                            title = line[9:].strip()[:50]
                        elif line.startswith("# "):
                            title = line[2:].strip()[:50]  # Remove '# ' prefix
                        else:
                            title = line[:50]
                        break

                conversations.append((filepath, title, timestamp))

            except Exception:
                # Skip problematic files
                continue

        # Sort by timestamp (newest first)
        conversations.sort(key=lambda x: x[2], reverse=True)
        return conversations

    def get_most_recent_conversation(self) -> tuple[Path, str, datetime] | None:
        """Get the most recent conversation file"""
        conversations = self.list_conversations()
        return conversations[0] if conversations else None

    def _conversation_to_markdown(self, conversation: Conversation) -> str:
        """Convert conversation to markdown format"""

        lines = []

        # Metadata header
        lines.append("<!-- Nova Chat History -->")
        lines.append(f"<!-- Conversation ID: {conversation.id} -->")
        lines.append(f"<!-- Created: {conversation.created_at.isoformat()} -->")
        lines.append(f"<!-- Updated: {conversation.updated_at.isoformat()} -->")

        if conversation.title:
            lines.append(f"<!-- Title: {conversation.title} -->")

        lines.append("")

        # Title
        title = (
            conversation.title
            or f"Chat {conversation.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        lines.append(f"# {title}")
        lines.append("")

        # Messages
        for message in conversation.messages:
            timestamp = message.timestamp.strftime("%H:%M:%S")

            if message.role == MessageRole.USER:
                lines.append(f"## User ({timestamp})")
            elif message.role == MessageRole.ASSISTANT:
                lines.append(f"## Nova ({timestamp})")
            elif message.role == MessageRole.SYSTEM:
                lines.append(f"## System ({timestamp})")

            lines.append("")
            lines.append(message.content)
            lines.append("")

        return "\n".join(lines)

    def _generate_content_based_title(self, conversation: Conversation) -> str:
        """Generate a meaningful title based on conversation content"""
        if not conversation.messages:
            return f"Chat {conversation.created_at.strftime('%Y-%m-%d %H:%M')}"

        # Get first user message to analyze
        first_user_message = None
        for message in conversation.messages:
            if message.role == MessageRole.USER:
                first_user_message = message
                break

        if not first_user_message:
            return f"Chat {conversation.created_at.strftime('%Y-%m-%d %H:%M')}"

        content = first_user_message.content.strip()

        # Remove common prefixes and clean up
        content = re.sub(
            r"^(please|can you|could you|help me|I need|I want to)\s+",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(r"^(to\s+)", "", content, flags=re.IGNORECASE)

        # Extract key topics and actions
        title = self._extract_meaningful_title(content)

        # Ensure title is reasonable length
        if len(title) > 60:
            title = title[:57] + "..."

        # Capitalize first letter
        title = title[0].upper() + title[1:] if title else title

        return title or f"Chat {conversation.created_at.strftime('%Y-%m-%d %H:%M')}"

    def _extract_meaningful_title(self, content: str) -> str:
        """Extract meaningful title from content using patterns"""
        # Common patterns for different types of requests
        patterns = [
            # Programming/code related
            (
                r"(implement|create|build|develop|write|code|program)\s+(.+?)(?:\?|$|\.|\n)",
                r"\1 \2",
            ),
            (r"(fix|debug|solve|resolve)\s+(.+?)(?:\?|$|\.|\n)", r"Fix \2"),
            (r"(optimize|improve|refactor)\s+(.+?)(?:\?|$|\.|\n)", r"Optimize \2"),
            (r"(test|unit test|testing)\s+(.+?)(?:\?|$|\.|\n)", r"Test \2"),
            # Analysis/research
            (r"(analyze|review|examine|study)\s+(.+?)(?:\?|$|\.|\n)", r"Analyze \2"),
            (r"(explain|describe|tell me about)\s+(.+?)(?:\?|$|\.|\n)", r"Explain \2"),
            (r"(compare|contrast)\s+(.+?)(?:\?|$|\.|\n)", r"Compare \2"),
            # Questions
            (r"(what is|what are|what's)\s+(.+?)(?:\?|$|\.|\n)", r"What is \2"),
            (r"(how to|how do|how can)\s+(.+?)(?:\?|$|\.|\n)", r"How to \2"),
            (r"(why does|why is|why do)\s+(.+?)(?:\?|$|\.|\n)", r"Why \2"),
            (r"(when should|when to|when is)\s+(.+?)(?:\?|$|\.|\n)", r"When to \2"),
            (r"(where is|where can|where to)\s+(.+?)(?:\?|$|\.|\n)", r"Where to \2"),
            # General assistance
            (r"(help with|help me)\s+(.+?)(?:\?|$|\.|\n)", r"Help with \2"),
            (r"(show me|demonstrate)\s+(.+?)(?:\?|$|\.|\n)", r"Show \2"),
            (r"(find|search for|look for)\s+(.+?)(?:\?|$|\.|\n)", r"Find \2"),
        ]

        content_lower = content.lower()

        for pattern, replacement in patterns:
            match = re.search(pattern, content_lower)
            if match:
                # Apply replacement and clean up
                title = re.sub(pattern, replacement, content_lower).strip()
                # Remove extra whitespace and clean up
                title = re.sub(r"\s+", " ", title)
                title = title.replace("\n", " ").strip()
                return title

        # Fallback: use first meaningful sentence/phrase
        sentences = re.split(r"[.!?]", content)
        first_sentence = sentences[0].strip() if sentences else content

        # Remove very short or generic phrases
        if len(first_sentence) < 10 or first_sentence.lower() in [
            "hi",
            "hello",
            "hey",
            "help",
        ]:
            # Look for the next sentence
            for sentence in sentences[1:]:
                sentence = sentence.strip()
                if len(sentence) > 10:
                    first_sentence = sentence
                    break

        # Clean up and return
        first_sentence = re.sub(r"\s+", " ", first_sentence).strip()
        return first_sentence

    def _markdown_to_conversation(
        self, content: str, conversation_id: str
    ) -> Conversation:
        """Parse markdown content back to conversation"""

        lines = content.split("\n")

        # Parse metadata
        metadata = {}
        for line in lines:
            if line.startswith("<!-- ") and line.endswith(" -->"):
                comment = line[5:-4]
                if ":" in comment:
                    key, value = comment.split(":", 1)
                    metadata[key.strip()] = value.strip()

        # Extract conversation details
        conv_id = metadata.get("Conversation ID", conversation_id)
        title = metadata.get("Title")

        try:
            created_at = (
                datetime.fromisoformat(metadata["Created"])
                if "Created" in metadata
                else datetime.now()
            )
            updated_at = (
                datetime.fromisoformat(metadata["Updated"])
                if "Updated" in metadata
                else datetime.now()
            )
        except ValueError:
            created_at = updated_at = datetime.now()

        # Parse messages
        messages = []
        current_role = None
        current_content = []
        current_timestamp = None

        for line in lines:
            # Check for message headers
            if line.startswith("## "):
                # Save previous message
                if current_role and current_content:
                    content_text = "\n".join(current_content).strip()
                    if content_text:
                        messages.append(
                            Message(
                                role=current_role,
                                content=content_text,
                                timestamp=current_timestamp or datetime.now(),
                            )
                        )

                # Parse new message header
                header = line[3:].strip()
                if header.startswith("User"):
                    current_role = MessageRole.USER
                elif header.startswith("Assistant") or header.startswith("Nova"):
                    current_role = MessageRole.ASSISTANT
                elif header.startswith("System"):
                    current_role = MessageRole.SYSTEM
                else:
                    current_role = None

                # Extract timestamp from header
                timestamp_match = re.search(r"\((\d{2}:\d{2}:\d{2})\)", header)
                if timestamp_match:
                    time_str = timestamp_match.group(1)
                    try:
                        # Use today's date with the extracted time
                        time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
                        current_timestamp = datetime.combine(
                            created_at.date(), time_obj
                        )
                    except ValueError:
                        current_timestamp = datetime.now()
                else:
                    current_timestamp = datetime.now()

                current_content = []

            elif (
                current_role
                and not line.startswith("#")
                and not line.startswith("<!--")
            ):
                # Add to current message content
                current_content.append(line)

        # Save final message
        if current_role and current_content:
            content_text = "\n".join(current_content).strip()
            if content_text:
                messages.append(
                    Message(
                        role=current_role,
                        content=content_text,
                        timestamp=current_timestamp or datetime.now(),
                    )
                )

        return Conversation(
            id=conv_id,
            title=title,
            messages=messages,
            created_at=created_at,
            updated_at=updated_at,
        )
