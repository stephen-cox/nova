"""Abstract base class for search engines"""

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx
from bs4 import BeautifulSoup
from newspaper import Article
from readability import Document

from ..models import SearchResponse

logger = logging.getLogger(__name__)


class BaseSearchClient(ABC):
    """Abstract base class for search clients"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=config.get("timeout", 10.0), headers={"User-Agent": "Nova AI Assistant/1.0"}
        )

    @abstractmethod
    async def search(
        self, query: str, max_results: int = 10, **kwargs
    ) -> SearchResponse:
        """Perform a web search"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate the search client configuration"""
        pass

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def extract_content(self, url: str) -> tuple[str | None, bool]:
        """Extract full content from a webpage URL

        Returns:
            tuple: (extracted_content, success_flag)
        """
        try:
            # Method 1: Try newspaper3k first (better for articles)
            article = Article(url)
            article.download()
            article.parse()

            if article.text and len(article.text.strip()) > 100:
                logger.debug(f"Content extracted via newspaper3k from {url}")
                return article.text.strip(), True

        except Exception as e:
            logger.debug(f"Newspaper3k extraction failed for {url}: {e}")

        try:
            # Method 2: Fallback to readability-lxml (better for general pages)
            response = await self.client.get(url, timeout=15.0)
            response.raise_for_status()

            doc = Document(response.text)
            content = doc.summary()

            if content:
                # Parse with BeautifulSoup to extract clean text
                soup = BeautifulSoup(content, "html.parser")
                clean_text = soup.get_text(separator=" ", strip=True)

                if len(clean_text.strip()) > 100:
                    logger.debug(f"Content extracted via readability from {url}")
                    return clean_text.strip(), True

        except Exception as e:
            logger.debug(f"Readability extraction failed for {url}: {e}")

        try:
            # Method 3: Basic HTML parsing fallback
            response = await self.client.get(url, timeout=10.0)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted elements
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()

            # Try to find main content areas
            main_content = (
                soup.find("main")
                or soup.find("article")
                or soup.find(class_=re.compile(r"content|main|article", re.I))
                or soup.find("div", class_=re.compile(r"post|entry|body", re.I))
                or soup.body
            )

            if main_content:
                text = main_content.get_text(separator=" ", strip=True)
                if len(text.strip()) > 100:
                    logger.debug(f"Content extracted via basic HTML parsing from {url}")
                    return text.strip()[:5000], True  # Limit to 5000 chars

        except Exception as e:
            logger.debug(f"Basic HTML extraction failed for {url}: {e}")

        logger.warning(f"All content extraction methods failed for {url}")
        return None, False
