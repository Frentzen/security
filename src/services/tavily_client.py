"""Tavily Search API wrapper with retry logic."""

import logging
import time
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tavily import TavilyClient as BaseTavilyClient

import sys
sys.path.insert(0, '/home/user/security')
from config import TAVILY_API_KEY, MAX_SEARCH_RESULTS_PER_QUERY, MAX_RETRIES, RETRY_DELAY_SECONDS

logger = logging.getLogger(__name__)


class TavilyClient:
    """Wrapper for Tavily Search API with retry logic and parallel search support."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Tavily client.

        Args:
            api_key: Tavily API key (uses env var if not provided)
        """
        self.api_key = api_key or TAVILY_API_KEY

        if not self.api_key:
            raise ValueError("TAVILY_API_KEY is required")

        self.client = BaseTavilyClient(api_key=self.api_key)
        self._cache: dict[str, list[dict]] = {}

    def search(
        self,
        query: str,
        max_results: int = MAX_SEARCH_RESULTS_PER_QUERY,
        search_depth: str = "advanced",
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None
    ) -> list[dict]:
        """Execute a single search query.

        Args:
            query: Search query string
            max_results: Maximum number of results
            search_depth: "basic" or "advanced"
            include_domains: Domains to prioritize
            exclude_domains: Domains to exclude

        Returns:
            List of search result dictionaries
        """
        # Check cache first
        cache_key = f"{query}:{max_results}:{search_depth}"
        if cache_key in self._cache:
            logger.debug(f"Cache hit for query: {query}")
            return self._cache[cache_key]

        last_exception = None

        for attempt in range(MAX_RETRIES):
            try:
                kwargs = {
                    "query": query,
                    "max_results": max_results,
                    "search_depth": search_depth,
                }

                if include_domains:
                    kwargs["include_domains"] = include_domains
                if exclude_domains:
                    kwargs["exclude_domains"] = exclude_domains

                response = self.client.search(**kwargs)

                results = []
                for result in response.get("results", []):
                    results.append({
                        "query": query,
                        "url": result.get("url", ""),
                        "title": result.get("title", ""),
                        "snippet": result.get("content", ""),
                        "score": result.get("score", 0.0),
                    })

                # Cache results
                self._cache[cache_key] = results
                return results

            except Exception as e:
                last_exception = e
                if "rate" in str(e).lower() or "429" in str(e):
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                elif attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(f"Search error: {e}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Search failed after {MAX_RETRIES} attempts: {e}")
                    raise

        raise last_exception or Exception("Max retries exceeded")

    def search_parallel(
        self,
        queries: list[str],
        max_results_per_query: int = MAX_SEARCH_RESULTS_PER_QUERY,
        max_workers: int = 5
    ) -> list[dict]:
        """Execute multiple searches in parallel.

        Args:
            queries: List of search queries
            max_results_per_query: Max results per query
            max_workers: Maximum parallel workers

        Returns:
            Combined list of all search results
        """
        all_results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_query = {
                executor.submit(self.search, query, max_results_per_query): query
                for query in queries
            }

            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    logger.debug(f"Got {len(results)} results for: {query}")
                except Exception as e:
                    logger.error(f"Search failed for '{query}': {e}")
                    # Continue with other searches even if one fails

        return all_results

    def search_security_topic(
        self,
        topic: str,
        framework: Optional[str] = None,
        max_results: int = MAX_SEARCH_RESULTS_PER_QUERY
    ) -> list[dict]:
        """Search for security topic with prioritized domains.

        Prioritizes authoritative security sources.

        Args:
            topic: Security topic to search
            framework: Optional framework for context
            max_results: Maximum results

        Returns:
            List of search results
        """
        # Prioritize authoritative security sources
        priority_domains = [
            "owasp.org",
            "cheatsheetseries.owasp.org",
            "nist.gov",
            "cisa.gov",
            "auth0.com",
            "okta.com",
        ]

        query = topic
        if framework:
            query = f"{topic} {framework}"

        return self.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_domains=priority_domains
        )

    def clear_cache(self):
        """Clear the search results cache."""
        self._cache.clear()
        logger.debug("Search cache cleared")
