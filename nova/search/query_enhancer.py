"""Query enhancement service for semantic search optimization"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class QueryEnhancer:
    """Enhances user queries using AI to generate optimized search terms"""

    def __init__(self, ai_client):
        self.ai_client = ai_client

    async def enhance_query(
        self, user_query: str, chat_context: str = ""
    ) -> dict[str, Any]:
        """Transform user query into optimized search terms

        Args:
            user_query: Original user search query
            chat_context: Recent conversation context for disambiguation

        Returns:
            Dict containing original query, enhanced queries, and strategy
        """
        enhancement_prompt = f"""You are a search-query optimizer.
Given (A) the user’s latest question and (B) a short chat-context summary,
produce a JSON object to drive a web search.

Rules:
- Keep queries short (6–12 words each), keyword-dense, no fluff.
- Resolve pronouns and vague references using the context.
- Add at most 1–2 synonyms per major noun phrase.
- If useful, include light operators (site:, intitle:, filetype:, OR).
- Include a recency hint only when the topic is time-sensitive.

Return as JSON:
{{
    "original": "{user_query}",
    "enhanced_queries": [
        "optimized query 1",
        "optimized query 2"
    ],
    "search_strategy": "brief explanation of approach"
}}

A) user_question = {user_query}
B) chat_context = {chat_context}
"""

        try:
            # Create messages format for the AI client
            messages = [{"role": "user", "content": enhancement_prompt}]
            response = await self.ai_client.generate_response(messages)
            # Extract JSON from response if it contains extra text
            response_text = response.strip()

            # Find JSON block in response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx != -1 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                enhancement_data = json.loads(json_text)

                # Validate response structure
                if not all(
                    key in enhancement_data for key in ["original", "enhanced_queries"]
                ):
                    raise ValueError("Invalid enhancement response structure")

                logger.info(
                    f"Enhanced query '{user_query}' with strategy: {enhancement_data.get('search_strategy', 'N/A')}"
                )
                print(enhancement_data)
                return enhancement_data
            else:
                raise ValueError("No valid JSON found in response")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse enhancement response as JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"Query enhancement failed: {e}")
            raise
