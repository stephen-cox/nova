"""Tests for search engine rate limiting functionality"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from nova.search.engines.bing import BingSearchClient
from nova.search.engines.duckduckgo import DuckDuckGoSearchClient
from nova.search.engines.google import GoogleSearchClient


class TestSearchRateLimiting:
    """Test rate limiting functionality in search engines"""

    def setup_method(self):
        """Reset rate limiting state before each test"""
        # Clear class-level rate limiting state
        from nova.search.engines.base import BaseSearchClient

        BaseSearchClient._last_request_times.clear()
        BaseSearchClient._request_counts.clear()
        BaseSearchClient._rate_limit_resets.clear()

    @pytest.mark.asyncio
    async def test_google_rate_limiting_delay(self):
        """Test that Google search client enforces minimum delay between requests"""
        config = {"api_key": "test-key", "search_engine_id": "test-engine-id"}
        client = GoogleSearchClient(config)

        # Mock successful responses
        with patch.object(client, "client") as mock_http_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "items": [],
                "searchInformation": {"totalResults": "0"},
            }
            mock_response.raise_for_status = AsyncMock()
            mock_http_client.get.return_value = mock_response

            # First request should be immediate
            start_time = time.time()
            await client.search("test query 1")
            first_request_time = time.time() - start_time

            # Second request should be delayed (Google has 1.0s minimum delay)
            start_time = time.time()
            await client.search("test query 2")
            second_request_time = time.time() - start_time

            # Second request should take at least close to the minimum delay
            assert second_request_time >= 0.9  # Allow for small timing variations
            assert first_request_time < 0.1  # First request should be fast

    @pytest.mark.asyncio
    async def test_duckduckgo_rate_limiting_faster(self):
        """Test that DuckDuckGo has shorter delays than Google"""
        config = {}
        client = DuckDuckGoSearchClient(config)

        # Mock successful HTML response
        with patch.object(client, "client") as mock_http_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body><div class='result'></div></body></html>"
            mock_response.raise_for_status = AsyncMock()
            mock_http_client.get.return_value = mock_response

            # Mock the HTML parsing to return empty results
            with patch.object(client, "_parse_duckduckgo_html", return_value=[]):
                # First request
                start_time = time.time()
                await client.search("test query 1")
                first_request_time = time.time() - start_time

                # Second request should have shorter delay than Google (0.3s for DDG)
                start_time = time.time()
                await client.search("test query 2")
                second_request_time = time.time() - start_time

                # DDG should have shorter delay than Google
                assert second_request_time >= 0.25  # Allow for timing variations
                assert second_request_time < 0.8  # Should be less than Google's 1.0s

    @pytest.mark.asyncio
    async def test_429_error_handling(self):
        """Test that 429 rate limit errors are handled with exponential backoff"""
        config = {"api_key": "test-key", "search_engine_id": "test-engine-id"}
        client = GoogleSearchClient(config)

        with patch.object(client, "client") as mock_http_client:
            # First response: 429 rate limit error
            rate_limit_response = AsyncMock()
            rate_limit_response.status_code = 429
            rate_limit_response.headers = {"retry-after": "2.0"}

            # Second response: successful
            success_response = AsyncMock()
            success_response.status_code = 200
            success_response.json.return_value = {
                "items": [],
                "searchInformation": {"totalResults": "0"},
            }
            success_response.raise_for_status = AsyncMock()

            # Mock to return 429 first, then success
            mock_http_client.get.side_effect = [rate_limit_response, success_response]

            # Should handle 429 and retry successfully
            start_time = time.time()
            result = await client.search("test query")
            elapsed_time = time.time() - start_time

            # Should have waited for the retry-after time
            assert elapsed_time >= 2.0  # Should wait at least the retry-after time
            assert result is not None
            assert mock_http_client.get.call_count == 2  # Should retry once

    @pytest.mark.asyncio
    async def test_429_error_without_retry_after_header(self):
        """Test 429 handling when no retry-after header is provided"""
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
            success_response.json.return_value = {
                "items": [],
                "searchInformation": {"totalResults": "0"},
            }
            success_response.raise_for_status = AsyncMock()

            mock_http_client.get.side_effect = [rate_limit_response, success_response]

            # Should handle 429 with default exponential backoff
            start_time = time.time()
            result = await client.search("test query")
            elapsed_time = time.time() - start_time

            # Should use exponential backoff (starts at 30s, but we should see some delay)
            # Note: In test we expect it to use exponential backoff
            assert elapsed_time >= 25.0  # Should wait for exponential backoff
            assert result is not None

    @pytest.mark.asyncio
    async def test_concurrent_requests_different_providers(self):
        """Test that different providers have independent rate limiting"""
        google_config = {"api_key": "test-key", "search_engine_id": "test-engine-id"}
        google_client = GoogleSearchClient(google_config)
        ddg_client = DuckDuckGoSearchClient({})

        with (
            patch.object(google_client, "client") as mock_google_client,
            patch.object(ddg_client, "client") as mock_ddg_client,
        ):
            # Mock responses
            google_response = AsyncMock()
            google_response.status_code = 200
            google_response.json.return_value = {
                "items": [],
                "searchInformation": {"totalResults": "0"},
            }
            google_response.raise_for_status = AsyncMock()
            mock_google_client.get.return_value = google_response

            ddg_response = AsyncMock()
            ddg_response.status_code = 200
            ddg_response.text = "<html><body></body></html>"
            ddg_response.raise_for_status = AsyncMock()
            mock_ddg_client.get.return_value = ddg_response

            with patch.object(ddg_client, "_parse_duckduckgo_html", return_value=[]):
                # Both should be able to make requests concurrently
                start_time = time.time()
                await asyncio.gather(
                    google_client.search("test query"), ddg_client.search("test query")
                )
                elapsed_time = time.time() - start_time

                # Should complete relatively quickly since they're independent
                assert elapsed_time < 2.0  # Should not be significantly delayed

    @pytest.mark.asyncio
    async def test_rate_limit_configuration(self):
        """Test that different providers have correct rate limit configurations"""
        google_client = GoogleSearchClient(
            {"api_key": "test", "search_engine_id": "test"}
        )
        ddg_client = DuckDuckGoSearchClient({})
        bing_client = BingSearchClient({"api_key": "test"})

        # Test rate limit configurations
        google_delay, google_max = google_client._get_rate_limit_config()
        ddg_delay, ddg_max = ddg_client._get_rate_limit_config()
        bing_delay, bing_max = bing_client._get_rate_limit_config()

        # Google should be most restrictive
        assert google_delay == 1.0
        assert google_max == 100

        # DuckDuckGo should be most lenient
        assert ddg_delay == 0.3
        assert ddg_max == 300

        # Bing should be in between
        assert bing_delay == 0.5
        assert bing_max == 200

        # Verify ordering: Google most restrictive, DDG most lenient
        assert google_delay > bing_delay > ddg_delay
        assert ddg_max > bing_max > google_max

    @pytest.mark.asyncio
    async def test_request_count_limiting(self):
        """Test that request count limits are enforced"""
        config = {}
        client = DuckDuckGoSearchClient(config)

        # Force very low rate limit for testing
        original_method = client._get_rate_limit_config

        def mock_rate_limit_config():
            return (0.1, 2)  # Allow only 2 requests per minute

        client._get_rate_limit_config = mock_rate_limit_config

        with patch.object(client, "client") as mock_http_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body></body></html>"
            mock_response.raise_for_status = AsyncMock()
            mock_http_client.get.return_value = mock_response

            with patch.object(client, "_parse_duckduckgo_html", return_value=[]):
                # First two requests should work
                await client.search("query 1")
                await client.search("query 2")

                # Third request should be delayed significantly (waiting for reset)
                start_time = time.time()
                await client.search("query 3")
                elapsed_time = time.time() - start_time

                # Should wait for rate limit reset
                assert elapsed_time >= 50.0  # Should wait most of a minute for reset

    @pytest.mark.asyncio
    async def test_provider_name_tracking(self):
        """Test that provider names are correctly tracked for rate limiting"""
        google_client = GoogleSearchClient(
            {"api_key": "test", "search_engine_id": "test"}
        )
        ddg_client = DuckDuckGoSearchClient({})
        bing_client = BingSearchClient({"api_key": "test"})

        assert google_client.provider_name == "GoogleSearchClient"
        assert ddg_client.provider_name == "DuckDuckGoSearchClient"
        assert bing_client.provider_name == "BingSearchClient"
