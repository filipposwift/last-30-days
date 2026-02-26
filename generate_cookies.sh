#!/bin/bash
# Generate youtube_cookies.txt from Chrome browser cookies.
# Run this locally, then copy the file to OpenClaw:
#   cp youtube_cookies.txt ~/.openclaw/skills/last-30-days/
#
# Cookies expire periodically — re-run when YouTube returns 403.

yt-dlp --cookies-from-browser chrome --cookies youtube_cookies_raw.txt "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --skip-download --no-warnings 2>/dev/null

# Keep only YouTube/Google cookies (strip all other domains)
head -4 youtube_cookies_raw.txt > youtube_cookies.txt
grep -E "^(\\.youtube\\.com|www\\.youtube\\.com|\\.google\\.com|accounts\\.google\\.com)\s" youtube_cookies_raw.txt >> youtube_cookies.txt
rm youtube_cookies_raw.txt

echo "Done — $(grep -c '^[^#]' youtube_cookies.txt) cookies saved to youtube_cookies.txt"
