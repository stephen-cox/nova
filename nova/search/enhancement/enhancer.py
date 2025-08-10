"""Main query enhancement pipeline using three-stage approach"""

import json
import logging
import time
from typing import Any

from ..models import (
    EnhancedSearchPlan,
    EnhancedSearchQuery,
    SearchEnhancementMode,
    SearchMemoryConstraints,
    TermClassification,
)
from .classifier import TermClassifier
from .extractors import ExtractionConfig, KeywordExtractor

logger = logging.getLogger(__name__)


class QueryEnhancer:
    """Three-stage query enhancement: NLP → LLM → JSON execution"""

    def __init__(self, ai_client=None, config: ExtractionConfig = None):
        self.ai_client = ai_client
        self.extractor = KeywordExtractor(config or ExtractionConfig())
        self.classifier = TermClassifier()
        self._enhancement_cache = {}

    async def enhance_query(
        self,
        user_query: str,
        conversation_context: str = "",
        memory_constraints: SearchMemoryConstraints | None = None,
        enhancement_mode: SearchEnhancementMode = SearchEnhancementMode.FAST,
        max_queries: int = 3
    ) -> EnhancedSearchPlan:
        """
        Three-stage enhancement pipeline:
        1. NLP extracts and classifies terms
        2. LLM creates structured search plan with constraints
        3. JSON output drives search execution
        """
        start_time = time.time()

        # Check cache first
        cache_key = f"{user_query}:{enhancement_mode}:{hash(conversation_context)}"
        if cache_key in self._enhancement_cache:
            cached_plan = self._enhancement_cache[cache_key]
            logger.debug("Using cached enhancement plan")
            return cached_plan

        try:
            # Stage 1: NLP Term Extraction & Classification
            extraction_details = await self._extract_and_classify_terms(
                user_query, conversation_context, enhancement_mode
            )

            # Stage 2: Structured LLM Planning (if AI client available)
            if self.ai_client and enhancement_mode != SearchEnhancementMode.DISABLED:
                search_plan = await self._generate_structured_search_plan(
                    user_query=user_query,
                    extraction_details=extraction_details,
                    conversation_context=conversation_context,
                    memory_constraints=memory_constraints or SearchMemoryConstraints(),
                    max_queries=max_queries
                )
            else:
                # Fallback: rule-based query generation
                search_plan = self._fallback_search_plan(
                    user_query, extraction_details, max_queries
                )

            processing_time = int((time.time() - start_time) * 1000)

            enhanced_plan = EnhancedSearchPlan(
                original_query=user_query,
                enhanced_queries=search_plan,
                extraction_details=extraction_details,
                enhancement_mode=enhancement_mode,
                processing_time_ms=processing_time,
                context_used=bool(conversation_context.strip())
            )

            # Cache the result
            self._enhancement_cache[cache_key] = enhanced_plan

            return enhanced_plan

        except Exception as e:
            logger.error(f"Query enhancement failed: {e}")
            # Fallback to original query
            return self._create_fallback_plan(user_query, enhancement_mode, start_time)

    async def _extract_and_classify_terms(
        self,
        user_query: str,
        conversation_context: str,
        enhancement_mode: SearchEnhancementMode
    ) -> dict[str, Any]:
        """Stage 1: Extract and classify terms using NLP"""

        # Combine query with recent conversation context
        full_text = user_query
        if conversation_context.strip():
            full_text = f"{conversation_context}\n\n{user_query}"

        # Extract keywords based on enhancement mode
        if enhancement_mode == SearchEnhancementMode.DISABLED:
            keywords = []
            entities = []
        else:
            # Configure extraction based on mode
            max_keywords = 15 if enhancement_mode == SearchEnhancementMode.HYBRID else 10
            keywords = self.extractor.extract_keywords(full_text, max_keywords)
            entities = self.extractor.extract_entities(user_query)  # Focus entities on main query

        # Classify terms
        classification = self.classifier.classify_terms(keywords, entities, user_query)

        return {
            "keywords": [kw.model_dump() for kw in keywords],
            "entities": entities,
            "classification": classification.model_dump(),
            "extraction_performance": self.extractor.get_performance_info()
        }

    async def _generate_structured_search_plan(
        self,
        user_query: str,
        extraction_details: dict[str, Any],
        conversation_context: str,
        memory_constraints: SearchMemoryConstraints,
        max_queries: int
    ) -> list[EnhancedSearchQuery]:
        """Stage 2: Generate structured search plan using LLM"""

        classification = TermClassification(**extraction_details["classification"])

        # Create structured prompt for LLM
        prompt = self._build_enhancement_prompt(
            user_query, classification, conversation_context, memory_constraints, max_queries
        )

        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a search query optimization expert. Generate optimized search queries in the exact JSON format requested. Focus on technical accuracy and search effectiveness."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            response = await self.ai_client.generate_response(messages)

            # Parse JSON response
            search_queries = self._parse_llm_response(response, user_query, max_queries)
            return search_queries

        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
            return self._fallback_search_plan(user_query, extraction_details, max_queries)

    def _build_enhancement_prompt(
        self,
        user_query: str,
        classification: TermClassification,
        conversation_context: str,
        memory_constraints: SearchMemoryConstraints,
        max_queries: int
    ) -> str:
        """Build structured prompt for LLM query enhancement"""

        # Build the conversation context section if available
        context_section = ""
        if conversation_context.strip():
            # Limit context length to avoid overwhelming the prompt
            limited_context = conversation_context[:500] + "..." if len(conversation_context) > 500 else conversation_context
            context_section = f"""
CONVERSATION CONTEXT:
{limited_context}

Use this context to understand what the user might be looking for and refine the search queries accordingly.
"""

        prompt = f"""Generate {max_queries} optimized search queries for: "{user_query}"
{context_section}
EXTRACTED TERMS:
Must-have terms: {', '.join(classification.must_have_terms[:8])}
Entities: {', '.join(classification.entities[:5])}
Technical terms: {', '.join(classification.technical_terms[:5])}

CONSTRAINTS:
- Technical level: {memory_constraints.technical_level}
- Time preference: {memory_constraints.timeframe}
- Locale: {memory_constraints.locale}

REQUIREMENTS:
1. Each query MUST include at least 2 must-have terms
2. Vary query styles: exact phrases, synonyms, related concepts
3. Prioritize technical accuracy over broad results
4. Consider recent vs comprehensive results based on timeframe
5. Use conversation context to refine search intent and focus

Return ONLY a JSON array in this exact format:
[
  {{
    "query": "optimized search query 1",
    "priority": 1,
    "expected_results": 10,
    "rationale": "why this query variant"
  }},
  {{
    "query": "optimized search query 2",
    "priority": 2,
    "expected_results": 8,
    "rationale": "why this query variant"
  }}
]

Generate {max_queries} queries now:"""

        return prompt

    def _parse_llm_response(
        self,
        response: str,
        original_query: str,
        max_queries: int
    ) -> list[EnhancedSearchQuery]:
        """Parse LLM JSON response into structured queries"""

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = response.strip()
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0].strip()
            elif "```" in json_text:
                json_text = json_text.split("```")[1].strip()

            queries_data = json.loads(json_text)

            if not isinstance(queries_data, list):
                raise ValueError("Response is not a list")

            enhanced_queries = []
            for i, query_data in enumerate(queries_data[:max_queries]):
                enhanced_queries.append(EnhancedSearchQuery(
                    query=query_data.get("query", original_query),
                    priority=query_data.get("priority", i + 1),
                    expected_results=query_data.get("expected_results", 10),
                    rationale=query_data.get("rationale", "Generated query")
                ))

            return enhanced_queries

        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Return original query as fallback
            return [EnhancedSearchQuery(
                query=original_query,
                priority=1,
                expected_results=10,
                rationale="Fallback to original query due to parsing error"
            )]

    def _fallback_search_plan(
        self,
        user_query: str,
        extraction_details: dict[str, Any],
        max_queries: int
    ) -> list[EnhancedSearchQuery]:
        """Generate search plan using rule-based approach (no LLM)"""

        classification = TermClassification(**extraction_details["classification"])
        queries = []

        # Query 1: Original query (baseline)
        queries.append(EnhancedSearchQuery(
            query=user_query,
            priority=1,
            expected_results=10,
            rationale="Original user query"
        ))

        if max_queries > 1 and classification.must_have_terms:
            # Query 2: Must-have terms optimized
            must_have_query = " ".join(classification.must_have_terms[:5])
            if must_have_query.strip() and must_have_query != user_query:
                queries.append(EnhancedSearchQuery(
                    query=must_have_query,
                    priority=2,
                    expected_results=8,
                    rationale="Focused on key terms"
                ))

        if max_queries > 2 and classification.entities:
            # Query 3: Entity-focused with quotes
            entity_parts = []
            for entity in classification.entities[:2]:
                if len(entity.split()) > 1:
                    entity_parts.append(f'"{entity}"')
                else:
                    entity_parts.append(entity)

            entity_query = " ".join(entity_parts + classification.technical_terms[:2])
            if entity_query.strip() and len(entity_query) > 3:
                queries.append(EnhancedSearchQuery(
                    query=entity_query,
                    priority=3,
                    expected_results=6,
                    rationale="Entity and technical term focused"
                ))

        return queries[:max_queries]

    def _create_fallback_plan(
        self,
        user_query: str,
        enhancement_mode: SearchEnhancementMode,
        start_time: float
    ) -> EnhancedSearchPlan:
        """Create a minimal fallback plan when enhancement fails"""

        processing_time = int((time.time() - start_time) * 1000)

        return EnhancedSearchPlan(
            original_query=user_query,
            enhanced_queries=[EnhancedSearchQuery(
                query=user_query,
                priority=1,
                expected_results=10,
                rationale="Fallback due to enhancement failure"
            )],
            extraction_details={"error": "Enhancement failed, using original query"},
            enhancement_mode=enhancement_mode,
            processing_time_ms=processing_time,
            context_used=False
        )

    def clear_cache(self):
        """Clear the enhancement cache"""
        self._enhancement_cache.clear()
        logger.debug("Enhancement cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        return {
            "cached_queries": len(self._enhancement_cache),
            "extractor_info": self.extractor.get_performance_info()
        }
