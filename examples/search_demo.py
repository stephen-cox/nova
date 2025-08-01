#!/usr/bin/env python3
"""
Demo script showing Nova's web search functionality
"""

import sys
from pathlib import Path

# Add the parent directory to Python path to import nova
sys.path.insert(0, str(Path(__file__).parent.parent))

from nova.core.search import search_web
from nova.utils.formatting import print_search_results


def main():
    """Demonstrate web search functionality"""

    # Configuration for search (DuckDuckGo requires no API keys)
    config = {
        "search": {
            "google": {},  # No API keys configured
            "bing": {},  # No API keys configured
        }
    }

    print("🔍 Nova Web Search Demo")
    print("=" * 40)
    print()

    # Example search
    query = "Python programming best practices"
    print(f"Searching for: {query}")
    print()

    try:
        # Perform the search (will use DuckDuckGo by default)
        search_response = search_web(config=config, query=query, max_results=3)

        # Display the results using Nova's formatting
        print_search_results(search_response)

    except Exception as e:
        print(f"Search failed: {e}")


if __name__ == "__main__":
    main()
