"""YouTube search and transcript extraction via YouTube Data API v3 + youtube-transcript-api.

Uses:
- YouTube Data API v3 for search and video statistics (requires YOUTUBE_API_KEY)
- youtube-transcript-api (pip) for transcript extraction (no auth needed)
"""

import math
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen, Request
import json

# Depth configurations: how many videos to search / transcribe
DEPTH_CONFIG = {
    "quick": 10,
    "default": 20,
    "deep": 40,
}

TRANSCRIPT_LIMITS = {
    "quick": 3,
    "default": 5,
    "deep": 8,
}

# Max words to keep from each transcript
TRANSCRIPT_MAX_WORDS = 500

_API_BASE = "https://www.googleapis.com/youtube/v3"


def _log(msg: str):
    """Log to stderr."""
    sys.stderr.write(f"[YouTube] {msg}\n")
    sys.stderr.flush()


def _extract_core_subject(topic: str) -> str:
    """Extract core subject from verbose query for YouTube search.

    Strips meta/research words to keep only the core product/concept name,
    similar to the approach used in other search modules.
    """
    text = topic.lower().strip()

    # Strip multi-word prefixes
    prefixes = [
        'what are the best', 'what is the best', 'what are the latest',
        'what are people saying about', 'what do people think about',
        'how do i use', 'how to use', 'how to',
        'what are', 'what is', 'tips for', 'best practices for',
    ]
    for p in prefixes:
        if text.startswith(p + ' '):
            text = text[len(p):].strip()

    # Strip individual noise words
    # NOTE: 'tips', 'tricks', 'tutorial', 'guide', 'review', 'reviews'
    # are intentionally KEPT — they're YouTube content types that improve search
    noise = {
        'best', 'top', 'good', 'great', 'awesome', 'killer',
        'latest', 'new', 'news', 'update', 'updates',
        'trending', 'hottest', 'popular', 'viral',
        'practices', 'features',
        'recommendations', 'advice',
        'prompt', 'prompts', 'prompting',
        'methods', 'strategies', 'approaches',
    }
    words = text.split()
    filtered = [w for w in words if w not in noise]

    result = ' '.join(filtered) if filtered else text
    return result.rstrip('?!.')


