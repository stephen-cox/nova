"""Keyword extraction using YAKE and optional KeyBERT"""

import logging
import time
from enum import Enum
from typing import Any

import spacy
import yake
from pydantic import BaseModel, Field

from ..models import KeywordResult

logger = logging.getLogger(__name__)


class ExtractionBackend(str, Enum):
    """Available keyword extraction backends"""

    YAKE_ONLY = "yake_only"  # Fast, lightweight (default)
    KEYBERT_ONLY = "keybert_only"  # Semantic, requires transformers
    HYBRID = "hybrid"  # YAKE + KeyBERT for best results
    ADAPTIVE = "adaptive"  # Auto-choose based on query complexity


class ExtractionConfig(BaseModel):
    """Configuration for keyword extraction"""

    backend: ExtractionBackend = Field(default=ExtractionBackend.YAKE_ONLY)
    yake_max_keywords: int = Field(default=10, ge=1, le=50)
    yake_lang: str = Field(default="en")
    yake_n: int = Field(default=3)  # N-gram size
    yake_deduplication_threshold: float = Field(default=0.9)
    yake_window_size: int = Field(default=1)

    # KeyBERT settings (when available)
    keybert_max_keywords: int = Field(default=6, ge=1, le=20)
    keybert_model: str = Field(default="all-MiniLM-L6-v2")
    keybert_use_mmr: bool = Field(default=True)
    keybert_diversity: float = Field(default=0.5)

    # Performance settings
    performance_mode: bool = Field(default=True)
    enable_spacy_preprocessing: bool = Field(default=True)


