# /last-30-days

Research skill maintained by Filippo for use on [OpenClaw](https://github.com/openclaw/openclaw).

Research any topic across Reddit, X, YouTube, and the web from the last 30 days. Surface what people are actually discussing, recommending, and debating right now — then write copy-paste-ready prompts.

## Typical Results

| Topic | Reddit | X | YouTube | Web |
|-------|--------|---|---------|-----|
| Nano Banana Pro | — | 32 posts, 164 likes | 5 videos, 98K views, 5 transcripts | 10 pages |
| Seedance 2.0 access | 3 threads, 114 upvotes | 31 posts, 191 likes | 20 videos, 685K views, 4 transcripts | 10 pages |
| OpenClaw use cases | 35 threads, 1,130 upvotes | 23 posts | 20 videos, 1.57M views, 5 transcripts | 10 pages |
| YouTube thumbnails | 7 threads, 654 upvotes | 32 posts, 110 likes | 18 videos, 6.15M views, 5 transcripts | 30 pages |
| AI generated ads | 12 threads | 29 posts, 101 likes | 3 videos, 83K views, 3 transcripts | 30 pages |

## Requirements

| Service | Env Variable | Required |
|---------|-------------|----------|
| Reddit (OpenAI Responses API) | `OPENAI_API_KEY` | Yes |
| X (xAI API) | `XAI_API_KEY` | Yes |
| YouTube (Data API v3) | `YOUTUBE_API_KEY` | No |
| Web search (Brave) | `BRAVE_API_KEY` | No |
| Web search (Parallel AI) | `PARALLEL_API_KEY` | No |
| Web search (OpenRouter) | `OPENROUTER_API_KEY` | No |
| Google AI Overview (DataForSEO) | `DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD` | No |

**Minimum:** `OPENAI_API_KEY` + `XAI_API_KEY` gives you Reddit + X. YouTube activates when `YOUTUBE_API_KEY` is set.

**Runtime:** Python 3 + `pip install youtube-transcript-api`.

## Installation

```bash
# Claude Code
git clone <this-repo> ~/.claude/skills/last-30-days

# Verify everything works
python3 scripts/last30days.py --diagnose
```

## Usage

```
/last-30-days <topic>
```

## Options

| Flag | Description |
|------|-------------|
| `--days=N` | Look back N days instead of 30 |
| `--quick` | Faster, fewer sources (8-12 each) |
| `--deep` | Comprehensive (50-70 Reddit, 40-60 X) |
| `--sources=reddit` | Reddit only |
| `--sources=x` | X only |
| `--include-web` | Add native web search (requires web search API key) |
| `--store` | Persist findings to SQLite (for watchlist) |
| `--diagnose` | Show source availability and exit |

## How It Works

1. **Phase 1 — Discovery:** Searches Reddit (OpenAI API), X (xAI API), YouTube (Data API v3), web
2. **Phase 2 — Supplemental:** Extracts @handles and r/subreddits from Phase 1, runs targeted follow-ups
3. **Enrichment:** Fetches real Reddit metrics (upvotes, comments) via public JSON
4. **Scoring:** Relevance 45%, recency 25%, engagement 30%
5. **Synthesis:** The agent synthesizes everything into a report with stats

Model fallback chain for Reddit: gpt-4.1 → gpt-4o → gpt-4o-mini.

---

## Examples

These show how different query types produce different outputs. Useful reference for agents.

### Prompting: Nano Banana Pro (JSON format discovery)

**Query:** `/last-30-days nano banana pro prompts for Gemini`

The skill discovered that JSON prompts are the dominant format for this tool — not prose. Key patterns found:

1. Use JSON structure with `image_type`, `subject`, `lighting`, `camera_settings` fields
2. Add `"face_id"` with a reference image URL — the secret to consistency
3. Separate subjects into distinct objects to prevent "concept bleeding"
4. Use camera/lens metadata (aperture, focal length, ISO) for hidden photorealism control
5. 14 reference images max for brand/character consistency

**Sample generated prompt** (after user asked for "a mock-up of an app for moms who swim"):

```json
{
  "image_type": "UI mockup",
  "device": { "frame": "iPhone 16 Pro", "display": "realistic screen with subtle reflection" },
  "app_concept": "SwimMom - fitness and community app for mothers who swim",
  "screen": "home dashboard",
  "color_palette": { "primary": "#4ECDC4", "secondary": "#FF6B6B" },
  "layout": {
    "header": "greeting with wave icon, profile avatar top right",
    "hero_card": "today's swim stats with circular progress ring",
    "section_2": "horizontal scroll of upcoming swim meetups",
    "section_3": "two cards - My Goals with streak counter, Find a Pool with map pin"
  }
}
```

This shows how /last-30-days learns the **format the community actually uses**, not what you'd guess.

### Recommendations: Best ClawdBot Use Cases

**Query:** `/last-30-days best clawdbot use cases`

When query type is RECOMMENDATIONS, the output is a ranked list of specific things with sources:

| Rank | Use Case | Mentions | Top Sources |
|------|----------|----------|-------------|
| 1 | Email/Calendar automation | 8x | r/selfhosted, @dreetje, @danpeguine |
| 2 | Task management via chat | 6x | r/LocalLLaMA, @danpeguine |
| 3 | Overnight coding agent | 5x | @bffmike (225 likes), r/LocalLLaMA |
| 4 | Smart home + life admin | 5x | r/selfhosted, VelvetShark |
| 5 | Browser automation | 4x | @steipete (243 likes) |

Notable single mentions: custom meditation with TTS, built a website from phone while putting baby to sleep, Ray-Ban Meta glasses integration.

**Stats:** 9 Reddit threads (161 upvotes) + 19 X posts (2,018 likes) from r/LocalLLaMA, r/selfhosted, @steipete, @danpeguine

This shows how RECOMMENDATIONS mode extracts **specific names and counts**, not generic advice.

### News: DeepSeek R1 (Community Sentiment)

**Query:** `/last-30-days what are people saying about DeepSeek R1`

NEWS/GENERAL mode synthesizes community sentiment with key insights:

1. **Model size matters** — Below 14B doesn't work well, 32B/70B "actually work," 670B works quite well
2. **Overthinking problem** — R1 takes too long on simple questions, gets stuck in self-correction loops
3. **Open source significance** — The real story is RL, distillation, and cost efficiency
4. **Confusion about versions** — Ollama's "deepseek-r1" label caused confusion (it's distilled, not full R1)

