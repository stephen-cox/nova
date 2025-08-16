"""Tests for HTML sanitization in content extraction"""

from nova.search.engines.base import BaseSearchClient
from nova.search.models import SearchResponse


class TestSearchClient(BaseSearchClient):
    """Concrete implementation of BaseSearchClient for testing"""

    async def search(
        self, query: str, max_results: int = 10, **kwargs
    ) -> SearchResponse:
        """Dummy implementation for testing"""
        return SearchResponse(
            query=query, results=[], total_results=0, search_time_ms=0, provider="test"
        )

    def validate_config(self) -> bool:
        """Dummy implementation for testing"""
        return True


class TestHTMLSanitization:
    """Test HTML sanitization for XML compatibility"""

    def test_sanitize_html_removes_null_bytes(self):
        """Test that NULL bytes are removed from HTML content"""
        client = TestSearchClient({})

        # HTML with NULL bytes (common cause of XML errors)
        html_with_nulls = "<!DOCTYPE html><html><body>Hello\x00World\x00</body></html>"

        sanitized = client._sanitize_html_for_xml(html_with_nulls)

        # Verify NULL bytes are removed
        assert "\x00" not in sanitized
        assert sanitized == "<!DOCTYPE html><html><body>HelloWorld</body></html>"

    def test_sanitize_html_removes_control_characters(self):
        """Test that invalid control characters are removed"""
        client = TestSearchClient({})

        # HTML with various control characters that break XML
        html_with_controls = (
            "<!DOCTYPE html><html><body>Text\x01\x02\x03\x0b\x0c\x0e\x0f</body></html>"
        )

        sanitized = client._sanitize_html_for_xml(html_with_controls)

        # Verify control characters are removed but valid content remains
        assert sanitized == "<!DOCTYPE html><html><body>Text</body></html>"
        # Ensure no invalid control characters remain
        for char in sanitized:
            code = ord(char)
            assert code not in [0x01, 0x02, 0x03, 0x0B, 0x0C, 0x0E, 0x0F]

    def test_sanitize_html_preserves_valid_characters(self):
        """Test that valid XML characters are preserved"""
        client = TestSearchClient({})

        # HTML with valid characters including tabs, newlines, and unicode
        valid_html = """<!DOCTYPE html>
<html>
<head>
\t<title>Test Page</title>
</head>
<body>
\t<p>Hello World! 🌍</p>
\t<p>Testing unicode: café, naïve, résumé</p>
\r\n\t<div>Tab and newline preserved</div>
</body>
</html>"""

        sanitized = client._sanitize_html_for_xml(valid_html)

        # Valid content should be unchanged
        assert sanitized == valid_html

    def test_sanitize_html_handles_empty_content(self):
        """Test handling of empty or None content"""
        client = TestSearchClient({})

        # Test empty string
        assert client._sanitize_html_for_xml("") == ""

        # Test None (should not crash)
        assert client._sanitize_html_for_xml(None) is None

    def test_sanitize_html_handles_unicode_properly(self):
        """Test that Unicode characters are handled correctly"""
        client = TestSearchClient({})

        # HTML with various Unicode characters
        unicode_html = """<html><body>
        <p>English: Hello</p>
        <p>Spanish: Hola</p>
        <p>French: Bonjour</p>
        <p>German: Guten Tag</p>
        <p>Chinese: 你好</p>
        <p>Japanese: こんにちは</p>
        <p>Arabic: مرحبا</p>
        <p>Emoji: 👋🌍🚀</p>
        </body></html>"""

        sanitized = client._sanitize_html_for_xml(unicode_html)

        # Unicode content should be preserved
        assert "你好" in sanitized
        assert "こんにちは" in sanitized
        assert "مرحبا" in sanitized
        assert "👋🌍🚀" in sanitized

    def test_sanitize_html_real_world_scenario(self):
        """Test with content similar to what might cause the DuckDuckGo error"""
        client = TestSearchClient({})

        # Simulate problematic HTML that might come from a real website
        problematic_html = """<!DOCTYPE html>
<html>
<head>
    <title>Search Results</title>
    <meta charset="utf-8">
</head>
<body>
    <div class="content">
        <p>Some text with embedded\x00null byte</p>
        <script>
            var data = "text\x01with\x02control\x03chars";
        </script>
        <p>Normal content that should be preserved</p>
        <div>More content\x0bwith\x0cinvalid\x0echars</div>
    </div>
</body>
</html>"""

        sanitized = client._sanitize_html_for_xml(problematic_html)

        # Verify problematic characters are removed
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized
        assert "\x02" not in sanitized
        assert "\x03" not in sanitized
        assert "\x0b" not in sanitized
        assert "\x0c" not in sanitized
        assert "\x0e" not in sanitized

        # Verify valid content is preserved
        assert "<!DOCTYPE html>" in sanitized
        assert "Search Results" in sanitized
        assert "Normal content that should be preserved" in sanitized
        assert "More content" in sanitized

    def test_sanitize_html_with_special_xml_characters(self):
        """Test that valid XML special characters are preserved"""
        client = TestSearchClient({})

        # HTML with XML special characters that should be preserved
        html_with_xml_chars = """<html><body>
        <p>Ampersand: &amp; &lt; &gt; &quot; &#39;</p>
        <p>Tab: \t</p>
        <p>Newline:
        New line here</p>
        <p>Carriage return: \r</p>
        </body></html>"""

        sanitized = client._sanitize_html_for_xml(html_with_xml_chars)

        # Valid XML characters should be preserved
        assert "&amp;" in sanitized
        assert "&lt;" in sanitized
        assert "&gt;" in sanitized
        assert "\t" in sanitized  # tab should be preserved
        assert "\n" in sanitized  # newline should be preserved
        assert "\r" in sanitized  # carriage return should be preserved

    def test_sanitize_html_performance_with_large_content(self):
        """Test performance with large HTML content"""
        client = TestSearchClient({})

        # Create large HTML content with some problematic characters
        large_content = (
            "<html><body>"
            + ("Valid text. " * 1000)
            + "\x00\x01\x02"
            + ("More valid text. " * 1000)
            + "</body></html>"
        )

        sanitized = client._sanitize_html_for_xml(large_content)

        # Verify problematic characters are removed
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized
        assert "\x02" not in sanitized

        # Verify content is mostly preserved
        assert "Valid text." in sanitized
        assert "More valid text." in sanitized
        assert len(sanitized) > len(large_content) - 10  # Should only lose a few chars