class KeywordExtractor:
    """High-performance keyword extractor with swappable backends"""

    def __init__(self, config: ExtractionConfig = None):
        self.config = config or ExtractionConfig()
        self._nlp = None
        self._keybert = None
        self._keybert_available = False

        # Initialize spaCy for preprocessing
        if self.config.enable_spacy_preprocessing:
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found, using basic preprocessing")
                self._nlp = None

        # Check for KeyBERT availability
        if self.config.backend in [
            ExtractionBackend.KEYBERT_ONLY,
            ExtractionBackend.HYBRID,
        ]:
            self._initialize_keybert()

    def _initialize_keybert(self) -> bool:
        """Initialize KeyBERT if available"""
        try:
            from keybert import KeyBERT

            self._keybert = KeyBERT(model=self.config.keybert_model)
            self._keybert_available = True
            logger.info(f"KeyBERT initialized with model: {self.config.keybert_model}")
            return True
        except ImportError:
            logger.warning(
                "KeyBERT not available. Install with: uv add keybert sentence-transformers"
            )
            self._keybert_available = False
            return False
        except Exception as e:
            logger.error(f"Failed to initialize KeyBERT: {e}")
            self._keybert_available = False
            return False

    def extract_keywords(
        self, text: str, max_keywords: int = None
    ) -> list[KeywordResult]:
        """Extract keywords using the configured backend"""
        start_time = time.time()
        max_keywords = max_keywords or self.config.yake_max_keywords

        if self.config.backend == ExtractionBackend.YAKE_ONLY:
            results = self._extract_yake_only(text, max_keywords)
        elif self.config.backend == ExtractionBackend.KEYBERT_ONLY:
            results = self._extract_keybert_only(text, max_keywords)
        elif self.config.backend == ExtractionBackend.HYBRID:
            results = self._extract_hybrid(text, max_keywords)
        elif self.config.backend == ExtractionBackend.ADAPTIVE:
            results = self._extract_adaptive(text, max_keywords)
        else:
            # Fallback to YAKE
            results = self._extract_yake_only(text, max_keywords)

        processing_time = (time.time() - start_time) * 1000
        logger.debug(
            f"Keyword extraction took {processing_time:.1f}ms using {self.config.backend}"
        )

        return results

    def _extract_yake_only(self, text: str, max_keywords: int) -> list[KeywordResult]:
        """Extract keywords using YAKE only"""
        try:
            # Preprocess text with spaCy if available
            if self._nlp:
                doc = self._nlp(text)
                # Remove stop words and punctuation, keep meaningful tokens
                processed_text = " ".join(
                    [
                        token.text
                        for token in doc
                        if not token.is_stop and not token.is_punct and token.is_alpha
                    ]
                )
            else:
                processed_text = text

            # Initialize YAKE
            kw_extractor = yake.KeywordExtractor(
                lan=self.config.yake_lang,
                n=self.config.yake_n,
                dedupLim=self.config.yake_deduplication_threshold,
                windowsSize=self.config.yake_window_size,
                top=max_keywords,
            )

            keywords = kw_extractor.extract_keywords(processed_text)

            results = []
            for item in keywords:
                # Handle different YAKE return formats
                if isinstance(item, tuple) and len(item) == 2:
                    keyword, score = item  # YAKE returns (keyword, score)
                elif isinstance(item, dict):
                    score = item.get("score", 0.0)
                    keyword = item.get("keyword", "")
                else:
                    # Skip malformed items
                    continue

                # Ensure score is numeric
                try:
                    score = float(score)
                except (ValueError, TypeError):
                    score = 1.0

                # Ensure keyword is string
                keyword = str(keyword).strip()
                if not keyword:
                    continue

                # YAKE returns lower scores for better keywords, invert for consistency
                normalized_score = 1.0 / (1.0 + score)

                results.append(
                    KeywordResult(
                        keyword=keyword,
                        score=normalized_score,
                        type=self._classify_keyword_type(keyword),
                        source="yake",
                    )
                )

            return results

        except Exception as e:
            logger.error(f"YAKE extraction failed: {e}")
            return []

    def _extract_keybert_only(
        self, text: str, max_keywords: int
    ) -> list[KeywordResult]:
        """Extract keywords using KeyBERT only"""
        if not self._keybert_available:
            logger.warning("KeyBERT not available, falling back to YAKE")
            return self._extract_yake_only(text, max_keywords)

        try:
            # Use KeyBERT with MMR for diversity
            if self.config.keybert_use_mmr:
                keywords = self._keybert.extract_keywords(
                    text,
                    keyphrase_ngram_range=(1, 3),
                    stop_words="english",
                    use_mmr=True,
                    diversity=self.config.keybert_diversity,
                    top_k=max_keywords,
                )
            else:
                keywords = self._keybert.extract_keywords(
                    text,
                    keyphrase_ngram_range=(1, 3),
                    stop_words="english",
                    top_k=max_keywords,
                )

            results = []
            for keyword, score in keywords:
                results.append(
                    KeywordResult(
                        keyword=keyword,
                        score=score,
                        type=self._classify_keyword_type(keyword),
                        source="keybert",
                    )
                )

            return results

        except Exception as e:
            logger.error(f"KeyBERT extraction failed: {e}")
            return self._extract_yake_only(text, max_keywords)

    def _extract_hybrid(self, text: str, max_keywords: int) -> list[KeywordResult]:
        """Extract keywords using both YAKE and KeyBERT, then merge"""
        # Split keywords between methods
        yake_count = max_keywords // 2
        keybert_count = max_keywords - yake_count

        # Extract from both methods
        yake_results = self._extract_yake_only(text, yake_count)
        keybert_results = self._extract_keybert_only(text, keybert_count)

        # Merge and deduplicate
        all_results = yake_results + keybert_results
        merged_results = self._merge_keyword_results(all_results)

        # Sort by score and return top results
        merged_results.sort(key=lambda x: x.score, reverse=True)
        return merged_results[:max_keywords]

    def _extract_adaptive(self, text: str, max_keywords: int) -> list[KeywordResult]:
        """Adaptively choose extraction method based on text characteristics"""
        # Simple heuristics for method selection
        word_count = len(text.split())

        if word_count < 50:
            # Short text: use YAKE for speed
            return self._extract_yake_only(text, max_keywords)
        elif word_count > 500:
            # Long text: use hybrid approach
            return self._extract_hybrid(text, max_keywords)
        else:
            # Medium text: use KeyBERT if available, otherwise YAKE
            if self._keybert_available:
                return self._extract_keybert_only(text, max_keywords)
            else:
                return self._extract_yake_only(text, max_keywords)

    def _classify_keyword_type(self, keyword: str) -> str:
        """Classify keyword type using spaCy if available"""
        if not self._nlp:
            return "general"

        try:
            doc = self._nlp(keyword)

            # Check for named entities
            if doc.ents:
                return "entity"

            # Check for technical terms (simplified heuristics)
            for token in doc:
                if token.pos_ in ["NOUN", "PROPN"] and len(token.text) > 6:
                    return "technical"

            return "general"

        except Exception:
            return "general"

    def _merge_keyword_results(
        self, results: list[KeywordResult]
    ) -> list[KeywordResult]:
        """Merge keyword results from different sources, handling duplicates"""
        keyword_map = {}

        for result in results:
            key = result.keyword.lower().strip()

            if key in keyword_map:
                # If duplicate, keep the one with higher score
                existing = keyword_map[key]
                if result.score > existing.score:
                    # Combine sources
                    combined_source = f"{existing.source}+{result.source}"
                    keyword_map[key] = KeywordResult(
                        keyword=result.keyword,
                        score=max(result.score, existing.score),
                        type=result.type,
                        source=combined_source,
                    )
            else:
                keyword_map[key] = result

        return list(keyword_map.values())

    def extract_entities(self, text: str) -> list[str]:
        """Extract named entities using spaCy"""
        if not self._nlp:
            return []

        try:
            doc = self._nlp(text)
            entities = [ent.text for ent in doc.ents if len(ent.text.strip()) > 2]
            return list(set(entities))  # Remove duplicates
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []

    def get_performance_info(self) -> dict[str, Any]:
        """Get information about the current extraction setup"""
        return {
            "backend": self.config.backend,
            "spacy_available": self._nlp is not None,
            "keybert_available": self._keybert_available,
            "performance_mode": self.config.performance_mode,
            "yake_settings": {
                "max_keywords": self.config.yake_max_keywords,
                "n_gram_size": self.config.yake_n,
                "language": self.config.yake_lang,
            },
        }
