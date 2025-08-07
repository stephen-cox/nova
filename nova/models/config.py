"""Configuration models and schemas"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIModelConfig(BaseModel):
    """Configuration for AI model settings"""

    provider: str = Field(
        default="openai", description="AI provider (openai, anthropic, ollama)"
    )
    model_name: str = Field(default="gpt-3.5-turbo", description="Model name")
    api_key: str | None = Field(
        default=None, description="API key (not required for ollama)"
    )
    base_url: str | None = Field(
        default=None,
        description="Custom API base URL (e.g., http://localhost:11434 for ollama)",
    )
    max_tokens: int = Field(
        default=2000, description="Maximum tokens per response", gt=0
    )
    temperature: float = Field(
        default=0.7, description="Response temperature", ge=0.0, le=1.0
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed_providers = {"openai", "anthropic", "ollama"}
        if v not in allowed_providers:
            raise ValueError(f"Provider must be one of: {', '.join(allowed_providers)}")
        return v


class PromptConfig(BaseModel):
    """Prompt system configuration"""

    enabled: bool = Field(default=True, description="Enable custom prompting")
    library_path: Path = Field(
        default=Path("~/.nova/prompts"), description="Prompt library location"
    )
    allow_user_prompts: bool = Field(
        default=True, description="Allow user-defined prompts"
    )
    validate_prompts: bool = Field(
        default=True, description="Validate prompt templates"
    )
    max_prompt_length: int = Field(default=8192, description="Maximum prompt length")


class ToolsConfig(BaseModel):
    """Tools and function calling configuration"""

    enabled: bool = Field(default=True, description="Enable function calling")

    # Built-in tools
    enabled_built_in_modules: list[str] = Field(
        default_factory=lambda: ["file_ops", "web_search", "conversation"],
        description="Enabled built-in tool modules",
    )

    # Permission settings
    permission_mode: str = Field(
        default="prompt", description="Permission mode: auto, prompt, deny"
    )

    # Execution settings
    execution_timeout: int = Field(
        default=30, description="Tool execution timeout (seconds)"
    )
    max_concurrent_tools: int = Field(
        default=3, description="Max concurrent tool executions"
    )

    @field_validator("permission_mode")
    @classmethod
    def validate_permission_mode(cls, v: str) -> str:
        allowed_modes = {"auto", "prompt", "deny"}
        if v not in allowed_modes:
            raise ValueError(
                f"Permission mode must be one of: {', '.join(allowed_modes)}"
            )
        return v

    # MCP integration (for future use)
    mcp_enabled: bool = Field(
        default=False, description="Enable MCP server integration"
    )

    # Advanced features
    tool_suggestions: bool = Field(
        default=True, description="Enable AI tool suggestions"
    )
    execution_logging: bool = Field(default=True, description="Log tool executions")


class AIProfile(BaseModel):
    """Named AI configuration profile"""

    name: str = Field(description="Profile name")
    provider: str = Field(description="AI provider (openai, anthropic, ollama)")
    model_name: str = Field(description="Model name")
    api_key: str | None = Field(
        default=None, description="API key (not required for ollama)"
    )
    base_url: str | None = Field(default=None, description="Custom API base URL")
    max_tokens: int = Field(
        default=2000, description="Maximum tokens per response", gt=0
    )
    temperature: float = Field(
        default=0.7, description="Response temperature", ge=0.0, le=1.0
    )
    system_prompt: str | None = Field(
        default=None, description="Custom system prompt or template reference"
    )
    prompt_variables: dict[str, str] = Field(
        default_factory=dict, description="Default prompt variables"
    )

    # Tools configuration per profile
    tools: ToolsConfig | None = Field(
        default=None,
        description="Tools configuration for this profile (inherits global if None)",
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed_providers = {"openai", "anthropic", "ollama"}
        if v not in allowed_providers:
            raise ValueError(f"Provider must be one of: {', '.join(allowed_providers)}")
        return v


class SearchConfig(BaseModel):
    """Configuration for web search functionality"""

    enabled: bool = Field(default=True, description="Enable web search functionality")
    default_provider: str = Field(
        default="duckduckgo", description="Default search provider"
    )
    max_results: int = Field(
        default=5, description="Default maximum search results", gt=0, le=50
    )
    use_ai_answers: bool = Field(
        default=True,
        description="Generate AI-powered answers from search results instead of showing raw results",
    )
    google: dict[str, str] = Field(
        default_factory=dict,
        description="Google Custom Search configuration (api_key, search_engine_id)",
    )
    bing: dict[str, str] = Field(
        default_factory=dict, description="Bing Search API configuration (api_key)"
    )

    @field_validator("default_provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed_providers = {"duckduckgo", "google", "bing"}
        if v not in allowed_providers:
            raise ValueError(f"Provider must be one of: {', '.join(allowed_providers)}")
        return v


class MonitoringConfig(BaseModel):
    """Configuration for monitoring and debugging"""

    enabled: bool = Field(default=True, description="Enable monitoring")
    level: str = Field(
        default="basic", description="Monitoring level (basic, detailed, debug)"
    )
    debug_log_file: str = Field(
        default="~/.nova/debug.log", description="Debug log file path"
    )
    context_warnings: bool = Field(default=True, description="Show context warnings")
    performance_metrics: bool = Field(
        default=True, description="Collect performance metrics"
    )


class ChatConfig(BaseModel):
    """Configuration for chat behavior"""

    history_dir: Path = Field(
        default=Path("~/.nova/history"), description="Chat history directory"
    )
    max_history_length: int = Field(
        default=50, description="Maximum messages to keep in memory", gt=0
    )
    auto_save: bool = Field(default=True, description="Auto-save chat history")


class NovaConfig(BaseModel):
    """Main configuration model"""

    model_config = ConfigDict(extra="forbid")

    chat: ChatConfig = Field(default_factory=ChatConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    prompts: PromptConfig = Field(default_factory=PromptConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    profiles: dict[str, AIProfile] = Field(
        default_factory=dict, description="Named AI profiles"
    )
    active_profile: str | None = Field(
        default="default", description="Currently active profile name"
    )

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
                temperature=profile.temperature,
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
                temperature=profile.temperature,
            )

        # If no profiles exist, create a minimal default config
        return AIModelConfig()

    def get_effective_tools_config(self) -> ToolsConfig:
        """Get the effective tools configuration from the active profile or global config"""
        # Check if active profile has tools configuration
        if self.active_profile and self.active_profile in self.profiles:
            profile = self.profiles[self.active_profile]
            if profile.tools is not None:
                return profile.tools

        # Fallback to default profile tools config
        if "default" in self.profiles:
            profile = self.profiles["default"]
            if profile.tools is not None:
                return profile.tools

        # Fall back to global tools configuration
        return self.tools
