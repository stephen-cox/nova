"""Configuration models and schemas"""

from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class AIModelConfig(BaseModel):
    """Configuration for AI model settings"""
    provider: str = Field(default="openai", description="AI provider (openai, anthropic, ollama)")
    model_name: str = Field(default="gpt-3.5-turbo", description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key (not required for ollama)")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL (e.g., http://localhost:11434 for ollama)")
    max_tokens: int = Field(default=2000, description="Maximum tokens per response", gt=0)
    temperature: float = Field(default=0.7, description="Response temperature", ge=0.0, le=1.0)
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed_providers = {'openai', 'anthropic', 'ollama'}
        if v not in allowed_providers:
            raise ValueError(f'Provider must be one of: {", ".join(allowed_providers)}')
        return v


class ChatConfig(BaseModel):
    """Configuration for chat behavior"""
    history_dir: Path = Field(default=Path("~/.nova/history"), description="Chat history directory")
    max_history_length: int = Field(default=50, description="Maximum messages to keep in memory", gt=0)
    auto_save: bool = Field(default=True, description="Auto-save chat history")


class NovaConfig(BaseModel):
    """Main configuration model"""
    model_config = ConfigDict(extra="forbid")
    
    ai_model: AIModelConfig = Field(default_factory=AIModelConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)