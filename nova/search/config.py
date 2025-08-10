"""Search configuration management"""

from typing import Any

from pydantic import BaseModel, Field

from .models import SearchEnhancementMode


class SearchConfig(BaseModel):
    """Configuration for enhanced web search functionality"""

    # Existing basic configuration
    enabled: bool = Field(default=True, description="Enable web search functionality")
    default_provider: str = Field(
        default="duckduckgo", description="Default search provider"
    )
    max_results: int = Field(
        default=5, description="Default maximum search results", gt=0, le=50
    )
    ai_response: bool = Field(
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

    # Enhanced search configuration
    default_enhancement: SearchEnhancementMode = Field(
        default=SearchEnhancementMode.FAST,
        description="Default search enhancement mode for /search command and web_search tool"
    )
    enable_conversation_context: bool = Field(
        default=True,
        description="Use recent conversation history to enhance search queries"
    )
    context_messages_count: int = Field(
        default=5,
        description="Number of recent messages to use for context",
        ge=0, le=20
    )
    default_technical_level: str = Field(
        default="intermediate",
        description="Default technical level for search queries",
        pattern="^(beginner|intermediate|expert)$"
    )
    default_timeframe: str = Field(
        default="any",
        description="Default timeframe preference for search results",
        pattern="^(recent|past_year|any)$"
    )

    # Performance and caching
    enhancement_cache_enabled: bool = Field(
        default=True,
        description="Cache enhanced queries to improve performance"
    )
    enhancement_cache_duration_minutes: int = Field(
        default=15,
        description="How long to cache enhanced queries",
        gt=0, le=1440  # Max 24 hours
    )
    performance_mode: bool = Field(
        default=True,
        description="Prioritize speed over semantic accuracy in enhancements"
    )

    # Keyword extraction configuration
    extraction_backend: str = Field(
        default="yake_only",
        description="Keyword extraction backend",
        pattern="^(yake_only|keybert_only|hybrid|adaptive)$"
    )
    enable_keybert: bool = Field(
        default=False,
        description="Enable KeyBERT semantic extraction (requires additional dependencies)"
    )
    yake_max_keywords: int = Field(
        default=10,
        description="Maximum keywords to extract using YAKE",
        gt=0, le=50
    )
    keybert_max_keywords: int = Field(
        default=6,
        description="Maximum keywords to extract using KeyBERT",
        gt=0, le=20
    )
    keybert_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="KeyBERT model name for semantic extraction"
    )

    @classmethod
    def from_nova_config(cls, config: dict[str, Any]) -> "SearchConfig":
        """Create SearchConfig from Nova configuration"""
        search_config = config.get("search", {})

        # Map Nova config to SearchConfig fields
        return cls(
            enabled=search_config.get("enabled", True),
            default_provider=search_config.get("default_provider", "duckduckgo"),
            max_results=search_config.get("max_results", 5),
            ai_response=search_config.get("ai_response", True),
            google=search_config.get("google", {}),
            bing=search_config.get("bing", {}),

            # Enhanced search settings
            default_enhancement=SearchEnhancementMode(
                search_config.get("default_enhancement", SearchEnhancementMode.FAST)
            ),
            enable_conversation_context=search_config.get("enable_conversation_context", True),
            context_messages_count=search_config.get("context_messages_count", 5),
            default_technical_level=search_config.get("default_technical_level", "intermediate"),
            default_timeframe=search_config.get("default_timeframe", "any"),

            # Performance settings
            enhancement_cache_enabled=search_config.get("enhancement_cache_enabled", True),
            enhancement_cache_duration_minutes=search_config.get("enhancement_cache_duration_minutes", 15),
            performance_mode=search_config.get("performance_mode", True),

            # Extraction settings
            extraction_backend=search_config.get("extraction_backend", "yake_only"),
            enable_keybert=search_config.get("enable_keybert", False),
            yake_max_keywords=search_config.get("yake_max_keywords", 10),
            keybert_max_keywords=search_config.get("keybert_max_keywords", 6),
            keybert_model=search_config.get("keybert_model", "all-MiniLM-L6-v2"),
        )

    def to_nova_config(self) -> dict[str, Any]:
        """Convert SearchConfig back to Nova configuration format"""
        return {
            "search": {
                "enabled": self.enabled,
                "default_provider": self.default_provider,
                "max_results": self.max_results,
                "ai_response": self.ai_response,
                "google": self.google,
                "bing": self.bing,

                # Enhanced search settings
                "default_enhancement": self.default_enhancement.value,
                "enable_conversation_context": self.enable_conversation_context,
                "context_messages_count": self.context_messages_count,
                "default_technical_level": self.default_technical_level,
                "default_timeframe": self.default_timeframe,

                # Performance settings
                "enhancement_cache_enabled": self.enhancement_cache_enabled,
                "enhancement_cache_duration_minutes": self.enhancement_cache_duration_minutes,
                "performance_mode": self.performance_mode,

                # Extraction settings
                "extraction_backend": self.extraction_backend,
                "enable_keybert": self.enable_keybert,
                "yake_max_keywords": self.yake_max_keywords,
                "keybert_max_keywords": self.keybert_max_keywords,
                "keybert_model": self.keybert_model,
            }
        }

    def get_memory_constraints(self) -> dict[str, Any]:
        """Get memory constraints for query enhancement"""
        return {
            "technical_level": self.default_technical_level,
            "timeframe": self.default_timeframe,
            "locale": "en-US",  # Could be configurable in the future
            "preferred_sites": [],  # Could be configurable in the future
            "blocked_sites": []  # Could be configurable in the future
        }
