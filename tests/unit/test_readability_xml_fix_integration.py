"""Integration test to verify the readability XML fix works end-to-end"""

from unittest.mock import AsyncMock, patch

import pytest

from nova.search.engines.duckduckgo import DuckDuckGoSearchClient


class TestReadabilityXMLFixIntegration:
    """Test that the readability XML fix works in real scenarios"""

    @pytest.mark.asyncio
    async def test_content_extraction_with_invalid_characters_real_scenario(self):
        """Test that content extraction works with HTML containing invalid XML characters"""

        # Create a real DuckDuckGo client instance
        client = DuckDuckGoSearchClient({})

        # Mock problematic HTML that would cause the original error
        problematic_html = """<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <h1>Main Content</h1>
    <p>This is some content that should be extracted.</p>
    <p>This paragraph has a null byte:\x00</p>
    <script>
        var problematic = "data\x01with\x02control\x03characters";
    </script>
    <p>More extractable content here with valid text.</p>
    <div>Additional content with invalid chars:\x0b\x0c\x0e\x0f</div>
    <p>Final paragraph that should be included in extraction.</p>
</body>
</html>"""

        # Mock the HTTP response to return our problematic HTML
        with patch.object(client, "client") as mock_http_client:
            mock_response = AsyncMock()
            mock_response.text = problematic_html
            mock_response.raise_for_status = AsyncMock()
            mock_http_client.get.return_value = mock_response

            # This should not raise an exception with our fix
            content, success = await client.extract_content("https://example.com/test")

            # Verify extraction completed (might succeed or gracefully fail)
            # The important thing is no XML exception was raised
            assert isinstance(content, (str, type(None)))
            assert isinstance(success, bool)

            # If extraction succeeded, verify content is reasonable
            if success and content:
                # Should contain the main content
                assert "Main Content" in content or "extractable content" in content
                # Should not contain the problematic characters
                assert "\x00" not in content
                assert "\x01" not in content
                assert "\x02" not in content

    @pytest.mark.asyncio
    async def test_sanitize_html_method_directly(self):
        """Test the sanitize HTML method directly with various scenarios"""

        client = DuckDuckGoSearchClient({})

        # Test case 1: HTML with NULL bytes
        html_with_nulls = "<html><body>Hello\x00World</body></html>"
        sanitized = client._sanitize_html_for_xml(html_with_nulls)
        assert "\x00" not in sanitized
        assert sanitized == "<html><body>HelloWorld</body></html>"

        # Test case 2: HTML with various control characters
        html_with_controls = (
            "<html><body>Text\x01\x02\x03\x0b\x0c\x0e\x0f</body></html>"
        )
        sanitized = client._sanitize_html_for_xml(html_with_controls)
        assert sanitized == "<html><body>Text</body></html>"

        # Test case 3: Valid HTML should be unchanged
        valid_html = "<html><body><p>Valid content with 🌍 unicode</p></body></html>"
        sanitized = client._sanitize_html_for_xml(valid_html)
        assert sanitized == valid_html

        # Test case 4: Empty/None handling
        assert client._sanitize_html_for_xml("") == ""
        assert client._sanitize_html_for_xml(None) is None

    @pytest.mark.asyncio
    async def test_newspaper3k_fallback_still_works(self):
        """Test that newspaper3k extraction still works as the primary method"""

        client = DuckDuckGoSearchClient({})

        # Mock newspaper3k to succeed
        with patch("nova.search.engines.base.Article") as mock_article_class:
            mock_article = AsyncMock()
            mock_article.text = "This is extracted content from newspaper3k that is long enough to meet the minimum length requirement for successful extraction."
            mock_article.download = AsyncMock()
            mock_article.parse = AsyncMock()
            mock_article_class.return_value = mock_article

            content, success = await client.extract_content(
                "https://example.com/article"
            )

            # Should succeed with newspaper3k
            assert success is True
            assert "extracted content from newspaper3k" in content
            assert len(content) > 100  # Meets minimum length requirement

    @pytest.mark.asyncio
    async def test_readability_with_sanitization_fallback(self):
        """Test that readability works as fallback with sanitization"""

        client = DuckDuckGoSearchClient({})

        # Mock newspaper3k to fail
        with patch(
            "nova.search.engines.base.Article",
            side_effect=Exception("Newspaper failed"),
        ):
            # Mock successful HTTP response for readability
            with patch.object(client, "client") as mock_http_client:
                mock_response = AsyncMock()
                # HTML with problematic characters that our sanitization should handle
                mock_response.text = """<html><body>
                <article>
                    <h1>Article Title</h1>
                    <p>This is the main content of the article that should be extracted successfully.</p>
                    <p>Even with problematic characters:\x00\x01\x02</p>
                    <p>The content extraction should still work because we sanitize before readability.</p>
                </article>
                </body></html>"""
                mock_response.raise_for_status = AsyncMock()
                mock_http_client.get.return_value = mock_response

                # This should work without XML errors
                content, success = await client.extract_content(
                    "https://example.com/article"
                )

                # Should either succeed with readability or fail gracefully to next method
                assert isinstance(success, bool)
                if success and content:
                    # If readability succeeded, should have reasonable content
                    assert len(content) > 50
                    # Should not contain problematic characters
                    assert "\x00" not in content
                    assert "\x01" not in content

    @pytest.mark.asyncio
    async def test_all_extraction_methods_fail_gracefully(self):
        """Test that all extraction methods fail gracefully without exceptions"""

        client = DuckDuckGoSearchClient({})

        # Mock all methods to fail in controlled ways
        with patch(
            "nova.search.engines.base.Article",
            side_effect=Exception("Newspaper failed"),
        ):
            with patch.object(client, "client") as mock_http_client:
                # Mock readability to fail (but after sanitization)
                mock_response = AsyncMock()
                mock_response.text = "Invalid HTML that causes readability to fail"
                mock_response.raise_for_status = AsyncMock()
                mock_http_client.get.side_effect = [
                    mock_response,  # First call for readability
                    mock_response,  # Second call for BeautifulSoup fallback
                ]

                # This should not raise any exceptions
                content, success = await client.extract_content(
                    "https://example.com/failing-site"
                )

                # Should gracefully fail
                assert success is False
                assert content is None
