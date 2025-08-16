# Nova Search Module

The Nova search module provides a pluggable architecture for web search engines. It supports multiple search providers and makes it easy to add new ones.

## Architecture

```
nova/search/
├── __init__.py          # Main module exports
├── models.py            # Data models (SearchResult, SearchResponse, SearchError)
├── manager.py           # SearchManager - coordinates multiple engines
├── content.py           # Content extraction and summarization
├── engines/             # Search engine implementations
│   ├── __init__.py      # Engine registry and factory functions
│   ├── base.py          # BaseSearchEngine abstract class
│   ├── duckduckgo.py    # DuckDuckGo engine (no API key needed)
│   ├── google.py        # Google Custom Search engine
│   ├── bing.py          # Microsoft Bing Search engine
│   └── example_engine.py # Template for new engines
└── README.md           # This file
```

## Currently Supported Engines

### DuckDuckGo (default)
- **No API key required**
- Uses HTML scraping of DuckDuckGo search results
- Always available as fallback

### Google Custom Search
- Requires Google API key and Custom Search Engine ID
- Configured via `search.google.api_key` and `search.google.search_engine_id`
- High quality results with good metadata

### Microsoft Bing
- Requires Bing Search API key
- Configured via `search.bing.api_key`
- Supports rich metadata including publication dates

## Usage

### Basic Usage

```python
from nova.search import SearchManager

# Initialize search manager
config = {
    "search": {
        "google": {
            "api_key": "your-google-api-key",
            "search_engine_id": "your-search-engine-id"
        },
        "bing": {
            "api_key": "your-bing-api-key"
        }
    }
}

search_manager = SearchManager(config)

# Perform search
results = await search_manager.search(
    query="Python web scraping",
    provider="google",  # Optional, will auto-select if not specified
    max_results=5,
    extract_content=True  # Extract full webpage content
)

# Close when done
await search_manager.close()
```

### Synchronous Wrapper

```python
from nova.search import search_web

# Synchronous search (handles async internally)
results = search_web(
    config=config,
    query="Python web scraping",
    provider="google",
    max_results=5
)
```

### Available Functions

```python
from nova.search import get_search_engine, list_search_engines

# Get available engine names
engines = list_search_engines()
# Returns: ['duckduckgo', 'google', 'bing']

# Create engine instance directly
engine = get_search_engine("duckduckgo", {})
```

## Adding a New Search Engine

To add a new search engine, follow these steps:

### 1. Create Engine Implementation

Create a new file in `nova/search/engines/` (e.g., `yandex.py`):

```python
"""Yandex search engine implementation"""

import logging
from datetime import datetime

from .base import BaseSearchEngine
from ..models import SearchResult, SearchResponse, SearchError

logger = logging.getLogger(__name__)

class YandexEngine(BaseSearchEngine):
    """Yandex search engine implementation"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.base_url = "https://api.yandex.com/search"

    def validate_config(self) -> bool:
        """Validate Yandex configuration"""
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 10, **kwargs) -> SearchResponse:
        """Perform Yandex search"""
        start_time = datetime.now()

        if not self.validate_config():
            raise SearchError("Yandex API key required")

        # Implement your search logic here
        # See engines/example_engine.py for detailed template

        # Return SearchResponse with results
        return SearchResponse(
            query=query,
            results=results,
            total_results=len(results),
            search_time_ms=search_time,
            provider="Yandex",
        )
```

### 2. Register the Engine

Add your engine to `nova/search/engines/__init__.py`:

```python
from .yandex import YandexEngine

# Add to SEARCH_ENGINES registry
SEARCH_ENGINES = {
    "duckduckgo": DuckDuckGoEngine,
    "google": GoogleEngine,
    "bing": BingEngine,
    "yandex": YandexEngine,  # Add this line
}
```

### 3. Configure in Nova

Add configuration to your Nova config file:

```yaml
search:
  yandex:
    api_key: "your-yandex-api-key"
```

### 4. Use Your Engine

```python
from nova.search import SearchManager

config = {
    "search": {
        "yandex": {
            "api_key": "your-yandex-api-key"
        }
    }
}

search_manager = SearchManager(config)
results = await search_manager.search("test query", provider="yandex")
```

## Configuration

Search engines are configured in the main Nova configuration under the `search` key:

```yaml
search:
  google:
    api_key: "your-google-api-key"
    search_engine_id: "your-search-engine-id"
  bing:
    api_key: "your-bing-api-key"
```

## Error Handling

The search module uses a specific `SearchError` exception for search-related failures:

```python
from nova.search import SearchError

try:
    results = await search_manager.search("query")
except SearchError as e:
    print(f"Search failed: {e}")
```

## Content Extraction

The search module can automatically extract full webpage content from search results:

```python
# Enable content extraction
results = await search_manager.search(
    "query",
    extract_content=True,
    ai_client=your_ai_client  # Optional: for AI-powered summarization
)

# Access extracted content
for result in results.results:
    if result.extraction_success:
        print(f"Full content: {result.full_content}")
        print(f"AI summary: {result.content_summary}")
```

## Testing

Tests are located in:
- `tests/unit/test_search.py` - Core search functionality
- `tests/unit/test_search_content_summarizer.py` - Content extraction and summarization
- `tests/unit/test_tools_web_search.py` - Web search tool integration

Run tests with:
```bash
uv run pytest tests/unit/test_search*.py -v
```
