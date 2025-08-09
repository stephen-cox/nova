"""Advanced memory and context management for conversations"""

import re
from datetime import datetime, timedelta
from typing import Any

from nova.core.ai_client import AIError, generate_sync_response
from nova.models.config import AIModelConfig
from nova.models.message import Conversation, ConversationSummary, Message


class MemoryManager:
    """Manages conversation memory, context optimization, and summarization"""

    def __init__(self, ai_config: AIModelConfig):
        self.ai_config = ai_config
        self.summarization_threshold = 30  # Messages before considering summarization
        self.context_token_limit = 4000  # Default context window
        self.importance_keywords = [
            "important",
            "remember",
            "note",
            "key",
            "critical",
            "essential",
            "todo",
            "task",
            "action",
            "follow up",
            "reminder",
        ]

    def should_summarize_conversation(self, conversation: Conversation) -> bool:
        """Determine if a conversation should be summarized"""
        # Don't summarize if we already have recent summaries
        if conversation.summaries:
            last_summary = conversation.summaries[-1]
            messages_since_summary = (
                len(conversation.messages) - last_summary.message_count
            )
            if messages_since_summary < self.summarization_threshold:
                return False

        # Summarize if we have enough messages
        return len(conversation.messages) >= self.summarization_threshold

    def create_conversation_summary(
        self, conversation: Conversation, message_count: int | None = None
    ) -> ConversationSummary:
        """Create an AI-generated summary of conversation messages"""
        if not conversation.messages:
            raise ValueError("Cannot summarize empty conversation")

        # Determine which messages to summarize
        if message_count is None:
            # Summarize messages since last summary, or last N messages
            if conversation.summaries:
                last_summary = conversation.summaries[-1]
                messages_to_summarize = conversation.messages[
                    last_summary.message_count :
                ]
            else:
                messages_to_summarize = conversation.messages[
                    :-5
                ]  # Keep recent 5 messages
        else:
            messages_to_summarize = conversation.messages[-message_count:]

        if len(messages_to_summarize) < 3:
            raise ValueError("Need at least 3 messages to create a meaningful summary")

        # Prepare messages for AI summarization
        context_messages = []
        for msg in messages_to_summarize:
            context_messages.append({"role": msg.role.value, "content": msg.content})

        # Create summarization prompt
        summary_prompt = {
            "role": "system",
            "content": """You are helping to summarize a conversation for memory management.
            Create a concise but comprehensive summary that captures:
            1. Key topics discussed
            2. Important decisions or conclusions
            3. Action items or follow-ups mentioned
            4. Any specific facts or information that should be remembered

            Keep the summary under 200 words but ensure all important context is preserved.
            Format your response as a clear, well-structured summary.""",
        }

        try:
            # Generate summary using AI
            messages_for_ai = [summary_prompt] + context_messages
            summary_text = generate_sync_response(
                config=self.ai_config, messages=messages_for_ai
            )

            # Extract key topics using simple keyword analysis
            key_topics = self._extract_key_topics(messages_to_summarize)

            # Create and add summary to conversation
            summary = conversation.add_summary(
                summary_text=summary_text.strip(),
                message_count=len(messages_to_summarize),
                key_topics=key_topics,
            )

            return summary

        except Exception as e:
            raise AIError(f"Failed to create conversation summary: {e}")

    def _extract_key_topics(self, messages: list[Message]) -> list[str]:
        """Extract key topics from messages using simple keyword analysis"""
        topics = set()
        text_content = " ".join([msg.content.lower() for msg in messages])

        # Simple topic extraction based on noun phrases and important keywords
        words = re.findall(r"\b\w{3,}\b", text_content)
        word_freq = {}

        for word in words:
            if len(word) > 3 and word not in [
                "that",
                "this",
                "with",
                "have",
                "will",
                "from",
                "they",
                "been",
                "their",
            ]:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Get most frequent words as topics
        frequent_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        topics.update([word for word, freq in frequent_words if freq > 1])

        return list(topics)[:10]  # Limit to 10 topics

    def analyze_message_importance(
        self, message: Message, conversation: Conversation
    ) -> float:
        """Analyze and score message importance for context retention"""
        content_lower = message.content.lower()
        importance_score = 1.0  # Base score

        # Boost importance for messages with key indicators
        for keyword in self.importance_keywords:
            if keyword in content_lower:
                importance_score += 0.3

        # Boost importance for questions
        if "?" in message.content:
            importance_score += 0.2

        # Boost importance for longer messages (more detailed)
        word_count = len(message.content.split())
        if word_count > 100:
            importance_score += 0.4
        elif word_count > 50:
            importance_score += 0.2

        # Boost importance for messages with code or technical content
        if any(
            indicator in content_lower
            for indicator in ["```", "def ", "class ", "import ", "function"]
        ):
            importance_score += 0.3

        # Boost importance for recent messages
        time_since = datetime.now() - message.timestamp
        if time_since < timedelta(hours=1):
            importance_score += 0.2
        elif time_since < timedelta(hours=6):
            importance_score += 0.1

        # Cap the maximum importance score
        return min(importance_score, 3.0)

    def optimize_conversation_context(
        self, conversation: Conversation, token_limit: int | None = None
    ) -> dict[str, Any]:
        """Optimize conversation context for AI consumption"""
        if token_limit is None:
            token_limit = self.context_token_limit

        # Update message importance scores
        for message in conversation.messages:
            if message.importance_score == 1.0:  # Default score, needs analysis
                new_score = self.analyze_message_importance(message, conversation)
                message.importance_score = new_score

        # Get optimized context using the conversation's method
        context_messages = conversation.get_context_for_ai(
            token_limit=token_limit, include_summaries=True
        )

        # Calculate context statistics
        estimated_tokens = sum(
            len(msg.get("content", "").split()) * 1.3 for msg in context_messages
        )

        return {
            "messages": context_messages,
            "estimated_tokens": estimated_tokens,
            "message_count": len(context_messages),
            "includes_summaries": any(
                "Previous conversation summary" in msg.get("content", "")
                for msg in context_messages
            ),
            "context_efficiency": (
                len(context_messages) / len(conversation.messages)
                if conversation.messages
                else 0
            ),
        }

    def suggest_conversation_tags(self, conversation: Conversation) -> list[str]:
        """Suggest relevant tags for a conversation based on content analysis"""
        if not conversation.messages:
            return []

        suggested_tags = set()
        all_content = " ".join([msg.content.lower() for msg in conversation.messages])

        # Technical topic detection
        tech_keywords = {
            "python": ["python", "django", "flask", "pandas"],
            "javascript": ["javascript", "react", "node", "npm"],
            "data": ["data", "database", "sql", "analysis"],
            "ai": ["ai", "machine learning", "neural", "model"],
            "web": ["web", "html", "css", "frontend", "backend"],
            "api": ["api", "rest", "endpoint", "request"],
            "debug": ["error", "bug", "debug", "fix", "issue"],
            "planning": ["plan", "design", "architecture", "structure"],
            "research": ["research", "investigate", "explore", "study"],
        }

        for tag, keywords in tech_keywords.items():
            if any(keyword in all_content for keyword in keywords):
                suggested_tags.add(tag)

        # Add topic-based tags from summaries
        for summary in conversation.summaries:
            suggested_tags.update(
                summary.key_topics[:3]
            )  # Add top 3 topics from each summary

        return list(suggested_tags)[:8]  # Limit to 8 suggested tags

    def cleanup_old_summaries(
        self, conversation: Conversation, max_summaries: int = 10
    ) -> None:
        """Remove old summaries to prevent memory bloat"""
        if len(conversation.summaries) > max_summaries:
            # Keep the most recent summaries
            conversation.summaries = conversation.summaries[-max_summaries:]
            conversation.updated_at = datetime.now()

    def get_memory_stats(self, conversation: Conversation) -> dict[str, Any]:
        """Get detailed memory statistics for a conversation"""
        stats = conversation.get_conversation_stats()

        # Add memory-specific statistics
        high_importance_msgs = len(
            [msg for msg in conversation.messages if msg.importance_score > 1.5]
        )

        recent_activity = len(
            [
                msg
                for msg in conversation.messages
                if (datetime.now() - msg.timestamp) < timedelta(hours=24)
            ]
        )

        context_efficiency = self.optimize_conversation_context(conversation)

        stats.update(
            {
                "high_importance_messages": high_importance_msgs,
                "recent_activity_24h": recent_activity,
                "context_efficiency": context_efficiency["context_efficiency"],
                "estimated_context_tokens": context_efficiency["estimated_tokens"],
                "needs_summarization": self.should_summarize_conversation(conversation),
                "suggested_tags": self.suggest_conversation_tags(conversation),
            }
        )

        return stats
