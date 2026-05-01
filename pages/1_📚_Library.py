"""
Library — searchable archive of analyzed podcast episodes.

Browse all past analyses, filter by sentiment/region/podcast, and
view sentiment trends across the corpus.
"""

import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

from core import database as db

st.set_page_config(page_title="Library — PodcastGPT", page_icon="📚", layout="wide")

# Reuse the styling from main app
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; }
    .episode-row {
        background: white;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid #667eea;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    .episode-meta { color: #666; font-size: 0.85rem; }
    .pill {
        display: inline-block;
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        font-size: 0.75rem;
        margin-right: 0.4rem;
        font-weight: 500;
    }
    .pill-bull { background: #d4edda; color: #155724; }
    .pill-bear { background: #f8d7da; color: #721c24; }
    .pill-neutral { background: #fff3cd; color: #856404; }
    .pill-region { background: #e8eaf6; color: #3f51b5; }
</style>
""", unsafe_allow_html=True)


def sentiment_pill(sentiment: str) -> str:
    s = (sentiment or "").lower()
    cls = "pill-neutral"
    if "bull" in s:
        cls = "pill-bull"
    elif "bear" in s:
        cls = "pill-bear"
    return f'<span class="pill {cls}">{sentiment or "—"}</span>'


def _format_timestamp(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%b %d, %Y · %H:%M")
    except (ValueError, TypeError):
        return ts or "—"


# ── Header ─────────────────────────────────────────────────────────────
st.title("📚 Episode Library")
st.caption("All analyzed podcast episodes, searchable and filterable.")

# ── Stats banner ───────────────────────────────────────────────────────
stats = db.get_stats()
total = stats["total_episodes"]
sentiments = stats["sentiment_breakdown"]

if total == 0:
    st.info("No episodes analyzed yet. Head over to the main page to process your first podcast.")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Total Episodes", total)
with m2:
    st.metric("Bullish", sentiments.get("Bullish", 0))
with m3:
    st.metric("Bearish", sentiments.get("Bearish", 0))
with m4:
    st.metric("Neutral/Mixed", sentiments.get("Neutral/Mixed", 0))

st.markdown("---")

# ── Filters ────────────────────────────────────────────────────────────
with st.container():
    f1, f2, f3, f4 = st.columns([3, 1.5, 2, 1.5])
    with f1:
        search = st.text_input("🔍 Search", placeholder="Title, guest, summary…")
    with f2:
        sentiment_filter = st.selectbox(
            "Sentiment", ["All", "Bullish", "Bearish", "Neutral/Mixed"]
        )
    with f3:
        podcasts = ["All"] + db.get_distinct_podcasts()
        podcast_filter = st.selectbox("Podcast", podcasts)
    with f4:
        regions = ["All", "Latin America", "EMEA", "Asia ex-China", "China",
                   "Frontier Markets", "GCC/Middle East", "Eastern Europe"]
        region_filter = st.selectbox("Region", regions)

# Build filter args
filters = {
    "search": search,
    "sentiment": None if sentiment_filter == "All" else sentiment_filter,
    "podcast": None if podcast_filter == "All" else podcast_filter,
    "region": None if region_filter == "All" else region_filter,
}
episodes = db.list_episodes(**filters)

st.caption(f"Showing **{len(episodes)}** episode(s)")

# ── Sentiment trend chart ──────────────────────────────────────────────
if len(episodes) >= 3:
    with st.expander("📈 Sentiment Trend", expanded=False):
        chart_data = []
        for e in reversed(episodes):  # chronological
            try:
                date = datetime.fromisoformat(e["created_at"]).strftime("%m-%d")
            except (ValueError, TypeError):
                continue
            score = e["bullish_score"] - e["bearish_score"]
            chart_data.append({"Date": date, "Net Sentiment": score})
        if chart_data:
            st.line_chart(chart_data, x="Date", y="Net Sentiment", height=220)
            st.caption("Net sentiment = bullish signals minus bearish signals per episode")

st.markdown("---")

# ── Episode list ───────────────────────────────────────────────────────
for ep in episodes:
    title = ep["episode_title"]
    podcast = ep["podcast_title"]
    guest = ep.get("guest", "Unknown")
    sentiment = ep.get("sentiment", "—")
    regions_list = ep.get("regions", [])[:3]
    themes_list = ep.get("themes", [])[:3]
    summary = (ep.get("summary") or "")[:240]
    when = _format_timestamp(ep.get("created_at", ""))

    region_pills = "".join(
        f'<span class="pill pill-region">{r}</span>' for r in regions_list
    )

    with st.container():
        col_main, col_actions = st.columns([5, 1])
        with col_main:
            st.markdown(f"""
            <div class="episode-row">
                <div style="font-weight:600; font-size:1.05rem;">{title}</div>
                <div class="episode-meta">
                    🎙️ {podcast} &nbsp; · &nbsp; 👤 {guest} &nbsp; · &nbsp; 🕒 {when}
                </div>
                <div style="margin-top: 0.5rem;">
                    {sentiment_pill(sentiment)} {region_pills}
                </div>
                <div style="margin-top: 0.5rem; color: #444; font-size: 0.9rem;">
                    {summary}{'…' if len(summary) >= 240 else ''}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_actions:
            st.write("")
            if st.button("View", key=f"view_{ep['id']}", use_container_width=True):
                st.session_state["selected_library_id"] = ep["id"]
                st.session_state["last_result"] = ep["full_result"]
                st.session_state["selected_episode"] = title
                st.success("Loaded! Switch to the main page to see full analysis.")
            if st.button("Delete", key=f"del_{ep['id']}", use_container_width=True):
                db.delete_episode(ep["id"])
                st.rerun()