Community sentiment curated from both sides:
- Positive: "R1 is insanely good for the price" ($0.55/M tokens vs $60 for o1-pro)
- Negative: "Stop using R1 for deep research - it hallucinates"

**Stats:** 10 Reddit threads (1,200+ upvotes) + 10 X posts (5,000+ likes) from r/LocalLLaMA, r/DeepSeek

### Workflow Discovery: Codex + Claude Code

**Query:** `/last-30-days how do I use Codex with Claude Code on same app`

The skill discovered an **emerging workflow pattern** not found in any docs:

1. **MCP Integration** — Add Codex as MCP server: `claude mcp add codex-cli -- npx -y codex-mcp-server`
2. **Review Loop** — Claude implements → Codex reviews → Claude fixes → optional final review
3. **Task Division** — Claude for planning/coding, Codex for review/debugging

When the user asked "how do I build a review loop workflow", the skill generated a concrete step-by-step setup with commands.

**Stats:** 17 Reddit threads (906 upvotes) + 20 X posts (3,750 likes) from r/ClaudeCode, r/ClaudeAI

---

## Data & Privacy

| Destination | Data Sent |
|-------------|-----------|
| `api.openai.com` | Search query |
| `api.x.ai` | Search query |
| `reddit.com` | Thread URLs (public JSON) |
| `googleapis.com` (YouTube Data API v3) | Search query |
| `youtube.com` (youtube-transcript-api) | Video ID (transcript fetch) |
| Optional web APIs (Brave/Parallel/OpenRouter) | Search query |
| DataForSEO (`api.dataforseo.com`) | Search query |

API keys are never shared across providers. Research data stays local.
