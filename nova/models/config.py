"""Configuration models and schemas"""

from pathlib import Path
from typing import Optional, Dict
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


class AIProfile(BaseModel):
    """Named AI configuration profile"""
    name: str = Field(description="Profile name")
    provider: str = Field(description="AI provider (openai, anthropic, ollama)")
    model_name: str = Field(description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key (not required for ollama)")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")
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
    
    chat: ChatConfig = Field(default_factory=ChatConfig)
    profiles: Dict[str, AIProfile] = Field(default_factory=dict, description="Named AI profiles")
    active_profile: Optional[str] = Field(default="default", description="Currently active profile name")
    
    def get_active_ai_config(self) -> AIModelConfig:
        """Get the active AI configuration from the active profile"""
        if self.active_profile and self.active_profile in self.profiles:
            profile = self.profiles[self.active_profile]
            return AIModelConfig(
                provider=profile.provider,
                model_name=profile.model_name,
                api_key=profile.api_key,
                base_url=profile.base_url,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature
            )
        
        # Fallback to default profile if active profile is not found
        if "default" in self.profiles:
            profile = self.profiles["default"]
            return AIModelConfig(
                provider=profile.provider,
                model_name=profile.model_name,
                api_key=profile.api_key,
                base_url=profile.base_url,
                max_tokens=profile.max_tokens,
                temperature=profile.temperature
            )
        
        # If no profiles exist, create a minimal default config
        return AIModelConfig()