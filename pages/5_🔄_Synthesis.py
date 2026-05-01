"""
Synthesis — cross-episode meta-analysis.

Pick a topic / region / theme and a question; the app pulls all
matching episodes from the library and asks the best model to
synthesize a coherent meta-view.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, List

import streamlit as st

from core import database as db
from core import models as model_router

st.set_page_config(page_title="Synthesis — PodcastGPT", page_icon="🔄", layout="wide")

st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; }
    .ep-mini {
        background: #f8f9fa;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        margin-bottom: 0.4rem;
        border-left: 3px solid #667eea;
        font-size: 0.85rem;
    }
    .synth-output {
        background: white;
        padding: 1.25rem 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        line-height: 1.6;
    }
    .pill {
        display: inline-block;
        padding: 0.1rem 0.5rem;
        border-radius: 999px;
        font-size: 0.7rem;
        font-weight: 500;
        margin-right: 0.3rem;
    }
    .pill-bull { background: #d4edda; color: #155724; }
    .pill-bear { background: #f8d7da; color: #721c24; }
    .pill-neutral { background: #fff3cd; color: #856404; }
</style>
""", unsafe_allow_html=True)


def sentiment_pill(s: str) -> str:
    sl = (s or "").lower()
    cls = "pill-neutral"
    if "bull" in sl:
        cls = "pill-bull"
    elif "bear" in sl:
        cls = "pill-bear"
    return f'<span class="pill {cls}">{s or "—"}</span>'


# ── Header ──────────────────────────────────────────────────────────────
st.title("🔄 Cross-Episode Synthesis")
st.caption(
    "Synthesize views across multiple episodes. Filter by topic, then ask a question."
)

avail = model_router.available_providers()
if not avail:
    st.error(
        "No AI provider keys configured. Add at least one of "
        "OPENAI / ANTHROPIC / GEMINI / DEEPSEEK API keys in the main page sidebar."
    )
    st.stop()

if db.get_stats()["total_episodes"] < 2:
    st.info("Synthesis needs at least 2 analyzed episodes. Process more first.")
    st.stop()

# ── Filter pane ─────────────────────────────────────────────────────────
st.markdown("### 🎯 Step 1: Filter episodes")

f1, f2, f3 = st.columns([2, 1.5, 1.5])
with f1:
    text_filter = st.text_input(
        "Keyword (matches title / guest / summary)",
        placeholder="e.g., property, inflation, Brazil",
        key="synth_text",
    )
with f2:
    podcasts = ["All"] + db.get_distinct_podcasts()
    podcast_filter = st.selectbox("Podcast", podcasts)
with f3:
    regions = ["All", "Latin America", "EMEA", "Asia ex-China", "China",
               "Frontier Markets", "GCC/Middle East", "Eastern Europe"]
    region_filter = st.selectbox("Region", regions)

f4, f5, f6 = st.columns([1.5, 1.5, 2])
with f4:
    sentiments = ["All", "Bullish", "Bearish", "Neutral/Mixed"]
    sentiment_filter = st.selectbox("Sentiment", sentiments)
with f5:
    max_episodes = st.slider("Max episodes", 2, 15, value=8)
with f6:
    priority = st.selectbox(
        "Model priority",
        ["quality", "balanced", "cost", "speed"],
        help="Quality is recommended for synthesis since it's a higher-stakes task.",
    )

# Run filter
filters: Dict[str, Any] = {"limit": max_episodes}
if text_filter:
    filters["search"] = text_filter
if podcast_filter != "All":
    filters["podcast"] = podcast_filter
if region_filter != "All":
    filters["region"] = region_filter
if sentiment_filter != "All":
    filters["sentiment"] = sentiment_filter

candidates = db.list_episodes(**filters)
st.caption(f"**{len(candidates)}** episode(s) match these filters")

if candidates:
    with st.expander(f"Selected episodes ({len(candidates)})", expanded=False):
        for e in candidates:
            ts = (e.get("created_at") or "")[:10]
            st.markdown(
                f'<div class="ep-mini">'
                f'<strong>{e["episode_title"][:80]}</strong> '
                f'{sentiment_pill(e.get("sentiment", ""))} '
                f'<span style="color:#888;">'
                f'· {e["podcast_title"]} · {ts}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ── Question ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 💭 Step 2: Ask a synthesis question")

starter_questions = [
    "How has the consensus view on this topic evolved over time?",
    "Where do the guests agree and where do they disagree?",
    "What are the most contrarian takes vs the consensus?",
    "What risks have been most consistently flagged?",
    "What positioning recommendations emerge from these episodes?",
]
default_q = st.session_state.get("synth_question", "")
sug_cols = st.columns(len(starter_questions))
for i, sq in enumerate(starter_questions):
    with sug_cols[i]:
        if st.button(sq[:40] + "…" if len(sq) > 40 else sq,
                     key=f"sq_{i}", use_container_width=True):
            st.session_state["synth_question"] = sq
            st.rerun()

question = st.text_area(
    "Your question",
    value=st.session_state.get("synth_question", ""),
    placeholder="e.g., How has the China property crisis view evolved?",
    height=90,
    key="synth_question_input",
)

# Show what model would be used
model_preview = model_router.select_model(
    task="deep_summary",
    transcript_chars=sum(len(e.get("full_transcript") or "") for e in candidates),
    priority=priority,
)
if model_preview and len(candidates) >= 2 and question.strip():
    cost = model_router.estimate_cost(
        model_preview,
        sum(min(len(e.get("full_transcript") or ""), 3000) for e in candidates) + 5000,
        output_tokens=2000,
    )
    st.caption(f"🤖 Will use: **{model_preview.name}** (~${cost:.3f})")

# ── Run ─────────────────────────────────────────────────────────────────
st.markdown("---")
run = st.button(
    f"🔄 Synthesize across {len(candidates)} episode(s)",
    type="primary",
    disabled=(len(candidates) < 2 or not question.strip()),
    use_container_width=True,
)

if run:
    with st.spinner(f"Synthesizing {len(candidates)} episodes…"):
        text, model_used = model_router.synthesize_across_episodes(
            episodes=candidates,
            question=question.strip(),
            priority=priority,
        )

    st.markdown("### 📝 Synthesis")
    if model_used:
        st.caption(f"_via {model_used.name} ({model_used.provider})_")
    st.markdown(f'<div class="synth-output">', unsafe_allow_html=True)
    st.markdown(text)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"**Source episodes ({len(candidates)}):**")
    for i, e in enumerate(candidates, 1):
        ts = (e.get("created_at") or "")[:10]
        st.markdown(
            f"{i}. **{e['episode_title'][:90]}** — "
            f"{e['podcast_title']} · {ts} · "
            f"{e.get('sentiment', '—')}"
        )

    # Allow user to download
    st.download_button(
        label="📄 Download synthesis as Markdown",
        data=f"# Cross-Episode Synthesis\n\n**Question:** {question}\n\n"
             f"**Episodes synthesized:** {len(candidates)}\n\n"
             f"**Model:** {model_used.name if model_used else '?'}\n\n"
             f"---\n\n{text}\n\n---\n\n"
             f"## Source Episodes\n\n" + "\n".join(
                 f"{i}. {e['episode_title']} — {e['podcast_title']} ({(e.get('created_at') or '')[:10]})"
                 for i, e in enumerate(candidates, 1)
             ),
        file_name="synthesis.md",
        mime="text/markdown",
    )
