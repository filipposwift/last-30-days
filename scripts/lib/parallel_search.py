"""Parallel AI web search for last-30-days skill.

Uses the Parallel AI Search API to find web content (blogs, docs, news, tutorials).
This is the primary web search backend -- it returns LLM-optimized results
with extended excerpts ranked by relevance.

Supports multiple specialized queries per search to improve coverage:
- recommendations: lists, comparisons, reviews
- news: announcements, developments, analysis
- prompting: techniques, templates, tutorials
- general: blog posts, opinions, practical guides

API docs: https://docs.parallel.ai/search-api/search-quickstart
"""

import sys
from typing import Any, Dict, List
from urllib.parse import urlparse

from . import http

ENDPOINT = "https://api.parallel.ai/v1beta/search"

# Domains to exclude (handled by Reddit/X search)
EXCLUDED_DOMAINS = {
    "reddit.com", "www.reddit.com", "old.reddit.com",
    "twitter.com", "www.twitter.com", "x.com", "www.x.com",
}

# Per-depth settings
_DEPTH_CONFIG = {
    "quick":   {"num_queries": 1, "max_results": 8,  "max_chars": 800},
    "default": {"num_queries": 2, "max_results": 10, "max_chars": 800},
    "deep":    {"num_queries": 3, "max_results": 12, "max_chars": 800},
}


def _build_queries(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str,
    query_type: str,
) -> List[str]:
    """Build specialized search objectives based on query type and depth.

    Returns 1-3 objective strings depending on depth.
    """
    date_range = f"from {from_date} to {to_date}"
    exclude = "Exclude reddit.com, x.com, and twitter.com."
    cfg = _DEPTH_CONFIG.get(depth, _DEPTH_CONFIG["default"])
    num = cfg["num_queries"]

    objectives = {
        "recommendations": [
            f"Find lists, rankings, and comparisons of {topic} {date_range}. Focus on 'best of', 'top picks', and buyer's guides. {exclude}",
            f"Find user reviews, detailed comparisons, and hands-on experiences with {topic} {date_range}. {exclude}",
            f"Find expert roundups, award lists, and community recommendations for {topic} {date_range}. {exclude}",
        ],
        "news": [
            f"Find news articles, announcements, and press releases about {topic} {date_range}. {exclude}",
            f"Find analysis, opinion pieces, and industry commentary about {topic} {date_range}. {exclude}",
            f"Find development updates, roadmap changes, and ecosystem news about {topic} {date_range}. {exclude}",
        ],
        "prompting": [
            f"Find prompting techniques, prompt templates, and tutorials for {topic} {date_range}. {exclude}",
            f"Find best practices, tips, and example prompts for {topic} {date_range}. {exclude}",
            f"Find advanced techniques, workflow guides, and prompt engineering strategies for {topic} {date_range}. {exclude}",
        ],
        "general": [
            f"Find recent blog posts, tutorials, news articles, and discussions about {topic} {date_range}. {exclude}",
            f"Find opinions, practical guides, and community insights about {topic} {date_range}. {exclude}",
            f"Find case studies, deep dives, and technical analysis of {topic} {date_range}. {exclude}",
        ],
    }

    query_list = objectives.get(query_type, objectives["general"])
    return query_list[:num]


def search_web(
    topic: str,
    from_date: str,
    to_date: str,
    api_key: str,
    depth: str = "default",
    query_type: str = "general",
) -> List[Dict[str, Any]]:
    """Search the web via Parallel AI Search API.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        api_key: Parallel AI API key
        depth: 'quick', 'default', or 'deep'
        query_type: 'general', 'recommendations', 'news', or 'prompting'

    Returns:
        List of result dicts with keys: url, title, snippet, source_domain, date, relevance

    Raises:
        http.HTTPError: On API errors
    """
    cfg = _DEPTH_CONFIG.get(depth, _DEPTH_CONFIG["default"])
    queries = _build_queries(topic, from_date, to_date, depth, query_type)

    all_items: List[Dict[str, Any]] = []
    seen_urls: set = set()

    for qi, objective in enumerate(queries):
        sys.stderr.write(f"[Web] Parallel AI query {qi+1}/{len(queries)}: {objective[:80]}...\n")
        sys.stderr.flush()

        payload = {
            "objective": objective,
            "max_results": cfg["max_results"],
            "max_chars_per_result": cfg["max_chars"],
        }

        response = http.post(
            ENDPOINT,
            json_data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "parallel-beta": "search-extract-2025-10-10",
            },
            timeout=30,
        )

        new_items = _normalize_results(response, seen_urls, id_offset=len(all_items))
        all_items.extend(new_items)

    sys.stderr.write(f"[Web] Parallel AI total: {len(all_items)} results ({len(queries)} queries)\n")
    sys.stderr.flush()

    return all_items


def _normalize_results(
    response: Dict[str, Any],
    seen_urls: set,
    id_offset: int = 0,
) -> List[Dict[str, Any]]:
    """Convert Parallel AI response to websearch item schema.

    Deduplicates URLs across multiple queries via seen_urls set.

    Args:
        response: Raw API response
        seen_urls: Set of already-seen URLs (mutated in place for dedup)
        id_offset: Starting index for item IDs

    Returns:
        List of normalized result dicts
    """
    items = []

    results = response.get("results", [])
    if not isinstance(results, list):
        return items

    for result in results:
        if not isinstance(result, dict):
            continue

        url = result.get("url", "")
        if not url:
            continue

        # Dedup across queries
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Skip excluded domains
        try:
            domain = urlparse(url).netloc.lower()
            if domain in EXCLUDED_DOMAINS:
                continue
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            domain = ""

        title = str(result.get("title", "")).strip()
        snippet = str(result.get("excerpt", result.get("snippet", result.get("description", "")))).strip()

        if not title and not snippet:
            continue

        # Extract relevance score if provided
        relevance = result.get("relevance_score", result.get("relevance", 0.6))
        try:
            relevance = min(1.0, max(0.0, float(relevance)))
        except (TypeError, ValueError):
            relevance = 0.6

        idx = id_offset + len(items) + 1
        items.append({
            "id": f"W{idx}",
            "title": title[:200],
            "url": url,
            "source_domain": domain,
            "snippet": snippet[:800],
            "date": result.get("published_date", result.get("date")),
            "date_confidence": "med" if result.get("published_date") or result.get("date") else "low",
            "relevance": relevance,
            "why_relevant": str(result.get("summary", "")).strip()[:200],
        })

    return items
