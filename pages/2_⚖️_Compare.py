"""
Compare — side-by-side analysis of two podcast episodes.

Useful for tracking how views evolve over time, or contrasting
takes from different guests on the same topic.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, List, Optional

import streamlit as st

from core import database as db

st.set_page_config(page_title="Compare — PodcastGPT", page_icon="⚖️", layout="wide")

st.markdown("""
<style>
    .compare-card {
        background: white;
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
    .compare-header {
        font-weight: 600;
        font-size: 1.05rem;
        margin-bottom: 0.5rem;
        color: #333;
    }
    .compare-meta { color: #666; font-size: 0.85rem; margin-bottom: 0.75rem; }
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
    .pill-shared { background: #c8e6c9; color: #1b5e20; }
    .pill-unique { background: #e8eaf6; color: #3f51b5; }
</style>
""", unsafe_allow_html=True)


def sentiment_pill(s: str) -> str:
    s_lower = (s or "").lower()
    cls = "pill-neutral"
    if "bull" in s_lower:
        cls = "pill-bull"
    elif "bear" in s_lower:
        cls = "pill-bear"
    return f'<span class="pill {cls}">{s or "—"}</span>'


def render_episode_card(ep: Dict[str, Any], other_ep: Optional[Dict[str, Any]] = None):
    """Render one episode column. Highlights shared vs unique items if `other_ep` given."""
    other_themes = set(other_ep.get("themes", [])) if other_ep else set()
    other_regions = set(other_ep.get("regions", [])) if other_ep else set()
    other_countries = set(other_ep.get("countries", [])) if other_ep else set()

    st.markdown(f'<div class="compare-card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="compare-header">{ep["episode_title"]}</div>'
        f'<div class="compare-meta">🎙️ {ep["podcast_title"]} · 👤 {ep.get("guest","Unknown")} · '
        f'🕒 {ep.get("created_at","")[:10]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div>{sentiment_pill(ep.get("sentiment",""))}</div>', unsafe_allow_html=True)
    st.markdown("&nbsp;", unsafe_allow_html=True)

    # Themes (shared vs unique)
    st.markdown("**Themes:**")
    theme_html = ""
    for t in ep.get("themes", []):
        cls = "pill-shared" if t in other_themes and other_ep else "pill-unique"
        theme_html += f'<span class="pill {cls}">{t}</span>'
    st.markdown(theme_html or "—", unsafe_allow_html=True)

    # Regions
    st.markdown("**Regions:**")
    region_html = ""
    for r in ep.get("regions", []):
        cls = "pill-shared" if r in other_regions and other_ep else "pill-unique"
        region_html += f'<span class="pill {cls}">{r}</span>'
    st.markdown(region_html or "—", unsafe_allow_html=True)

    # Countries
    if ep.get("countries"):
        st.markdown("**Countries:**")
        country_html = ""
        for c in ep["countries"][:8]:
            cls = "pill-shared" if c in other_countries and other_ep else "pill-unique"
            country_html += f'<span class="pill {cls}">{c}</span>'
        st.markdown(country_html, unsafe_allow_html=True)

    # Sentiment scores
    bull = ep.get("bullish_score", 0)
    bear = ep.get("bearish_score", 0)
    st.markdown(f"**Sentiment scores:** 🟢 {bull} bull / 🔴 {bear} bear (net: {bull-bear:+d})")

    # Summary
    with st.expander("Summary", expanded=False):
        st.write(ep.get("summary", "") or "—")

    # Highlights
    highlights = (ep.get("highlights") or "").split("\n")
    highlights = [h.strip().lstrip("•-* ") for h in highlights if h.strip()]
    if highlights:
        with st.expander(f"Key Takeaways ({len(highlights)})", expanded=False):
            for h in highlights[:8]:
                st.markdown(f"- {h}")

    st.markdown("</div>", unsafe_allow_html=True)


# ── UI ─────────────────────────────────────────────────────────────────
st.title("⚖️ Compare Episodes")
st.caption("Side-by-side analysis. Shared themes/regions appear in green, unique in blue.")

episodes = db.list_episodes(limit=100)
if len(episodes) < 2:
    st.info("Compare needs at least 2 analyzed episodes. Process more podcasts first.")
    st.stop()

# Episode picker
def label(e: Dict[str, Any]) -> str:
    title = e["episode_title"][:60] + ("…" if len(e["episode_title"]) > 60 else "")
    return f"{title} — {e['podcast_title']}"

ep_options = {label(e): e for e in episodes}
ep_labels = list(ep_options.keys())

c1, c2 = st.columns(2)
with c1:
    left_label = st.selectbox("Episode A", ep_labels, index=0)
with c2:
    default_b = 1 if len(ep_labels) > 1 else 0
    right_label = st.selectbox("Episode B", ep_labels, index=default_b)

if left_label == right_label:
    st.warning("Select two different episodes to compare.")
    st.stop()

left = ep_options[left_label]
right = ep_options[right_label]

st.markdown("---")

# Cross-episode analysis summary
shared_themes = set(left.get("themes", [])) & set(right.get("themes", []))
shared_regions = set(left.get("regions", [])) & set(right.get("regions", []))
shared_countries = set(left.get("countries", [])) & set(right.get("countries", []))

s1, s2, s3, s4 = st.columns(4)
s1.metric("Shared Themes", len(shared_themes))
s2.metric("Shared Regions", len(shared_regions))
s3.metric("Shared Countries", len(shared_countries))

# Sentiment delta
left_net = left.get("bullish_score", 0) - left.get("bearish_score", 0)
right_net = right.get("bullish_score", 0) - right.get("bearish_score", 0)
s4.metric("Sentiment Δ (B − A)", right_net - left_net)

st.markdown("---")

# Side-by-side
left_col, right_col = st.columns(2)
with left_col:
    render_episode_card(left, other_ep=right)
with right_col:
    render_episode_card(right, other_ep=left)
