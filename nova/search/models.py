"""Search-specific models and data structures"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Individual search result"""

    title: str = Field(description="Title of the search result")
    url: str = Field(description="URL of the search result")
    snippet: str = Field(description="Brief description/snippet of the content")
    source: str = Field(description="Source website domain")
    published_date: datetime | None = Field(
        default=None, description="Publication date if available"
    )
    full_content: str | None = Field(
        default=None, description="Full extracted webpage content"
    )
    content_summary: str | None = Field(
        default=None, description="AI-generated summary of the content"
    )
    extraction_success: bool = Field(
        default=False, description="Whether content extraction was successful"
    )


class SearchResponse(BaseModel):
    """Complete search response with metadata"""

    query: str = Field(description="Original search query")
    results: list[SearchResult] = Field(description="List of search results")
    total_results: int = Field(description="Total number of results found")
    search_time_ms: int = Field(description="Time taken for search in milliseconds")
    provider: str = Field(description="Search provider used")


class SearchEnhancementMode(str, Enum):
    """Available search enhancement modes"""

    AUTO = "auto"  # Automatically choose best enhancement
    DISABLED = "disabled"  # No enhancement, direct search
    FAST = "fast"  # YAKE-only enhancement (~50ms)
    SEMANTIC = "semantic"  # KeyBERT semantic analysis (~200-500ms)
    HYBRID = "hybrid"  # Combined YAKE + KeyBERT (~300-600ms)
    ADAPTIVE = "adaptive"  # Choose based on query complexity


class KeywordResult(BaseModel):
    """Individual keyword extraction result"""

    keyword: str = Field(description="Extracted keyword or phrase")
    score: float = Field(description="Relevance score")
    type: str = Field(description="Type of keyword (entity, technical, general)")
    source: str = Field(description="Extraction method (yake, keybert, spacy)")


class TermClassification(BaseModel):
    """Classification of extracted terms"""

    must_have_terms: list[str] = Field(
        description="Critical terms that must appear in search"
    )
    nice_to_have_terms: list[str] = Field(
        description="Optional terms that improve relevance"
    )
    entities: list[str] = Field(description="Named entities found")
    technical_terms: list[str] = Field(description="Technical terms or jargon")


class SearchMemoryConstraints(BaseModel):
    """User preferences and memory constraints for search"""

    preferred_sites: list[str] = Field(
        default_factory=list, description="Preferred websites"
    )
    blocked_sites: list[str] = Field(
        default_factory=list, description="Blocked websites"
    )
    locale: str = Field(default="en-US", description="Search locale preference")
    technical_level: str = Field(
        default="intermediate", description="Technical complexity level"
    )
    timeframe: str = Field(default="any", description="Time preference for results")


class EnhancedSearchQuery(BaseModel):
    """Single enhanced search query with metadata"""

    query: str = Field(description="The search query string")
    priority: int = Field(description="Query priority (1=highest)")
    expected_results: int = Field(description="Expected number of results")
    rationale: str = Field(description="Why this query was generated")


class EnhancedSearchPlan(BaseModel):
    """Complete search plan with multiple optimized queries"""

    original_query: str = Field(description="Original user query")
    enhanced_queries: list[EnhancedSearchQuery] = Field(
        description="Generated search queries"
    )
    extraction_details: dict[str, Any] = Field(description="Keyword extraction details")
    enhancement_mode: SearchEnhancementMode = Field(description="Enhancement mode used")
    processing_time_ms: int = Field(description="Time taken for enhancement")
    context_used: bool = Field(description="Whether conversation context was used")


class SearchError(Exception):
    """Search-related errors"""

    pass
