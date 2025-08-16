"""Nova search module with pluggable search engines"""

from .content import ContentSummarizer
from .engines import get_search_engine, list_search_engines
from .manager import SearchManager, search_web
from .models import SearchError, SearchResponse, SearchResult

__all__ = [
    "SearchManager",
    "search_web",
    "SearchResult",
    "SearchResponse",
    "SearchError",
    "ContentSummarizer",
    "get_search_engine",
    "list_search_engines",
]
