"""Abstract base class for search engines"""

import asyncio
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import httpx
from bs4 import BeautifulSoup
from newspaper import Article
from readability import Document

from ..models import SearchResponse

logger = logging.getLogger(__name__)


class BaseSearchClient(ABC):
    """Abstract base class for search clients"""

    # Class-level rate limiting state shared across all instances
    _last_request_times: ClassVar[dict[str, float]] = {}
    _request_counts: ClassVar[dict[str, int]] = {}
    _rate_limit_resets: ClassVar[dict[str, float]] = {}

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=config.get("timeout", 10.0),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

    @property
    def provider_name(self) -> str:
        """Get the provider name for rate limiting tracking"""
        return self.__class__.__name__

    def _get_rate_limit_config(self) -> tuple[float, int]:
        """Get rate limiting configuration for this provider.

        Returns:
            tuple: (min_delay_seconds, max_requests_per_minute)
        """
        # Default conservative rate limits
        defaults = {
            "GoogleSearchClient": (1.0, 100),  # Google has strict rate limits
            "BingSearchClient": (0.5, 200),  # Bing is more lenient
            "DuckDuckGoSearchClient": (0.3, 300),  # DuckDuckGo is most lenient
        }

        provider = self.provider_name
        return defaults.get(provider, (0.5, 200))  # Default fallback

    async def _wait_for_rate_limit(self) -> None:
        """Wait if necessary to respect rate limits"""
        provider = self.provider_name
        current_time = time.time()
        min_delay, max_requests_per_minute = self._get_rate_limit_config()

        # Check if we need to reset the request count (every minute)
        last_reset = self._rate_limit_resets.get(provider, 0)
        if current_time - last_reset >= 60.0:  # Reset every minute
            self._request_counts[provider] = 0
            self._rate_limit_resets[provider] = current_time
            logger.debug(f"Reset rate limit counter for {provider}")

        # Check request count limit
        current_count = self._request_counts.get(provider, 0)
        if current_count >= max_requests_per_minute:
            wait_time = 60.0 - (current_time - self._rate_limit_resets.get(provider, 0))
            if wait_time > 0:
                logger.warning(
                    f"Rate limit exceeded for {provider}, waiting {wait_time:.1f}s"
                )
                await asyncio.sleep(wait_time)
                # Reset after waiting
                self._request_counts[provider] = 0
                self._rate_limit_resets[provider] = time.time()

        # Check minimum delay between requests
        last_request = self._last_request_times.get(provider, 0)
        time_since_last = current_time - last_request

        if time_since_last < min_delay:
            wait_time = min_delay - time_since_last
            logger.debug(f"Rate limiting {provider}: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        # Update tracking
        self._last_request_times[provider] = time.time()
        self._request_counts[provider] = current_count + 1

    async def _handle_rate_limit_error(self, response: httpx.Response) -> None:
        """Handle 429 rate limit errors with exponential backoff"""
        if response.status_code == 429:
            provider = self.provider_name

            # Try to get retry-after header
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    wait_time = float(retry_after)
                except ValueError:
                    wait_time = 60.0  # Default fallback
            else:
                # Exponential backoff: start with 30s, max 300s (5 min)
                base_wait = 30.0
                current_count = self._request_counts.get(provider, 0)
                wait_time = min(base_wait * (2 ** min(current_count // 10, 3)), 300.0)

            logger.warning(
                f"Rate limited by {provider} (429), waiting {wait_time:.1f}s"
            )
            await asyncio.sleep(wait_time)

            # Reset rate limit tracking after waiting
            self._rate_limit_resets[provider] = time.time()
            self._request_counts[provider] = 0

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.close()

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
        try:
            await self.client.aclose()
            logger.debug(f"Closed HTTP client for {self.__class__.__name__}")
        except Exception as e:
            logger.warning(
                f"Error closing HTTP client for {self.__class__.__name__}: {e}"
            )

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

            # Sanitize HTML content to remove invalid XML characters
            html_content = self._sanitize_html_for_xml(response.text)

            doc = Document(html_content)
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

    def _sanitize_html_for_xml(self, html_content: str) -> str:
        """Sanitize HTML content to remove invalid XML characters that cause readability to fail.

        The readability library fails when HTML contains NULL bytes or other control characters
        that are not valid in XML. This method removes those characters.
        """
        if not html_content:
            return html_content

        # Remove NULL bytes and other problematic control characters
        # Keep only valid XML characters: tab, newline, carriage return, and printable characters
        sanitized = ""
        for char in html_content:
            code = ord(char)
            if (
                code == 0x09  # tab
                or code == 0x0A  # newline
                or code == 0x0D  # carriage return
                or (0x20 <= code <= 0xD7FF)  # basic multilingual plane
                or (0xE000 <= code <= 0xFFFD)  # private use area and others
                or (0x10000 <= code <= 0x10FFFF)
            ):  # supplementary planes
                sanitized += char
            # Skip invalid characters silently

        return sanitized
