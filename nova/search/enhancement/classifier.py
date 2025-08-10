"""Term classification for search query optimization"""

import logging
import re
from typing import Any

from ..models import KeywordResult, TermClassification

logger = logging.getLogger(__name__)


class TermClassifier:
    """Classifies extracted terms by importance and type for search optimization"""

    def __init__(self):
        # Technical term patterns
        self.technical_patterns = [
            r'\b[A-Z]{2,}\b',  # Acronyms
            r'\b\w+\.\w+',     # dotted notation (e.g., numpy.array)
            r'\b\w+::\w+',     # scope resolution (e.g., std::vector)
            r'\b\w+_\w+',      # snake_case
            r'\bv?\d+\.\d+',   # version numbers
        ]

        # High-priority terms (programming/technical)
        self.technical_keywords = {
            'python', 'javascript', 'java', 'rust', 'go', 'c++', 'typescript',
            'react', 'vue', 'angular', 'django', 'flask', 'fastapi', 'express',
            'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'github', 'git',
            'api', 'rest', 'graphql', 'database', 'sql', 'nosql', 'mongodb',
            'mysql', 'postgresql', 'redis', 'elasticsearch', 'nginx', 'apache',
            'linux', 'ubuntu', 'debian', 'centos', 'macos', 'windows',
            'machine learning', 'deep learning', 'neural network', 'tensorflow',
            'pytorch', 'scikit-learn', 'pandas', 'numpy', 'opencv', 'nlp',
            'blockchain', 'cryptocurrency', 'bitcoin', 'ethereum', 'smart contract'
        }

        # Common stop words that should be deprioritized
        self.stop_words = {
            'the', 'is', 'at', 'which', 'on', 'and', 'or', 'but', 'in', 'with',
            'to', 'for', 'of', 'as', 'by', 'from', 'up', 'about', 'into',
            'through', 'during', 'before', 'after', 'above', 'below', 'between',
            'how', 'what', 'when', 'where', 'why', 'who', 'whom', 'whose',
            'best', 'good', 'great', 'better', 'simple', 'easy', 'basic',
            'tutorial', 'guide', 'example', 'learn', 'learning'
        }

    def classify_terms(
        self,
        keywords: list[KeywordResult],
        entities: list[str],
        original_query: str
    ) -> TermClassification:
        """Classify terms into must-have and nice-to-have categories"""

        must_have_terms = set()
        nice_to_have_terms = set()
        technical_terms = set()

        # Process named entities (usually high priority)
        processed_entities = []
        for entity in entities:
            if len(entity.strip()) > 2 and entity.lower() not in self.stop_words:
                processed_entities.append(entity)
                must_have_terms.add(entity.lower())

        # Process extracted keywords
        for keyword_result in keywords:
            keyword = keyword_result.keyword.lower().strip()

            if self._is_stop_word_phrase(keyword):
                continue

            # High priority terms
            if (keyword_result.score > 0.7 or
                keyword in self.technical_keywords or
                self._is_technical_term(keyword) or
                keyword_result.type in ["entity", "technical"]):

                must_have_terms.add(keyword)

                if (keyword in self.technical_keywords or
                    self._is_technical_term(keyword)):
                    technical_terms.add(keyword)
            else:
                nice_to_have_terms.add(keyword)

        # Look for quoted phrases in original query (always must-have)
        quoted_phrases = re.findall(r'"([^"]*)"', original_query)
        for phrase in quoted_phrases:
            if phrase.strip():
                must_have_terms.add(phrase.lower().strip())

        # Ensure we have at least some must-have terms
        if not must_have_terms and keywords:
            # Take top 2-3 keywords as must-have
            top_keywords = sorted(keywords, key=lambda x: x.score, reverse=True)[:3]
            for kw in top_keywords:
                keyword = kw.keyword.lower().strip()
                if not self._is_stop_word_phrase(keyword):
                    must_have_terms.add(keyword)
                    if keyword in nice_to_have_terms:
                        nice_to_have_terms.remove(keyword)

        return TermClassification(
            must_have_terms=list(must_have_terms),
            nice_to_have_terms=list(nice_to_have_terms),
            entities=processed_entities,
            technical_terms=list(technical_terms)
        )

    def _is_technical_term(self, term: str) -> bool:
        """Check if a term appears to be technical"""
        if term in self.technical_keywords:
            return True

        for pattern in self.technical_patterns:
            if re.search(pattern, term):
                return True

        return False

    def _is_stop_word_phrase(self, phrase: str) -> bool:
        """Check if a phrase consists mostly of stop words"""
        words = phrase.split()
        if len(words) == 1:
            return words[0] in self.stop_words

        # For multi-word phrases, check if majority are stop words
        stop_word_count = sum(1 for word in words if word in self.stop_words)
        return stop_word_count >= len(words) * 0.7

    def prioritize_terms(self, classification: TermClassification, max_terms: int = 10) -> dict[str, list[str]]:
        """Prioritize terms for search query generation"""

        # Start with must-have terms
        prioritized_must_have = []
        prioritized_nice_to_have = []

        # Prioritize entities first
        for entity in classification.entities:
            if len(prioritized_must_have) < max_terms // 2:
                prioritized_must_have.append(entity)

        # Add technical terms
        for tech_term in classification.technical_terms:
            if tech_term not in prioritized_must_have and len(prioritized_must_have) < max_terms // 2:
                prioritized_must_have.append(tech_term)

        # Add remaining must-have terms
        for term in classification.must_have_terms:
            if term not in prioritized_must_have and len(prioritized_must_have) < max_terms // 2:
                prioritized_must_have.append(term)

        # Fill remaining slots with nice-to-have terms
        remaining_slots = max_terms - len(prioritized_must_have)
        for term in classification.nice_to_have_terms:
            if len(prioritized_nice_to_have) < remaining_slots:
                prioritized_nice_to_have.append(term)

        return {
            "must_have": prioritized_must_have,
            "nice_to_have": prioritized_nice_to_have
        }

    def generate_search_variations(self, classification: TermClassification, max_variations: int = 3) -> list[str]:
        """Generate variations of search queries based on classified terms"""

        variations = []
        must_have = classification.must_have_terms[:5]  # Limit to avoid overly long queries
        nice_to_have = classification.nice_to_have_terms[:3]

        if not must_have:
            return []

        # Variation 1: Must-have terms only (most focused)
        variations.append(" ".join(must_have))

        # Variation 2: Must-have + some nice-to-have (balanced)
        if nice_to_have:
            combined = must_have + nice_to_have[:2]
            variations.append(" ".join(combined))

        # Variation 3: Include entities with quotes for exact matching
        if classification.entities and len(variations) < max_variations:
            entity_query_parts = []
            for entity in classification.entities[:2]:
                if len(entity.split()) > 1:
                    entity_query_parts.append(f'"{entity}"')
                else:
                    entity_query_parts.append(entity)

            # Add non-entity must-have terms
            non_entity_terms = [term for term in must_have
                             if term not in [e.lower() for e in classification.entities]]

            entity_query = " ".join(entity_query_parts + non_entity_terms[:3])
            if entity_query not in variations:
                variations.append(entity_query)

        return variations[:max_variations]

    def get_classification_summary(self, classification: TermClassification) -> dict[str, Any]:
        """Get a summary of the classification results"""
        return {
            "total_terms": len(classification.must_have_terms) + len(classification.nice_to_have_terms),
            "must_have_count": len(classification.must_have_terms),
            "nice_to_have_count": len(classification.nice_to_have_terms),
            "entities_count": len(classification.entities),
            "technical_terms_count": len(classification.technical_terms),
            "has_entities": len(classification.entities) > 0,
            "has_technical_terms": len(classification.technical_terms) > 0
        }
