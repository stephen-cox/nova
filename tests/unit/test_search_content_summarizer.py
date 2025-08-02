"""
Tests for ContentSummarizer and enhanced SearchResult functionality
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from nova.core.search import (
    ContentSummarizer,
    SearchResult,
)


class TestEnhancedSearchResult:
    """Test enhanced SearchResult model with new fields"""

    def test_enhanced_search_result_creation(self):
        """Test creating SearchResult with all new fields"""
        result = SearchResult(
            title="Test Article",
            url="https://example.com/article",
            snippet="Original snippet text",
            source="example.com",
            published_date=datetime.now(),
            full_content="This is the full extracted content from the webpage.",
            content_summary="AI-generated summary of the content",
            extraction_success=True,
        )

        assert result.title == "Test Article"
        assert result.url == "https://example.com/article"
        assert result.snippet == "Original snippet text"
        assert result.source == "example.com"
        assert (
            result.full_content
            == "This is the full extracted content from the webpage."
        )
        assert result.content_summary == "AI-generated summary of the content"
        assert result.extraction_success is True

    def test_enhanced_search_result_defaults(self):
        """Test SearchResult with default values for new fields"""
        result = SearchResult(
            title="Test Article",
            url="https://example.com/article",
            snippet="Original snippet text",
            source="example.com",
        )

        assert result.full_content is None
        assert result.content_summary is None
        assert result.extraction_success is False

    def test_enhanced_search_result_partial_extraction(self):
        """Test SearchResult with content but no summary"""
        result = SearchResult(
            title="Test Article",
            url="https://example.com/article",
            snippet="Original snippet text",
            source="example.com",
            full_content="Extracted content",
            extraction_success=True,
        )

        assert result.full_content == "Extracted content"
        assert result.content_summary is None
        assert result.extraction_success is True


class TestContentSummarizer:
    """Test ContentSummarizer functionality"""

    @pytest.fixture
    def mock_ai_client(self):
        """Create a mock AI client"""
        client = AsyncMock()
        client.generate_response = AsyncMock()
        return client

    @pytest.fixture
    def content_summarizer(self, mock_ai_client):
        """Create ContentSummarizer with mock AI client"""
        return ContentSummarizer(mock_ai_client)

    @pytest.mark.asyncio
    async def test_summarize_content_success(self, content_summarizer, mock_ai_client):
        """Test successful content summarization"""
        mock_ai_client.generate_response.return_value = (
            "This is a concise summary of the content."
        )

        content = "This is a long piece of content that needs to be summarized for the user's query about Python programming."
        summary = await content_summarizer.summarize_content(
            content, "Python programming", max_length=50
        )

        assert summary == "This is a concise summary of the content."
        mock_ai_client.generate_response.assert_called_once()

        # Check that the correct messages were passed
        call_args = mock_ai_client.generate_response.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0]["role"] == "system"
        assert call_args[1]["role"] == "user"
        assert "Python programming" in call_args[1]["content"]

    @pytest.mark.asyncio
    async def test_summarize_content_too_short(self, content_summarizer):
        """Test content that's too short to summarize"""
        short_content = "Short"
        summary = await content_summarizer.summarize_content(
            short_content, "test query"
        )

        assert summary == "Content too short to summarize"

    @pytest.mark.asyncio
    async def test_summarize_content_ai_failure_fallback(
        self, content_summarizer, mock_ai_client
    ):
        """Test fallback when AI summarization fails"""
        mock_ai_client.generate_response.side_effect = Exception("AI failed")

        content = "First sentence. Second sentence here. Third sentence for testing. Fourth sentence to check fallback."
        summary = await content_summarizer.summarize_content(
            content, "test query", max_length=50
        )

        # Should fall back to simple sentence truncation
        assert "First sentence" in summary
        assert summary.endswith("...")

    @pytest.mark.asyncio
    async def test_summarize_content_long_content_truncation(
        self, content_summarizer, mock_ai_client
    ):
        """Test content truncation for very long content"""
        mock_ai_client.generate_response.return_value = "Summary of truncated content."

        # Create content longer than 3000 characters
        long_content = "A" * 4000

        await content_summarizer.summarize_content(long_content, "test query")

        # Check that the content was truncated in the prompt
        call_args = mock_ai_client.generate_response.call_args[0][0]
        prompt_content = call_args[1]["content"]
        assert "..." in prompt_content  # Should contain truncation indicator

    @pytest.mark.asyncio
    async def test_synthesize_results_success(self, content_summarizer, mock_ai_client):
        """Test successful results synthesis"""
        mock_ai_client.generate_response.return_value = (
            "Comprehensive synthesis of all search results."
        )

        results = [
            SearchResult(
                title="Result 1",
                url="https://example1.com",
                snippet="Snippet 1",
                source="example1.com",
                content_summary="Summary 1",
            ),
            SearchResult(
                title="Result 2",
                url="https://example2.com",
                snippet="Snippet 2",
                source="example2.com",
                content_summary="Summary 2",
            ),
        ]

        synthesis = await content_summarizer.synthesize_results(results, "test query")

        assert synthesis == "Comprehensive synthesis of all search results."
        mock_ai_client.generate_response.assert_called_once()

        # Check that the synthesis prompt includes all results
        call_args = mock_ai_client.generate_response.call_args[0][0]
        synthesis_prompt = call_args[1]["content"]
        assert "Result 1" in synthesis_prompt
        assert "Result 2" in synthesis_prompt
        assert "Summary 1" in synthesis_prompt
        assert "Summary 2" in synthesis_prompt

    @pytest.mark.asyncio
    async def test_synthesize_results_no_results(self, content_summarizer):
        """Test synthesis with no results"""
        synthesis = await content_summarizer.synthesize_results([], "test query")
        assert synthesis == "No search results available to synthesize."

    @pytest.mark.asyncio
    async def test_synthesize_results_ai_failure_fallback(
        self, content_summarizer, mock_ai_client
    ):
        """Test fallback when AI synthesis fails"""
        mock_ai_client.generate_response.side_effect = Exception("AI synthesis failed")

        results = [
            SearchResult(
                title="Result 1",
                url="https://example1.com",
                snippet="Snippet 1",
                source="example1.com",
                content_summary="Summary 1",
            )
        ]

        synthesis = await content_summarizer.synthesize_results(results, "test query")

        # Should fall back to simple concatenation
        assert "**Result 1**: Summary 1" in synthesis

    @pytest.mark.asyncio
    async def test_synthesize_results_uses_snippet_fallback(
        self, content_summarizer, mock_ai_client
    ):
        """Test synthesis uses snippet when no content_summary available"""
        mock_ai_client.generate_response.return_value = "Synthesis using snippets."

        results = [
            SearchResult(
                title="Result 1",
                url="https://example1.com",
                snippet="This is the snippet text",
                source="example1.com",
                # No content_summary provided
            )
        ]

        await content_summarizer.synthesize_results(results, "test query")

        # Check that snippet was used in the prompt
        call_args = mock_ai_client.generate_response.call_args[0][0]
        synthesis_prompt = call_args[1]["content"]
        assert "This is the snippet text" in synthesis_prompt
