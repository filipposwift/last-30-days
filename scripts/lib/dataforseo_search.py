"""DataForSEO Google AI Mode search for last-30-days skill.

Supplemental web source that runs alongside Brave/Parallel/OpenRouter.
Returns Google's AI overview (synthesized answer) + reference URLs as web items.

API docs: https://docs.dataforseo.com/v3/serp/google/ai_mode/live/advanced/
"""

import base64
import sys
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from . import http

ENDPOINT = "https://api.dataforseo.com/v3/serp/google/ai_mode/live/advanced"

# Domains to exclude (handled by Reddit/X search)
EXCLUDED_DOMAINS = {
    "reddit.com", "www.reddit.com", "old.reddit.com",
    "twitter.com", "www.twitter.com", "x.com", "www.x.com",
}


def search_web(
    topic: str,
    from_date: str,
    to_date: str,
    api_login: str,
    api_password: str,
    depth: str = "default",
) -> Tuple[List[Dict[str, Any]], str]:
    """Search via DataForSEO Google AI Mode API.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        api_login: DataForSEO login
        api_password: DataForSEO password
        depth: 'quick', 'default', or 'deep'

    Returns:
        Tuple of (web_items, ai_overview_text)
        web_items are raw dicts matching brave_search schema.

    Raises:
        http.HTTPError: On API errors
    """
    queries = _build_structured_queries(topic, depth)

    all_items = []
    all_overviews = []
    seen_urls = set()

    for query in queries:
        try:
            response = _call_api(query, api_login, api_password)
            items, overview = _normalize_results(response, from_date, to_date)

            # Dedupe across queries
            for item in items:
                url_key = item["url"].lower().rstrip("/")
                if url_key not in seen_urls:
                    seen_urls.add(url_key)
                    all_items.append(item)

            if overview:
                all_overviews.append(overview)
        except http.HTTPError as e:
            sys.stderr.write(f"[DataForSEO] API error for query '{query[:50]}': {e}\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"[DataForSEO] Error for query '{query[:50]}': {e}\n")
            sys.stderr.flush()

    ai_overview = "\n\n---\n\n".join(all_overviews) if all_overviews else ""

    sys.stderr.write(f"[DataForSEO] {len(all_items)} reference URLs, {len(all_overviews)} AI overviews\n")
    sys.stderr.flush()

    return all_items, ai_overview


def _build_structured_queries(topic: str, depth: str) -> List[str]:
    """Generate 1-3 natural language questions from topic.

    Args:
        topic: Raw topic string
        depth: 'quick' (1 query), 'default' (2), 'deep' (3)

    Returns:
        List of query strings
    """
    queries = [
        f"What are the biggest {topic} trends and what's driving them?",
        f"Who are the top influencers and brands in {topic} right now?",
        f"What do experts recommend for {topic} in 2026?",
    ]

    count = {"quick": 1, "default": 2, "deep": 3}.get(depth, 2)
    return queries[:count]


def _call_api(
    query: str,
    api_login: str,
    api_password: str,
) -> Dict[str, Any]:
    """Make a single DataForSEO AI Mode API call.

    Args:
        query: Search query
        api_login: DataForSEO login
        api_password: DataForSEO password

    Returns:
        API response dict

    Raises:
        http.HTTPError: On API errors
    """
    # Basic Auth header
    credentials = base64.b64encode(f"{api_login}:{api_password}".encode()).decode()

    payload = [{
        "keyword": query,
        "location_code": 2840,  # United States
        "language_code": "en",
    }]

    sys.stderr.write(f"[DataForSEO] Querying: {query[:60]}...\n")
    sys.stderr.flush()

    # DataForSEO expects a JSON array (list) as payload, but http.request's
    # debug logging calls .keys() which fails on lists. Send raw bytes instead.
    import json as _json
    import urllib.request
    import urllib.error

    data = _json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
        "User-Agent": http.USER_AGENT,
    }
    req = urllib.request.Request(ENDPOINT, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return _json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = None
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        raise http.HTTPError(f"HTTP {e.code}: {e.reason}", e.code, body)
    except urllib.error.URLError as e:
        raise http.HTTPError(f"URL Error: {e.reason}")


def _normalize_results(
    response: Dict[str, Any],
    from_date: str,
    to_date: str,
) -> Tuple[List[Dict[str, Any]], str]:
    """Extract reference URLs and AI overview from API response.

    Args:
        response: Raw API response
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)

    Returns:
        Tuple of (web_items, ai_overview_text)
    """
    items = []
    ai_overview = ""

    # Navigate response structure: tasks[0].result[0]
    tasks = response.get("tasks", [])
    if not tasks:
        return items, ai_overview

    task = tasks[0]
    if task.get("status_code") != 20000:
        status_msg = task.get("status_message", "Unknown error")
        sys.stderr.write(f"[DataForSEO] Task error: {status_msg}\n")
        sys.stderr.flush()
        return items, ai_overview

    results = task.get("result", [])
    if not results:
        return items, ai_overview

    result = results[0]
    result_items = result.get("items", [])

    for entry in result_items:
        entry_type = entry.get("type", "")

        # Extract AI overview text (field is "markdown", not "text")
        if entry_type == "ai_overview":
            overview_text = entry.get("markdown", "") or entry.get("text", "")
            if overview_text:
                ai_overview = overview_text

            # Extract references from AI overview
            references = entry.get("references", [])
            for i, ref in enumerate(references):
                url = ref.get("url", "")
                if not url:
                    continue

                # Skip excluded domains
                try:
                    domain = urlparse(url).netloc.lower()
                    if domain in EXCLUDED_DOMAINS:
                        continue
                    if domain.startswith("www."):
                        domain = domain[4:]
                except Exception:
                    domain = ref.get("domain", "")

                title = ref.get("title", "").strip()
                snippet = ref.get("text", ref.get("snippet", "")).strip()

                if not title and not snippet:
                    continue

                items.append({
                    "id": f"D{i+1}",
                    "title": title[:200],
                    "url": url,
                    "source_domain": domain,
                    "snippet": snippet[:500],
                    "date": None,
                    "date_confidence": "low",
                    "relevance": 0.75,  # Higher than Brave — Google curated these
                    "why_relevant": _extract_mention(ai_overview, title, domain),
                })

    return items, ai_overview


def _extract_mention(ai_overview: str, title: str, domain: str) -> str:
    """Extract a brief mention of this source from the AI overview.

    Tries to find the sentence that references this domain/title.

    Args:
        ai_overview: Full AI overview text
        title: Reference title
        domain: Reference domain

    Returns:
        Brief relevant snippet, or empty string
    """
    if not ai_overview:
        return ""

    # Try to find a sentence mentioning the domain
    search_terms = [domain]
    if title:
        # Use first few words of title as search term
        words = title.split()[:4]
        if len(words) >= 2:
            search_terms.append(" ".join(words))

    sentences = ai_overview.replace("\n", " ").split(".")

    for term in search_terms:
        term_lower = term.lower()
        for sentence in sentences:
            if term_lower in sentence.lower():
                clean = sentence.strip()
                if clean:
                    return clean[:150]

    return ""
