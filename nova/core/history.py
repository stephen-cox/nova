"""Chat history management with markdown save/load"""

import logging
import re
from datetime import datetime
from pathlib import Path

import yaml

from nova.models.message import Conversation, Message, MessageRole

logger = logging.getLogger(__name__)


class HistoryError(Exception):
    """History-related errors"""

    pass


def _validate_metadata(metadata: dict) -> dict:
    """Validate and sanitize metadata from YAML frontmatter"""
    allowed_keys = {
        "conversation_id",
        "created",
        "updated",
        "title",
        "tags",
        "summaries_count",
    }
    max_title_length = 200
    max_tag_count = 50
    max_tag_length = 100

    validated = {}

    for key, value in metadata.items():
        if key not in allowed_keys:
            logger.warning(f"Ignoring unknown metadata key: {key}")
            continue

        if key == "title" and isinstance(value, str):
            # Validate and truncate title
            validated[key] = value.strip()[:max_title_length]
        elif key in ["created", "updated"] and isinstance(value, str):
            # Validate ISO format timestamps
            try:
                datetime.fromisoformat(value)
                validated[key] = value
            except ValueError:
                logger.warning(f"Invalid timestamp format for {key}: {value}")
        elif key == "conversation_id" and isinstance(value, str):
            # Sanitize conversation_id
            validated[key] = re.sub(r"[^\w\-]", "_", value.strip())
        elif key == "tags" and isinstance(value, list):
            # Validate tags list
            clean_tags = []
            for tag in value[:max_tag_count]:  # Limit number of tags
                if isinstance(tag, str):
                    clean_tag = tag.strip()[:max_tag_length]
                    if clean_tag:
                        clean_tags.append(clean_tag)
            validated[key] = clean_tags
        elif key == "summaries_count" and isinstance(value, int):
            # Validate summaries count
            if 0 <= value <= 1000:  # Reasonable limit
                validated[key] = value
        else:
            # For other valid keys, store as-is if basic type check passes
            if isinstance(value, str | int | list):
                validated[key] = value

    return validated


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

                # Extract title efficiently (reads only first 1KB)
                title = self._extract_title_efficiently(filepath)

                conversations.append((filepath, title, timestamp))

            except OSError as e:
                logger.warning(f"Could not access file {filepath}: {e}")
            except ValueError as e:
                logger.warning(f"Invalid timestamp in filename {filepath}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error processing file {filepath}: {e}")

        # Sort by timestamp (newest first)
        conversations.sort(key=lambda x: x[2], reverse=True)
        return conversations

    def get_most_recent_conversation(self) -> tuple[Path, str, datetime] | None:
        """Get the most recent conversation file"""
        conversations = self.list_conversations()
        return conversations[0] if conversations else None

    def _conversation_to_markdown(self, conversation: Conversation) -> str:
        """Convert conversation to markdown format with YAML frontmatter"""

        lines = []

        # YAML frontmatter header
        metadata = {
            "conversation_id": conversation.id,
            "created": conversation.created_at.isoformat(),
            "updated": conversation.updated_at.isoformat(),
        }

        if conversation.title:
            metadata["title"] = conversation.title

        if conversation.tags:
            metadata["tags"] = list(conversation.tags)

        if conversation.summaries:
            metadata["summaries_count"] = len(conversation.summaries)

        lines.append("---")
        lines.append(yaml.dump(metadata, default_flow_style=False).strip())
        lines.append("---")
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

    def _parse_yaml_frontmatter(self, content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter and return validated metadata and remaining content"""
        if not content.startswith("---\n"):
            return {}, content

        lines = content.split("\n")
        frontmatter_end = -1

        # Find the end of the frontmatter
        for i, line in enumerate(lines[1:], 1):  # Skip first "---"
            if line.strip() == "---":
                frontmatter_end = i
                break

        if frontmatter_end <= 0:
            logger.warning("YAML frontmatter found but no closing delimiter")
            return {}, content

        try:
            frontmatter_text = "\n".join(lines[1:frontmatter_end])
            frontmatter = yaml.safe_load(frontmatter_text)

            if frontmatter is None:
                # Empty YAML frontmatter is valid, return empty metadata
                remaining_content = "\n".join(lines[frontmatter_end + 1 :])
                return {}, remaining_content
            elif not isinstance(frontmatter, dict):
                logger.warning("YAML frontmatter must be a dictionary")
                return {}, content

            # Validate and sanitize metadata
            validated_metadata = _validate_metadata(frontmatter)
            remaining_content = "\n".join(lines[frontmatter_end + 1 :])

            return validated_metadata, remaining_content

        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML frontmatter: {e}")
            return {}, content
        except Exception as e:
            logger.error(f"Unexpected error parsing YAML frontmatter: {e}")
            return {}, content

    def _parse_legacy_metadata(self, content: str) -> dict:
        """Parse legacy HTML comment metadata format"""
        metadata = {}
        lines = content.split("\n")

        for line in lines:
            if line.startswith("<!-- ") and line.endswith(" -->"):
                comment = line[5:-4]
                if ":" in comment:
                    key, value = comment.split(":", 1)
                    # Map old keys to new YAML format
                    old_key = key.strip()
                    if old_key == "Conversation ID":
                        metadata["conversation_id"] = value.strip()
                    elif old_key == "Created":
                        metadata["created"] = value.strip()
                    elif old_key == "Updated":
                        metadata["updated"] = value.strip()
                    elif old_key == "Title":
                        metadata["title"] = value.strip()

        # Still validate legacy metadata
        return _validate_metadata(metadata)

    def _extract_title_efficiently(self, filepath: Path) -> str:
        """Extract title efficiently by reading only the beginning of file"""
        try:
            with open(filepath, encoding="utf-8") as f:
                # Read only first 1KB for title extraction
                partial_content = f.read(1024)

            if partial_content.startswith("---\n"):
                # Parse only YAML frontmatter
                metadata, _ = self._parse_yaml_frontmatter(partial_content)
                if "title" in metadata:
                    return metadata["title"][:50]

            # Fallback to content-based title extraction
            return self._extract_title_from_content(partial_content)

        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Error reading file {filepath}: {e}")
            return "Untitled"

    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from content when no frontmatter title exists"""
        lines = content.split("\n")

        # Look for the first real markdown H1 header (outside of YAML frontmatter)
        skip_until_content = False
        if content.strip().startswith("---"):
            skip_until_content = True

        for line in lines:
            stripped = line.strip()

            # If we started with ---, wait for the content section
            if skip_until_content:
                if stripped == "---":
                    skip_until_content = False  # Found closing, now look for content
                continue

            # Look for markdown H1 header
            if stripped.startswith("# ") and not stripped.startswith("##"):
                # Make sure it's not a comment inside YAML
                return stripped[2:].strip()[:50]  # Remove '# ' prefix

        # Fallback to first non-metadata content
        skip_until_content = False
        if content.strip().startswith("---"):
            skip_until_content = True

        for line in lines:
            stripped = line.strip()

            # If we started with ---, wait for the content section
            if skip_until_content:
                if stripped == "---":
                    skip_until_content = False
                continue

            # Skip empty lines, comments, and headers
            if (
                not stripped
                or stripped.startswith("<!--")
                or stripped.startswith("#")
                or stripped.startswith("##")
            ):
                continue

            # Extract title from first user message or use first content
            if stripped.startswith("**User:**"):
                return stripped[9:].strip()[:50]
            else:
                return stripped[:50]

        return "Untitled"

    def _markdown_to_conversation(
        self, content: str, conversation_id: str
    ) -> Conversation:
        """Parse markdown content back to conversation"""

        # Parse metadata using new helper methods
        metadata, content = self._parse_yaml_frontmatter(content)

        # Fallback to HTML comment parsing for legacy files
        if not metadata:
            metadata = self._parse_legacy_metadata(content)

        # Extract conversation details
        conv_id = metadata.get("conversation_id", conversation_id)
        title = metadata.get("title")

        try:
            created_at = (
                datetime.fromisoformat(metadata["created"])
                if "created" in metadata
                else datetime.now()
            )
            updated_at = (
                datetime.fromisoformat(metadata["updated"])
                if "updated" in metadata
                else datetime.now()
            )
        except ValueError:
            created_at = updated_at = datetime.now()

        # Parse messages
        messages = []
        current_role = None
        current_content = []
        current_timestamp = None

        # Split content into lines for message parsing
        lines = content.split("\n")

        for line in lines:
            # Check for message headers - must match pattern "## User/Nova/System (timestamp)"
            message_header_match = re.match(
                r"^## (User|Nova|Assistant|System)\s*\((\d{2}:\d{2}:\d{2})\)", line
            )
            if message_header_match:
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
                role_name = message_header_match.group(1)
                timestamp_str = message_header_match.group(2)

                if role_name == "User":
                    current_role = MessageRole.USER
                elif role_name in ["Assistant", "Nova"]:
                    current_role = MessageRole.ASSISTANT
                elif role_name == "System":
                    current_role = MessageRole.SYSTEM
                else:
                    current_role = None

                # Extract timestamp from header
                try:
                    # Use today's date with the extracted time
                    time_obj = datetime.strptime(timestamp_str, "%H:%M:%S").time()
                    current_timestamp = datetime.combine(created_at.date(), time_obj)
                except ValueError:
                    current_timestamp = datetime.now()

                current_content = []

            elif current_role and not line.startswith("<!--"):
                # Add to current message content (exclude only metadata comments)
                # Note: We allow "---" lines within message content as they could be horizontal rules
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

        # Generate title from content if not available
        if not title:
            # First try to extract from markdown headers in content
            title = self._extract_title_from_content(content)

            # If that doesn't work and we have messages, use content-based generation
            if title == "Untitled" and messages:
                temp_conversation = Conversation(
                    id=conv_id,
                    title=None,
                    messages=messages,
                    created_at=created_at,
                    updated_at=updated_at,
                )
                title = self._generate_content_based_title(temp_conversation)

        # Create conversation object
        conversation = Conversation(
            id=conv_id,
            title=title,
            messages=messages,
            created_at=created_at,
            updated_at=updated_at,
        )

        # Restore tags if they exist in metadata
        if "tags" in metadata and isinstance(metadata["tags"], list):
            conversation.tags = set(metadata["tags"])

        return conversation
