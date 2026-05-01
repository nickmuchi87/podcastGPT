"""
Watchlist — manage podcast subscriptions for auto-fetch.

Add RSS feeds to monitor; the auto-fetch script (scripts/auto_fetch.py)
will process new episodes on a schedule and push digests to Telegram.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

from core import database as db

st.set_page_config(page_title="Watchlist — PodcastGPT", page_icon="⭐", layout="wide")

st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; }
    .feed-card {
        background: white;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid #667eea;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    .feed-card.disabled { opacity: 0.6; border-left-color: #999; }
    .feed-meta { color: #666; font-size: 0.8rem; margin-top: 0.25rem; }
    .pill {
        display: inline-block;
        padding: 0.1rem 0.5rem;
        border-radius: 999px;
        font-size: 0.7rem;
        font-weight: 500;
        margin-right: 0.3rem;
    }
    .pill-on { background: #d4edda; color: #155724; }
    .pill-off { background: #f8d7da; color: #721c24; }
    .pill-priority { background: #e8eaf6; color: #3f51b5; }
</style>
""", unsafe_allow_html=True)


def fmt_time(ts: str) -> str:
    if not ts:
        return "never"
    try:
        return datetime.fromisoformat(ts).strftime("%b %d, %H:%M")
    except (ValueError, TypeError):
        return ts


# ── Header ──────────────────────────────────────────────────────────────
st.title("⭐ Watchlist")
st.caption(
    "Subscribe to podcast RSS feeds. The auto-fetch script processes new "
    "episodes on a schedule and pushes digests to Telegram."
)

# Show how to run the cron
with st.expander("ℹ️ How auto-fetch works", expanded=False):
    st.markdown("""
**Setup**

1. Add feeds below (and toggle them on/off as needed)
2. Set environment variables for the providers/Telegram you want to use:
   - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, or `DEEPSEEK_API_KEY`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (optional, for digest)
3. Run the script manually or schedule via cron:

```bash
python scripts/auto_fetch.py
```

```cron
# every day at 6am — process new episodes from your watchlist
0 6 * * * cd /path/to/podcastGPT && python scripts/auto_fetch.py
```

The script:
- Fetches each enabled feed in your watchlist
- Identifies the most recent episode that hasn't been analyzed yet
- Routes it through the smart model router (cost / balanced / quality / speed)
- Saves the analysis to your Library
- If `telegram_notify` is on, pushes a digest to your Telegram bot
""")

# ── Add new feed ────────────────────────────────────────────────────────
st.markdown("### ➕ Add a feed")

with st.form("add_feed", clear_on_submit=True):
    a1, a2 = st.columns([2, 3])
    with a1:
        name = st.text_input("Display name", placeholder="e.g., Odd Lots")
    with a2:
        url = st.text_input("RSS URL", placeholder="https://feeds.example.com/podcast.xml")

    b1, b2, b3 = st.columns(3)
    with b1:
        priority = st.selectbox(
            "Routing priority",
            ["balanced", "quality", "cost", "speed"],
            help="How the smart router picks a model when processing new episodes",
        )
    with b2:
        notify = st.checkbox("Send to Telegram", value=True)
    with b3:
        enabled = st.checkbox("Enabled", value=True)

    submitted = st.form_submit_button("Add to watchlist", type="primary", use_container_width=True)
    if submitted:
        if not name or not url:
            st.error("Name and RSS URL are both required.")
        else:
            new_id = db.add_watchlist(
                name=name.strip(),
                rss_url=url.strip(),
                enabled=enabled,
                telegram_notify=notify,
                routing_priority=priority,
            )
            if new_id == -1:
                st.error("This RSS URL is already in your watchlist.")
            else:
                st.success(f"Added: {name}")
                st.rerun()

st.markdown("---")

# ── Existing watchlist ──────────────────────────────────────────────────
feeds = db.list_watchlist()
st.markdown(f"### 📋 Subscribed feeds ({len(feeds)})")

if not feeds:
    st.info("No feeds yet. Add one above to start auto-fetching.")
else:
    for feed in feeds:
        disabled_cls = "" if feed["enabled"] else " disabled"
        on_pill = '<span class="pill pill-on">ON</span>' if feed["enabled"] else '<span class="pill pill-off">OFF</span>'
        notify_pill = (
            '<span class="pill pill-on">📨 Telegram</span>'
            if feed["telegram_notify"] else ""
        )
        priority_pill = (
            f'<span class="pill pill-priority">'
            f'{feed.get("routing_priority", "balanced")}</span>'
        )
        last_ep = feed.get("last_episode_processed", "") or "—"
        if len(last_ep) > 60:
            last_ep = last_ep[:60] + "…"

        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(
                f'<div class="feed-card{disabled_cls}">'
                f'<div style="font-weight: 600;">{feed["name"]}</div>'
                f'<div class="feed-meta">'
                f'{on_pill}{notify_pill}{priority_pill}'
                f' &nbsp;·&nbsp; last checked: {fmt_time(feed.get("last_checked_at", ""))}'
                f' &nbsp;·&nbsp; last processed: {last_ep}'
                f'</div>'
                f'<div class="feed-meta" style="font-family: monospace;">{feed["rss_url"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with c2:
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                action = "Disable" if feed["enabled"] else "Enable"
                if st.button(action, key=f"toggle_{feed['id']}", use_container_width=True):
                    db.update_watchlist(feed["id"], enabled=not feed["enabled"])
                    st.rerun()
            with sub_c2:
                if st.button("Delete", key=f"del_{feed['id']}", use_container_width=True):
                    db.delete_watchlist(feed["id"])
                    st.rerun()

st.markdown("---")

# ── Quick-add from sample podcasts ──────────────────────────────────────
with st.expander("⚡ Quick-add from app's curated EM podcasts", expanded=False):
    st.caption("Subscribe to any of the pre-loaded EM/macro feeds with one click.")
    SAMPLES = {
        "Odd Lots (Bloomberg)":          "https://www.omnycontent.com/d/playlist/e73c998e-6e60-432f-8610-ae210140c5b1/8a94442e-5a74-4fa2-8b8d-ae27003a8d6b/982f5071-765c-403d-969d-ae27003a8d83/podcast.rss",
        "All-In Podcast":                "https://rss.libsyn.com/shows/254861/destinations/1928300.xml",
        "Clauses & Controversies":       "https://feeds.soundcloud.com/users/soundcloud:users:869013289/sounds.rss",
        "AQ Americas Quarterly":         "https://rss.buzzsprout.com/2066030.rss",
        "DebtTalks":                     "https://feed.ausha.co/QdrlaHqD6Q9l",
        "Geopolitics (Frank McKenna)":   "https://feeds.simplecast.com/DOK9zz6K",
        "Tellimer EM Equities":          "https://emerging-market-equities.buzzsprout.com/1632829.rss",
        "Conflicts of Interest (ACLED)": "https://rss.buzzsprout.com/2538836.rss",
        "Macro Voices":                  "https://feeds.megaphone.fm/macrovoices",
        "Moody's EM Decoded":            "https://feeds.megaphone.fm/moodystalksemergingmarketsdecoded",
    }
    existing_urls = {f["rss_url"] for f in feeds}
    cols = st.columns(2)
    for i, (n, u) in enumerate(SAMPLES.items()):
        with cols[i % 2]:
            already = u in existing_urls
            if st.button(
                f"{'✓ ' if already else '+ '}{n}",
                key=f"sample_{i}",
                use_container_width=True,
                disabled=already,
            ):
                db.add_watchlist(name=n, rss_url=u)
                st.rerun()
