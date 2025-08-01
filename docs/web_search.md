# Web Search Feature

Nova includes built-in web search functionality that allows you to search the internet directly from within chat sessions. This feature supports multiple search providers and integrates seamlessly with the conversational interface.

## Features

- **Multiple Search Providers**: Support for DuckDuckGo, Google Custom Search, and Bing Search API
- **Chat Integration**: Use `/search` commands directly in chat sessions
- **Rich Formatting**: Search results are displayed with markdown formatting including titles, links, and snippets
- **Configurable**: Customize search providers, result limits, and behavior through configuration

## Quick Start

### Basic Usage

In a chat session, use the `/search` command:

```
You: /search Python web frameworks
```

This will search using the default provider (DuckDuckGo) and display formatted results.

### Advanced Usage

```bash
# Search with specific provider
/search machine learning --provider google

# Limit number of results
/search AI news --max 3

# Combine options
/search blockchain technology --provider bing --max 5
```

## Configuration

### Default Configuration

Nova works out-of-the-box with DuckDuckGo (no API keys required):

```yaml
search:
  enabled: true
  default_provider: "duckduckgo"
  max_results: 5
  google: {}
  bing: {}
```

### Adding Google Custom Search

1. Get a Google Custom Search API key:
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Enable the Custom Search API
   - Create credentials (API key)

2. Create a Custom Search Engine:
   - Go to [Google Custom Search](https://cse.google.com/)
   - Create a new search engine
   - Note the Search Engine ID

3. Configure Nova:

```yaml
search:
  enabled: true
  default_provider: "google"
  max_results: 10
  google:
    api_key: "your-google-api-key"
    search_engine_id: "your-search-engine-id"
```

Or set environment variables:
```bash
export GOOGLE_SEARCH_API_KEY="your-google-api-key"
export GOOGLE_SEARCH_ENGINE_ID="your-search-engine-id"
```

### Adding Bing Search

1. Get a Bing Search API key:
   - Visit [Azure Portal](https://portal.azure.com/)
   - Create a Bing Search resource
   - Get the API key from the resource

2. Configure Nova:

```yaml
search:
  enabled: true
  default_provider: "bing"
  max_results: 10
  bing:
    api_key: "your-bing-api-key"
```

Or set environment variable:
```bash
export BING_SEARCH_API_KEY="your-bing-api-key"
```

## Chat Commands

### `/search <query>`
Perform a web search with the default provider and settings.

**Example:**
```
/search Python asyncio tutorial
```

### `/search <query> --provider <provider>`
Search with a specific provider (duckduckgo, google, or bing).

**Example:**
```
/search latest AI research --provider google
```

### `/search <query> --max <number>`
Limit the number of search results (1-50).

**Example:**
```
/search machine learning frameworks --max 3
```

### Combined Options
You can combine provider and result limit options:

```
/search quantum computing --provider bing --max 8
```

## Search Result Format

Search results are displayed in a rich markdown format:

```markdown
## 🔍 Search Results for: Python web frameworks

Found 1,234,567 results in 245ms using Google

### 1. [Django Web Framework](https://djangoproject.com/)
**djangoproject.com**

Django is a high-level Python web framework that encourages rapid development
and clean, pragmatic design. Built by experienced developers...

*Published: 2024-01-15*

---

### 2. [Flask - Web Development](https://flask.palletsprojects.com/)
**flask.palletsprojects.com**

Flask is a lightweight WSGI web application framework. It is designed to make
getting started quick and easy, with the ability to scale up...

---
```

## Programmatic Usage

You can also use the search functionality programmatically:

```python
from nova.core.search import search_web
from nova.utils.formatting import print_search_results

# Configure search
config = {
    "search": {
        "google": {
            "api_key": "your-api-key",
            "search_engine_id": "your-cx-id"
        }
    }
}

# Perform search
response = search_web(
    config=config,
    query="Python best practices",
    provider="google",
    max_results=5
)

# Display results
print_search_results(response)

# Or access results programmatically
for result in response.results:
    print(f"Title: {result.title}")
    print(f"URL: {result.url}")
    print(f"Snippet: {result.snippet}")
    print(f"Source: {result.source}")
    if result.published_date:
        print(f"Published: {result.published_date}")
    print("---")
```

## Search Providers

### DuckDuckGo
- **API Key Required**: No
- **Rate Limits**: Reasonable for personal use
- **Features**: Privacy-focused, no tracking
- **Reliability**: Good for general searches

### Google Custom Search
- **API Key Required**: Yes
- **Rate Limits**: 100 queries/day (free tier)
- **Features**: High-quality results, rich metadata
- **Reliability**: Excellent

### Bing Search API
- **API Key Required**: Yes
- **Rate Limits**: 3,000 queries/month (free tier)
- **Features**: Good coverage, date information
- **Reliability**: Very good

## Troubleshooting

### Search is Disabled
If you see "Web search is disabled in configuration":

1. Check your configuration file
2. Ensure `search.enabled: true`
3. Restart Nova after configuration changes

### No Results Found
- Try different search terms
- Check if the provider is working (try a different one)
- Verify API keys are correct

### API Key Errors
- **Google**: Verify both API key and Search Engine ID are correct
- **Bing**: Ensure the API key is from a Bing Search resource
- Check that APIs are enabled in respective consoles

### Rate Limiting
If you hit rate limits:
- Switch to a different provider temporarily
- Consider upgrading to paid tiers for higher limits
- DuckDuckGo doesn't have strict rate limits

## Privacy Considerations

- **DuckDuckGo**: Privacy-focused, doesn't track users
- **Google**: May log searches (see Google's privacy policy)
- **Bing**: May log searches (see Microsoft's privacy policy)

When using Nova's search feature, your queries are sent to the selected search provider. Consider using DuckDuckGo for privacy-sensitive searches.

## Contributing

The search system is extensible. To add a new search provider:

1. Create a new client class inheriting from `BaseSearchClient`
2. Implement the required methods (`search`, `validate_config`)
3. Add configuration support in `SearchConfig`
4. Register the provider in `SearchManager`
5. Add tests for the new provider

See `nova/core/search.py` for implementation details.