def _api_get(endpoint: str, params: dict) -> dict:
    """Make a GET request to YouTube Data API v3."""
    url = f"{_API_BASE}/{endpoint}?{urlencode(params)}"
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def search_youtube(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    api_key: str = "",
) -> Dict[str, Any]:
    """Search YouTube via Data API v3.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        depth: 'quick', 'default', or 'deep'
        api_key: YouTube Data API v3 key

    Returns:
        Dict with 'items' list of video metadata dicts.
    """
    if not api_key:
        return {"items": [], "error": "YOUTUBE_API_KEY not set"}

    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    core_topic = _extract_core_subject(topic)

    _log(f"Searching YouTube for '{core_topic}' (since {from_date}, count={count})")

    # search.list — find video IDs (100 quota units per call, max 50 results)
    # We may need multiple pages for deep mode (40 results = 1 call)
    all_video_ids = []
    all_snippets = {}  # video_id -> snippet data
    page_token = None
    remaining = count

    while remaining > 0:
        max_results = min(remaining, 50)
        params = {
            "part": "snippet",
            "type": "video",
            "q": core_topic,
            "publishedAfter": f"{from_date}T00:00:00Z",
            "maxResults": max_results,
            "order": "relevance",
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            data = _api_get("search", params)
        except Exception as e:
            _log(f"Search API error: {e}")
            return {"items": [], "error": f"YouTube API error: {e}"}

        for item in data.get("items", []):
            vid = item.get("id", {}).get("videoId")
            if vid:
                all_video_ids.append(vid)
                all_snippets[vid] = item.get("snippet", {})

        page_token = data.get("nextPageToken")
        remaining -= max_results
        if not page_token:
            break

    if not all_video_ids:
        _log("YouTube search returned 0 results")
        return {"items": []}

    # videos.list — get statistics in batch (1 quota unit per call, up to 50 IDs)
    stats = {}
    for i in range(0, len(all_video_ids), 50):
        batch = all_video_ids[i:i+50]
        try:
            vdata = _api_get("videos", {
                "part": "statistics,contentDetails",
                "id": ",".join(batch),
                "key": api_key,
            })
            for v in vdata.get("items", []):
                s = v.get("statistics", {})
                stats[v["id"]] = {
                    "views": int(s.get("viewCount", 0)),
                    "likes": int(s.get("likeCount", 0)),
                    "comments": int(s.get("commentCount", 0)),
                }
        except Exception as e:
            _log(f"Videos API error: {e}")

    # Build items list
    items = []
    for vid in all_video_ids:
        snippet = all_snippets.get(vid, {})
        st = stats.get(vid, {"views": 0, "likes": 0, "comments": 0})

        # Parse date from snippet.publishedAt (ISO 8601)
        published = snippet.get("publishedAt", "")
        date_str = published[:10] if len(published) >= 10 else None

        items.append({
            "video_id": vid,
            "title": snippet.get("title", ""),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "channel_name": snippet.get("channelTitle", ""),
            "date": date_str,
            "engagement": {
                "views": st["views"],
                "likes": st["likes"],
                "comments": st["comments"],
            },
            "duration": None,
            "relevance": 0.7,
            "why_relevant": f"YouTube video about {core_topic}",
        })

    # Soft date filter: prefer recent items but fall back to all if too few
    recent = [i for i in items if i["date"] and i["date"] >= from_date]
    if len(recent) >= 3:
        items = recent
        _log(f"Found {len(items)} videos within date range")
    else:
        _log(f"Found {len(items)} videos ({len(recent)} within date range, keeping all)")

    # Sort by views descending
    items.sort(key=lambda x: x["engagement"]["views"], reverse=True)

    return {"items": items}


def fetch_transcript(video_id: str) -> Optional[str]:
    """Fetch transcript for a YouTube video using youtube-transcript-api.

    Args:
        video_id: YouTube video ID

    Returns:
        Plaintext transcript string, or None if no captions available.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        _log("youtube-transcript-api not installed")
        return None

    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
    except Exception:
        # Fallback: try any available language
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception:
            return None

    text = ' '.join(entry['text'] for entry in transcript_list)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Truncate to max words
    words = text.split()
    if len(words) > TRANSCRIPT_MAX_WORDS:
        text = ' '.join(words[:TRANSCRIPT_MAX_WORDS]) + '...'

    return text if text else None


def fetch_transcripts_parallel(
    video_ids: List[str],
    max_workers: int = 5,
) -> Dict[str, Optional[str]]:
    """Fetch transcripts for multiple videos in parallel.

    Args:
        video_ids: List of YouTube video IDs
        max_workers: Max parallel fetches

    Returns:
        Dict mapping video_id to transcript text (or None).
    """
    if not video_ids:
        return {}

    _log(f"Fetching transcripts for {len(video_ids)} videos")

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_transcript, vid): vid
            for vid in video_ids
        }
        for future in as_completed(futures):
            vid = futures[future]
            try:
                results[vid] = future.result()
            except Exception:
                results[vid] = None

    got = sum(1 for v in results.values() if v)
    _log(f"Got transcripts for {got}/{len(video_ids)} videos")
    return results


def search_and_transcribe(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    api_key: str = "",
) -> Dict[str, Any]:
    """Full YouTube search: find videos, then fetch transcripts for top results.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        depth: 'quick', 'default', or 'deep'
        api_key: YouTube Data API v3 key

    Returns:
        Dict with 'items' list. Each item has a 'transcript_snippet' field.
    """
    # Step 1: Search
    search_result = search_youtube(topic, from_date, to_date, depth, api_key=api_key)
    items = search_result.get("items", [])

    if not items:
        return search_result

    # Step 2: Fetch transcripts for top N by views
    transcript_limit = TRANSCRIPT_LIMITS.get(depth, TRANSCRIPT_LIMITS["default"])
    top_ids = [item["video_id"] for item in items[:transcript_limit]]
    transcripts = fetch_transcripts_parallel(top_ids)

    # Step 3: Attach transcripts to items
    for item in items:
        vid = item["video_id"]
        transcript = transcripts.get(vid)
        item["transcript_snippet"] = transcript or ""

    return {"items": items}


def parse_youtube_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse YouTube search response to normalized format.

    Returns:
        List of item dicts ready for normalization.
    """
    return response.get("items", [])
