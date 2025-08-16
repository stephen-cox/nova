# Integration Tests

This directory contains integration tests that make real API calls and require network connectivity.

## Search Integration Tests

The `test_search_integration.py` file contains tests that verify search functionality returns real results from search providers.

### Running Search Integration Tests

```bash
# Run all search integration tests
uv run pytest tests/integration/test_search_integration.py -v

# Run specific test
uv run pytest tests/integration/test_search_integration.py::TestSearchIntegration::test_duckduckgo_real_search -v

# Run only integration tests (skip unit tests)
uv run pytest -m integration

# Skip integration tests (run only unit tests)
uv run pytest -m "not integration"
```

### Test Coverage

**DuckDuckGo Engine (No API Key Required):**
- ✅ Real search results verification
- ✅ Response structure validation
- ✅ Result content relevance checking
- ✅ Multiple results quality verification
- ✅ Error handling with invalid providers

**Google Search Engine (Requires API Key):**
- ⚠️ Skipped unless `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_CX` environment variables are set
- ✅ Real API calls when configured
- ✅ Result quality verification

**Bing Search Engine (Requires API Key):**
- ⚠️ Skipped unless `BING_SEARCH_API_KEY` environment variable is set
- ✅ Real API calls when configured
- ✅ Result quality verification

**Web Search Tool:**
- ✅ Tool wrapper function testing
- ✅ Provider selection verification
- ✅ Max results limit testing
- ✅ Query variation testing with different query types

### What These Tests Verify

1. **Real Search Results**: Tests confirm that searches return actual results from search providers
2. **Response Structure**: Validates that responses contain expected fields (title, URL, snippet, source)
3. **Content Relevance**: Checks that search results are relevant to the search query
4. **URL Validity**: Ensures returned URLs are properly formatted HTTP/HTTPS links
5. **Result Diversity**: Verifies that multiple results have unique URLs
6. **Error Handling**: Tests proper error handling for invalid providers and edge cases
7. **Tool Integration**: Confirms the web_search tool works with real search providers

### API Key Configuration

To run tests for Google and Bing search providers, set these environment variables:

```bash
# Google Search
export GOOGLE_SEARCH_API_KEY="your_google_api_key"
export GOOGLE_SEARCH_CX="your_custom_search_engine_id"

# Bing Search
export BING_SEARCH_API_KEY="your_bing_api_key"
```

Without these keys, the respective tests will be skipped.

### Performance Notes

Integration tests make real network requests and may take longer to run than unit tests. They are marked with `@pytest.mark.integration` for easy filtering.
