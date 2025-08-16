"""Content extraction and summarization utilities"""

import logging

from .models import SearchResult

logger = logging.getLogger(__name__)


class ContentSummarizer:
    """Handles advanced multi-level summarization using AI providers"""

    def __init__(self, ai_client):
        self.ai_client = ai_client

    async def summarize_content(
        self, content: str, query: str, max_length: int = 200
    ) -> str:
        """Generate a focused summary of content based on the search query"""
        if not content or len(content.strip()) < 50:
            return "Content too short to summarize"

        # Truncate very long content to avoid token limits
        if len(content) > 3000:
            content = content[:3000] + "..."

        prompt = f"""Summarize the following content in relation to the search query "{query}".
Focus on information most relevant to the query. Keep the summary under {max_length} words and make it informative and actionable.

Content:
{content}

Summary:"""

        try:
            # Use Nova's AI client interface
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates concise, relevant summaries.",
                },
                {"role": "user", "content": prompt},
            ]

            response = await self.ai_client.generate_response(messages)
            return response.strip() if response else "Summary generation failed"

        except Exception as e:
            logger.warning(f"AI summarization failed: {e}")
            # Fallback to simple truncation
            sentences = content.split(". ")
            summary = sentences[0]
            for sentence in sentences[1:3]:  # Take first 3 sentences max
                if len(summary + sentence) < max_length * 6:  # Rough char limit
                    summary += ". " + sentence
                else:
                    break
            return summary + ("..." if len(sentences) > 3 else "")

    async def synthesize_results(
        self, search_results: list[SearchResult], query: str
    ) -> str:
        """Create a comprehensive synthesis across multiple search results"""
        if not search_results:
            return "No search results available to synthesize."

        # Prepare synthesis prompt with all summaries
        summaries = []
        for i, result in enumerate(search_results[:5], 1):  # Limit to top 5 results
            content = result.content_summary or result.snippet
            if content:
                summaries.append(f"{i}. {result.title} ({result.source}):\n{content}")

        if not summaries:
            return "No content available for synthesis."

        synthesis_prompt = f"""Based on the following search results for the query "{query}", provide a comprehensive answer that:
1. Synthesizes information from multiple sources
2. Highlights key points and insights
3. Notes any conflicting information
4. Provides a balanced perspective

Search Results:
{chr(10).join(summaries)}

Comprehensive Answer:"""

        try:
            # Use Nova's AI client interface
            messages = [
                {
                    "role": "system",
                    "content": "You are a research assistant that synthesizes information from multiple sources to provide comprehensive, balanced answers.",
                },
                {"role": "user", "content": synthesis_prompt},
            ]

            response = await self.ai_client.generate_response(messages)
            return response.strip() if response else "Synthesis generation failed"

        except Exception as e:
            logger.warning(f"AI synthesis failed: {e}")
            # Fallback to simple concatenation
            return "\n\n".join(
                [
                    f"**{result.title}**: {result.content_summary or result.snippet}"
                    for result in search_results[:3]
                ]
            )
