"""
Q&A — chat with the full transcript of an analyzed episode.

Uses the smart model router to pick the best LLM for Q&A based on
transcript length and user-selected priority (cost/quality/balanced).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, List

import streamlit as st

from core import database as db
from core import models as model_router

st.set_page_config(page_title="Q&A — PodcastGPT", page_icon="💬", layout="wide")


# ── UI ──────────────────────────────────────────────────────────────────
st.title("💬 Ask the Podcast")
st.caption(
    "Pick an analyzed episode and ask questions grounded in its full transcript. "
    "Routing balances cost and quality automatically."
)

# Show available providers / current routing priority
avail = model_router.available_providers()
if not avail:
    st.error(
        "No AI provider keys configured. Add at least one of "
        "`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, or `DEEPSEEK_API_KEY`."
    )
    st.stop()

priority_options = ["balanced", "quality", "cost", "speed"]
current = st.session_state.get("routing_priority", "balanced")
prio_col, info_col = st.columns([2, 3])
with prio_col:
    st.session_state["routing_priority"] = st.radio(
        "Routing priority",
        priority_options,
        index=priority_options.index(current),
        horizontal=True,
        key="qa_priority",
    )
with info_col:
    st.caption(f"Active providers: **{', '.join(sorted(avail))}**")

episodes = db.list_episodes(limit=200)
episodes_with_transcripts = [e for e in episodes if e.get("full_transcript")]

if not episodes_with_transcripts:
    st.info(
        "No episodes with stored transcripts yet. "
        "Process new episodes — their transcripts are saved automatically."
    )
    st.stop()

ep_options = {
    f"{e['episode_title'][:70]}{'…' if len(e['episode_title'])>70 else ''} — {e['podcast_title']}": e
    for e in episodes_with_transcripts
}
selected_label = st.selectbox("Choose an episode", list(ep_options.keys()))
episode = ep_options[selected_label]
transcript = episode.get("full_transcript", "")

# Show what model will be picked
chosen = model_router.select_model(
    task="qa",
    transcript_chars=len(transcript),
    priority=st.session_state["routing_priority"],
)

# Episode meta
m1, m2, m3 = st.columns([3, 2, 1])
with m1:
    st.markdown(
        f"**Guest:** {episode.get('guest','Unknown')} · "
        f"**Sentiment:** {episode.get('sentiment','—')}"
    )
with m2:
    if chosen:
        cost = model_router.estimate_cost(chosen, len(transcript), output_tokens=600)
        st.caption(f"🤖 Will use: **{chosen.name}** (~${cost:.3f}/question)")
with m3:
    if st.button("🔄 New chat", use_container_width=True):
        st.session_state[f"qa_history_{episode['id']}"] = []
        st.rerun()

st.caption(f"Transcript length: {len(transcript):,} chars")

# Suggested starter questions
st.markdown("**Suggested:**")
suggestions = [
    "What's the guest's main view on EM rates?",
    "Which countries were discussed most?",
    "What are the top 3 risks they flagged?",
    "Did the guest disagree with consensus on anything?",
]
sug_cols = st.columns(len(suggestions))
suggested_q = None
for i, s in enumerate(suggestions):
    with sug_cols[i]:
        if st.button(s, key=f"sug_{i}", use_container_width=True):
            suggested_q = s

st.markdown("---")

# Chat history (per episode)
hist_key = f"qa_history_{episode['id']}"
if hist_key not in st.session_state:
    st.session_state[hist_key] = []

for turn in st.session_state[hist_key]:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        if turn["role"] == "assistant" and turn.get("model"):
            st.caption(f"_via {turn['model']}_")

# Input
user_q = st.chat_input("Ask anything about this episode…")
question = suggested_q or user_q

if question:
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state[hist_key].append({"role": "user", "content": question})

    with st.chat_message("assistant"):
        full_answer = ""
        model_used = None
        placeholder = st.empty()
        try:
            for chunk, model in model_router.stream_chat_with_transcript(
                transcript=transcript,
                question=question,
                history=st.session_state[hist_key][:-1],
                priority=st.session_state["routing_priority"],
            ):
                model_used = model
                full_answer += chunk
                placeholder.markdown(full_answer + "▌")
            placeholder.markdown(full_answer)
        except Exception:
            # Fallback to non-streaming if streaming fails
            full_answer, model_used = model_router.chat_with_transcript(
                transcript=transcript,
                question=question,
                history=st.session_state[hist_key][:-1],
                priority=st.session_state["routing_priority"],
            )
            placeholder.markdown(full_answer)
        if model_used:
            st.caption(f"_via {model_used.name}_")

    st.session_state[hist_key].append({
        "role": "assistant",
        "content": full_answer,
        "model": model_used.name if model_used else None,
    })
