"""Supadata Transcript API client.

Fetches transcripts via api.supadata.ai with mode=auto (captions → AI speech-to-text).
Supports YouTube URLs and X/Twitter URLs.
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# Max words to keep from each transcript (matches youtube_yt)
TRANSCRIPT_MAX_WORDS = 500

_API_BASE = "https://api.supadata.ai/v1"


def _log(msg: str):
    """Log to stderr."""
    sys.stderr.write(f"[Supadata] {msg}\n")
    sys.stderr.flush()


def _api_get(endpoint: str, params: dict, api_key: str, timeout: int = 30) -> dict:
    """Make a GET request to Supadata API."""
    url = f"{_API_BASE}/{endpoint}?{urlencode(params)}"
    req = Request(url, headers={
        "x-api-key": api_key,
        "Accept": "application/json",
    })
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode()), resp.status


def _truncate(text: str, max_words: int = TRANSCRIPT_MAX_WORDS) -> str:
    """Truncate text to max_words."""
    words = text.split()
    if len(words) > max_words:
        return ' '.join(words[:max_words]) + '...'
    return text


def _poll_job(job_id: str, api_key: str, max_wait: int = 60, interval: int = 3) -> Optional[str]:
    """Poll an async job until completion or timeout."""
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            url = f"{_API_BASE}/transcribe/status/{job_id}"
            req = Request(url, headers={
                "x-api-key": api_key,
                "Accept": "application/json",
            })
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            status = data.get("status")
            if status == "completed":
                content = data.get("content") or ""
                return content if content else None
            elif status == "failed":
                _log(f"Job {job_id} failed: {data.get('error', 'unknown')}")
                return None
            # else: still processing, continue polling
        except Exception as e:
            _log(f"Poll error for job {job_id}: {e}")
            return None

    _log(f"Job {job_id} timed out after {max_wait}s")
    return None


def fetch_transcript(video_url: str, api_key: str) -> Optional[str]:
    """Fetch transcript for a video URL via Supadata API.

    Args:
        video_url: YouTube or X/Twitter video URL
        api_key: Supadata API key

    Returns:
        Plaintext transcript string (truncated to 500 words), or None on failure.
    """
    if not api_key:
        return None

    _log(f"Fetching transcript for {video_url}")

    try:
        params = {"url": video_url, "mode": "auto"}
        url = f"{_API_BASE}/transcribe?{urlencode(params)}"
        req = Request(url, headers={
            "x-api-key": api_key,
            "Accept": "application/json",
        })

        with urlopen(req, timeout=30) as resp:
            status = resp.status
            data = json.loads(resp.read().decode())

        if status == 200:
            # Sync response — transcript ready
            content = data.get("content") or ""
            if content:
                return _truncate(content.strip())
            return None

        elif status == 202:
            # Async — poll for result
            job_id = data.get("jobId")
            if not job_id:
                _log("Got 202 but no jobId")
                return None
            _log(f"Async job started: {job_id}")
            content = _poll_job(job_id, api_key)
            if content:
                return _truncate(content.strip())
            return None

        else:
            _log(f"Unexpected status {status}")
            return None

    except HTTPError as e:
        if e.code == 202:
            # urllib treats 202 as success in some versions; handle body
            try:
                data = json.loads(e.read().decode())
                job_id = data.get("jobId")
                if job_id:
                    _log(f"Async job started: {job_id}")
                    content = _poll_job(job_id, api_key)
                    if content:
                        return _truncate(content.strip())
            except Exception:
                pass
            return None
        _log(f"HTTP error {e.code}: {e.reason}")
        return None
    except (URLError, OSError) as e:
        _log(f"Network error: {e}")
        return None
    except Exception as e:
        _log(f"Error: {e}")
        return None


def fetch_transcripts_batch(
    urls: List[str],
    api_key: str,
    max_workers: int = 3,
) -> Dict[str, Optional[str]]:
    """Fetch transcripts for multiple URLs in parallel.

    Args:
        urls: List of video URLs (YouTube or X/Twitter)
        api_key: Supadata API key
        max_workers: Max parallel fetches

    Returns:
        Dict mapping url to transcript text (or None).
    """
    if not urls or not api_key:
        return {}

    _log(f"Batch fetching transcripts for {len(urls)} URLs")

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_transcript, url, api_key): url
            for url in urls
        }
        for future in as_completed(futures):
            url = futures[future]
            try:
                results[url] = future.result()
            except Exception:
                results[url] = None

    got = sum(1 for v in results.values() if v)
    _log(f"Got transcripts for {got}/{len(urls)} URLs")
    return results
