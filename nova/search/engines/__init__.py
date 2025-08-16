"""Search engines for Nova"""

from .base import BaseSearchEngine
from .bing import BingEngine
from .duckduckgo import DuckDuckGoEngine
from .google import GoogleEngine

# Registry of available search engines
SEARCH_ENGINES = {
    "duckduckgo": DuckDuckGoEngine,
    "google": GoogleEngine,
    "bing": BingEngine,
}


def get_search_engine(name: str, config: dict):
    """Get a search engine instance by name"""
    if name not in SEARCH_ENGINES:
        raise ValueError(
            f"Unknown search engine: {name}. Available: {list(SEARCH_ENGINES.keys())}"
        )

    return SEARCH_ENGINES[name](config)


def list_search_engines():
    """List all available search engines"""
    return list(SEARCH_ENGINES.keys())


__all__ = [
    "BaseSearchEngine",
    "DuckDuckGoEngine",
    "GoogleEngine",
    "BingEngine",
    "SEARCH_ENGINES",
    "get_search_engine",
    "list_search_engines",
]
