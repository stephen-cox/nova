"""Message and conversation models"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role types"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Individual chat message"""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    token_count: Optional[int] = Field(default=None, description="Estimated token count")
    importance_score: float = Field(default=1.0, description="Message importance for context retention")


class ConversationSummary(BaseModel):
    """Summary of conversation segments for memory management"""
    summary_text: str
    message_count: int
    start_timestamp: datetime
    end_timestamp: datetime
    key_topics: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class Conversation(BaseModel):
    """Chat conversation container"""
    id: str = Field(description="Unique conversation ID")
    title: Optional[str] = Field(default=None, description="Conversation title")
    messages: List[Message] = Field(default_factory=list)
    summaries: List[ConversationSummary] = Field(default_factory=list, description="Historical summaries")
    tags: List[str] = Field(default_factory=list, description="Conversation tags for categorization")
    context_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context information")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def add_message(self, role: MessageRole, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add a new message to the conversation"""
        message = Message(role=role, content=content, metadata=metadata)
        self.messages.append(message)
        self.updated_at = datetime.now()
        return message
    
    def get_recent_messages(self, limit: int) -> List[Message]:
        """Get the most recent messages"""
        return self.messages[-limit:] if limit > 0 else self.messages
    
    def get_messages_by_importance(self, min_score: float = 0.5, limit: Optional[int] = None) -> List[Message]:
        """Get messages above a certain importance threshold"""
        important_messages = [msg for msg in self.messages if msg.importance_score >= min_score]
        if limit:
            # Sort by importance score descending, then by timestamp descending
            important_messages.sort(key=lambda x: (x.importance_score, x.timestamp), reverse=True)
            return important_messages[:limit]
        return important_messages
    
    def get_context_for_ai(self, token_limit: int = 4000, include_summaries: bool = True) -> List[Dict[str, str]]:
        """Get optimized context for AI, respecting token limits"""
        context = []
        estimated_tokens = 0
        
        # Add recent messages first (most important for context)
        for message in reversed(self.messages):
            msg_tokens = message.token_count or len(message.content.split()) * 1.3  # Rough estimate
            if estimated_tokens + msg_tokens > token_limit * 0.8:  # Reserve 20% for summaries
                break
            
            context.insert(0, {
                "role": message.role.value,
                "content": message.content
            })
            estimated_tokens += msg_tokens
        
        # Add summaries if there's space and they exist
        if include_summaries and self.summaries and estimated_tokens < token_limit * 0.8:
            remaining_tokens = token_limit - estimated_tokens
            summary_context = []
            
            for summary in reversed(self.summaries):
                summary_tokens = len(summary.summary_text.split()) * 1.3
                if summary_tokens > remaining_tokens:
                    break
                
                summary_context.insert(0, {
                    "role": "system",
                    "content": f"Previous conversation summary: {summary.summary_text}"
                })
                remaining_tokens -= summary_tokens
            
            # Insert summaries at the beginning
            context = summary_context + context
        
        return context
    
    def add_summary(self, summary_text: str, message_count: int, key_topics: List[str] = None) -> ConversationSummary:
        """Add a conversation summary"""
        if not self.messages:
            raise ValueError("Cannot create summary for conversation with no messages")
        
        start_msg = self.messages[max(0, len(self.messages) - message_count)]
        end_msg = self.messages[-1]
        
        summary = ConversationSummary(
            summary_text=summary_text,
            message_count=message_count,
            start_timestamp=start_msg.timestamp,
            end_timestamp=end_msg.timestamp,
            key_topics=key_topics or []
        )
        
        self.summaries.append(summary)
        self.updated_at = datetime.now()
        return summary
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the conversation"""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now()
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the conversation"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now()
    
    def update_message_importance(self, message_index: int, importance_score: float) -> None:
        """Update the importance score of a message"""
        if 0 <= message_index < len(self.messages):
            self.messages[message_index].importance_score = importance_score
            self.updated_at = datetime.now()
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics"""
        if not self.messages:
            return {"message_count": 0, "total_tokens": 0, "duration": None}
        
        total_tokens = sum(msg.token_count or 0 for msg in self.messages)
        duration = self.messages[-1].timestamp - self.messages[0].timestamp
        
        return {
            "message_count": len(self.messages),
            "total_tokens": total_tokens,
            "duration": duration,
            "summaries_count": len(self.summaries),
            "tags": self.tags,
            "avg_importance": sum(msg.importance_score for msg in self.messages) / len(self.messages)
        }