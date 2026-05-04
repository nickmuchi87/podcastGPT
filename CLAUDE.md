# PodcastGPT — Codebase Guide for Claude

**Streamlit app that turns podcast episodes into structured EM (Emerging
Markets) Portfolio Manager research.** Multi-page UI with SQLite-backed
persistence, smart model routing across 4 LLM providers, and a cron-ready
auto-fetch script.

## Architecture

```
podcastGPT/
├── podcast_frontend.py        # Main Streamlit page (entry for `streamlit run`)
├── core/                      # Pure-logic modules (no Streamlit deps unless noted)
│   ├── database.py            # SQLite persistence (episodes / watchlist / alerts)
│   ├── models.py              # Smart router across Claude/GPT/Gemini/DeepSeek
│   ├── transcript.py          # Transcript discovery (YouTube / Listen Notes / web)
│   ├── insights.py            # EM extraction (sentiment, regions, themes, countries)
│   └── exports.py             # Markdown / HTML / PDF / Telegram delivery
├── pages/                     # Streamlit auto-discovers; ordered by file prefix
│   ├── 0_📊_Dashboard.py      # KPIs + sentiment trend + corpus stats
│   ├── 1_📚_Library.py        # Searchable archive (search, filters, tags, notes)
│   ├── 2_⚖️_Compare.py        # Side-by-side diff of two episodes
│   ├── 3_💬_QA.py             # Chat with any analyzed transcript
│   ├── 4_⭐_Watchlist.py      # RSS feed subscriptions
│   ├── 5_🔄_Synthesis.py      # Cross-episode meta-analysis
│   └── 6_🔔_Alerts.py         # Saved searches → Telegram notifications
├── scripts/
│   └── auto_fetch.py          # Cron-ready: process new episodes, send digests/alerts
├── content/
│   └── podcastgpt.db          # SQLite DB (gitignored)
├── packages.txt               # System packages (ffmpeg for pydub)
├── requirements.txt           # Python deps
└── .streamlit/config.toml     # Streamlit Cloud config
```

## Data flow

**Manual processing** (Streamlit UI):
1. User picks RSS feed → `parse_podcast_feed` (cached)
2. User selects episode → `process_podcast(audio_url, link, podcast, episode)`
3. `core.transcript.find_transcript()` runs 6-step search:
   YouTube URL → Listen Notes URL → episode webpage → Listen Notes auto-search → YouTube search → web search
4. If no online transcript: download audio → Whisper transcription
5. `core.models.generate_summary()` smart-routes to best LLM
6. `core.insights.extract_em_insights()` runs keyword/sentiment extraction
7. `db.save_episode()` persists with full transcript
8. `core.exports.deliver_to_telegram()` (optional) pushes digest

**Auto-fetch** (cron):
- `scripts/auto_fetch.py` does the same flow without Streamlit
- Skips Whisper (heavy + needs ffmpeg in cron context)
- Evaluates alerts after each save
- Updates watchlist watermark

## Smart router (`core/models.py`)

10 models registered across 4 providers. Each `ModelSpec` has cost_in/out,
context_window, tier (1 = top, 3 = budget), quality_score (0-100),
supported tasks, and speed.

**Routing modes:**
- `cost`: cheapest viable model
- `balanced`: quality minus est-cost penalty (default)
- `quality`: highest quality_score
- `speed`: fastest model

**Tasks:** `summary`, `deep_summary`, `qa`, `classification`, `long_context`,
`batch`, `complex_reasoning`

Auto-fallback: up to 3 attempts, excluded list prevents retrying broken
providers.

API keys from env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`, `DEEPSEEK_API_KEY`) OR Streamlit session state (the
sidebar inputs). Key lookup uses `streamlit.runtime.exists()` to avoid
warnings outside Streamlit context.

## SQLite schema (`core/database.py`)

Three tables:
- `episodes`: title, podcast, guest, summary, highlights, full_transcript,
  sentiment, regions/themes/countries/asset_classes (JSON arrays), scores,
  full_result (JSON), user_notes, tags (JSON array)
- `watchlist`: feed name, rss_url, enabled, telegram_notify,
  routing_priority, last_checked_at, last_episode_processed
- `alerts`: name, keyword/region/theme/country/sentiment criteria,
  trigger_count, last_triggered_at/_episode

Schema migrations are idempotent: `init_db()` uses `CREATE TABLE IF NOT
EXISTS` and adds columns via `ALTER TABLE` wrapped in try/except for
existing DBs.

## Testing

Streamlit's `AppTest` is used for page render smoke tests:

```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("pages/1_📚_Library.py", default_timeout=30)
at.run()
assert not at.exception
```

The DB is at `content/podcastgpt.db`. To seed a clean test DB, see the
`/tmp/seed_test_data.py` pattern (4 episodes covering bullish India,
bearish Turkey, mixed China, bullish LatAm).

## Deployment

**Streamlit Cloud:**
- Entry point: `podcast_frontend.py`
- Set `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / etc. in Settings → Secrets
- `packages.txt` installs `ffmpeg` for pydub
- `.streamlit/config.toml` sets headless mode

**Cron auto-fetch:**
```bash
0 6 * * * cd /path/to/podcastGPT && python scripts/auto_fetch.py
```
Required env: at least one provider API key. Optional: `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID` for digest/alerts.

## Important gotchas

- **Pydub import is guarded** — `PYDUB_AVAILABLE` flag, since ffmpeg may not
  be installed everywhere
- **Gemini SDK import is guarded with bare `Exception`** — old crypto bindings
  can pyo3-panic on some systems
- **DeepSeek uses OpenAI-compatible API** via `base_url=https://api.deepseek.com`
  — no extra Python dep
- **Transcript truncation**: `process_podcast` stores the full transcript
  in `result['_full_transcript']` for downstream Q&A, but truncates
  `podcast_details` to 5000 chars for storage in `full_result`
- **Auto-fetch never uses Whisper** — too heavy for cron; skips episodes
  without online transcripts
- **`_provider_key` checks both env vars AND `st.session_state`** — that's how
  sidebar API key inputs work
- **YouTube transcript extraction** uses the timedtext XML API (no pip dep),
  preferring English manual captions over auto-generated ones
- **PDF export uses weasyprint** (optional) — falls back to self-contained
  HTML download if weasyprint isn't installed
- **Q&A streaming** — `stream_chat_with_transcript()` yields chunks; all 4
  providers support streaming. Falls back to non-streaming on error

## When adding a feature

1. **New page** — drop `pages/N_emoji_Name.py`. Streamlit auto-discovers.
   Always `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
   at the top so `from core import ...` works.
2. **New model** — add a `ModelSpec` to `MODELS` in `core/models.py`. Set
   `quality_score` realistically; the router will route work to it.
3. **New schema column** — add to the `CREATE TABLE` in `init_db()` AND
   add an idempotent `ALTER TABLE` for existing DBs.
4. **New core/ helper** — keep it Streamlit-free if possible so cron can
   reuse it. Use callbacks for progress reporting.
5. **Don't push to `main` from sandbox** — only `claude/...` branches are
   allowed by the proxy. Open a PR on GitHub instead.
