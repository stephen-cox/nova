"""Search-related data models"""

from datetime import datetime

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


class SearchError(Exception):
    """Search-related errors"""

    pass
