"""Test specifically for the Google 429 rate limiting fix"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from nova.search.engines.google import GoogleSearchClient
from nova.search.models import SearchError


class TestGoogle429Fix:
    """Test that Google 429 errors are properly handled"""

    def setup_method(self):
        """Reset rate limiting state before each test"""
        from nova.search.engines.base import BaseSearchClient

        BaseSearchClient._last_request_times.clear()
        BaseSearchClient._request_counts.clear()
        BaseSearchClient._rate_limit_resets.clear()

    @pytest.mark.asyncio
    async def test_google_429_error_with_retry_after_header(self):
        """Test that Google 429 errors with retry-after header are handled correctly"""
        config = {"api_key": "test-key", "search_engine_id": "test-engine-id"}
        client = GoogleSearchClient(config)

        with patch.object(client, "client") as mock_http_client:
            # First response: 429 with retry-after header
            rate_limit_response = AsyncMock()
            rate_limit_response.status_code = 429
            rate_limit_response.headers = {
                "retry-after": "1"
            }  # Wait 1 second for test speed

            # Second response: successful
            success_response = AsyncMock()
            success_response.status_code = 200
            success_response.json = lambda: {
                "items": [
                    {
                        "title": "Test Result",
                        "link": "https://example.com",
                        "snippet": "Test snippet",
                        "displayLink": "example.com",
                    }
                ],
                "searchInformation": {"totalResults": "1", "searchTime": "0.123"},
            }
            success_response.raise_for_status = AsyncMock()

            # Configure mock to return 429 first, then success on retry
            mock_http_client.get = AsyncMock(
                side_effect=[rate_limit_response, success_response]
            )

            # Should handle 429 and retry successfully
            result = await client.search("test query")

            # Verify the search succeeded after retry
            assert result is not None
            assert result.query == "test query"
            assert len(result.results) == 1
            assert result.results[0].title == "Test Result"
            assert result.results[0].url == "https://example.com"

            # Verify it made exactly 2 requests (original + retry)
            assert mock_http_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_google_429_error_without_retry_after_header(self):
        """Test that Google 429 errors without retry-after use exponential backoff"""
        config = {"api_key": "test-key", "search_engine_id": "test-engine-id"}
        client = GoogleSearchClient(config)

        with patch.object(client, "client") as mock_http_client:
            # First response: 429 without retry-after header
            rate_limit_response = AsyncMock()
            rate_limit_response.status_code = 429
            rate_limit_response.headers = {}  # No retry-after header

            # Second response: successful
            success_response = AsyncMock()
            success_response.status_code = 200
            success_response.json = lambda: {
                "items": [],
                "searchInformation": {"totalResults": "0"},
            }
            success_response.raise_for_status = AsyncMock()

            mock_http_client.get = AsyncMock(
                side_effect=[rate_limit_response, success_response]
            )

            # Should handle 429 with exponential backoff
            result = await client.search("test query")

            # Verify it eventually succeeded
            assert result is not None
            assert mock_http_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_google_search_with_rate_limiting_delays(self):
        """Test that Google search applies proper rate limiting delays between requests"""
        config = {"api_key": "test-key", "search_engine_id": "test-engine-id"}
        client = GoogleSearchClient(config)

        with patch.object(client, "client") as mock_http_client:
            # Mock successful responses
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = lambda: {
                "items": [],
                "searchInformation": {"totalResults": "0"},
            }
            mock_response.raise_for_status = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)

            # First request should be immediate
            await client.search("test query 1")

            # Second request should be delayed by Google's rate limit (1.0s)
            import time

            start_time = time.time()
            await client.search("test query 2")
            elapsed_time = time.time() - start_time

            # Should have waited close to the 1 second minimum delay for Google
            assert elapsed_time >= 0.9  # Allow for small timing variations
            assert mock_http_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_google_multiple_429_errors_exponential_backoff(self):
        """Test that multiple 429 errors use increasing backoff times"""
        config = {"api_key": "test-key", "search_engine_id": "test-engine-id"}
        client = GoogleSearchClient(config)

        with patch.object(client, "client") as mock_http_client:
            # First response: 429 with short retry-after
            first_429 = AsyncMock()
            first_429.status_code = 429
            first_429.headers = {"retry-after": "0.5"}  # Short delay for test

            # Second response: another 429 (simulating persistent rate limiting)
            second_429 = AsyncMock()
            second_429.status_code = 429
            second_429.headers = {"retry-after": "1.0"}  # Longer delay

            # Third response: successful
            success_response = AsyncMock()
            success_response.status_code = 200
            success_response.json = lambda: {
                "items": [],
                "searchInformation": {"totalResults": "0"},
            }
            success_response.raise_for_status = AsyncMock()

            # Configure responses: 429, 429, success
            mock_http_client.get = AsyncMock(
                side_effect=[first_429, second_429, success_response]
            )

            # Should handle multiple 429 errors and eventually succeed
            result = await client.search("test query")

            assert result is not None
            # Should have made 3 requests (original + 2 retries)
            assert mock_http_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_google_non_429_errors_not_retried(self):
        """Test that non-429 errors are not retried"""
        config = {"api_key": "test-key", "search_engine_id": "test-engine-id"}
        client = GoogleSearchClient(config)

        with patch.object(client, "client") as mock_http_client:
            # Mock a 500 server error
            error_response = AsyncMock()
            error_response.status_code = 500
            error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500 Server Error", request=None, response=error_response
            )
            mock_http_client.get = AsyncMock(return_value=error_response)

            # Should raise SearchError without retry
            with pytest.raises(SearchError) as exc_info:
                await client.search("test query")

            assert "Google search failed" in str(exc_info.value)
            # Should have made only 1 request (no retry for non-429 errors)
            assert mock_http_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_rate_limiting_state_persists_across_instances(self):
        """Test that rate limiting state is shared across client instances"""
        config = {"api_key": "test-key", "search_engine_id": "test-engine-id"}

        # Create two separate client instances
        client1 = GoogleSearchClient(config)
        client2 = GoogleSearchClient(config)

        with (
            patch.object(client1, "client") as mock_client1,
            patch.object(client2, "client") as mock_client2,
        ):
            # Mock successful responses
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = lambda: {
                "items": [],
                "searchInformation": {"totalResults": "0"},
            }
            mock_response.raise_for_status = AsyncMock()

            mock_client1.get = AsyncMock(return_value=mock_response)
            mock_client2.get = AsyncMock(return_value=mock_response)

            # First request with client1
            await client1.search("test query 1")

            # Second request with client2 should be rate limited
            import time

            start_time = time.time()
            await client2.search("test query 2")
            elapsed_time = time.time() - start_time

            # Should have been rate limited despite using different client instance
            assert elapsed_time >= 0.9  # Google's 1.0s delay

            # Both clients should have made requests
            assert mock_client1.get.call_count == 1
            assert mock_client2.get.call_count == 1
