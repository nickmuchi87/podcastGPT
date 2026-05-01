"""
Q&A — chat with the full transcript of an analyzed episode.

Pick an episode from the library and ask questions; answers are
grounded in the stored transcript using the configured LLM.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, List, Optional

import streamlit as st

from core import database as db

st.set_page_config(page_title="Q&A — PodcastGPT", page_icon="💬", layout="wide")


# ── LLM clients (lazy) ──────────────────────────────────────────────────
def _ask_with_anthropic(transcript: str, question: str, history: List[Dict[str, str]]) -> str:
    try:
        import anthropic
    except ImportError:
        return "Anthropic SDK not installed. Add `anthropic` to requirements.txt."

    api_key = os.environ.get("ANTHROPIC_API_KEY") or st.session_state.get("anthropic_api_key")
    if not api_key:
        return "ANTHROPIC_API_KEY not set."

    client = anthropic.Anthropic(api_key=api_key)
    system = (
        "You are an EM (Emerging Markets) Portfolio Manager research assistant. "
        "Answer questions strictly using the provided podcast transcript. "
        "If the transcript doesn't cover a question, say so. Be concise but specific. "
        "Quote short passages from the transcript when relevant."
    )
    messages = [
        {"role": "user", "content": f"<transcript>\n{transcript[:120000]}\n</transcript>"},
        {"role": "assistant", "content": "Got it — ask away and I'll answer based on this transcript."},
    ]
    for turn in history[-6:]:  # keep recent history
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": question})

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        return resp.content[0].text if resp.content else "(empty response)"
    except Exception as e:
        return f"Anthropic error: {e}"


def _ask_with_openai(transcript: str, question: str, history: List[Dict[str, str]]) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        return "OpenAI SDK not installed."

    api_key = os.environ.get("OPENAI_API_KEY") or st.session_state.get("openai_api_key")
    if not api_key:
        return "OPENAI_API_KEY not set."

    client = OpenAI(api_key=api_key)
    system = (
        "You are an EM Portfolio Manager research assistant. "
        "Answer strictly from the provided transcript. If unclear, say so."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Podcast transcript:\n\n{transcript[:60000]}"},
    ]
    for turn in history[-6:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": question})

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=800,
            temperature=0.2,
        )
        return resp.choices[0].message.content or "(empty response)"
    except Exception as e:
        return f"OpenAI error: {e}"


def ask(transcript: str, question: str, history: List[Dict[str, str]]) -> str:
    """Route to the first available LLM."""
    if os.environ.get("ANTHROPIC_API_KEY") or st.session_state.get("anthropic_api_key"):
        return _ask_with_anthropic(transcript, question, history)
    return _ask_with_openai(transcript, question, history)


# ── UI ──────────────────────────────────────────────────────────────────
st.title("💬 Ask the Podcast")
st.caption("Pick an analyzed episode and ask questions grounded in its full transcript.")

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

# Episode meta
meta_col1, meta_col2 = st.columns([3, 1])
with meta_col1:
    st.markdown(f"**Guest:** {episode.get('guest','Unknown')} · "
                f"**Sentiment:** {episode.get('sentiment','—')} · "
                f"**Transcript:** {len(episode.get('full_transcript','')):,} chars")
with meta_col2:
    if st.button("🔄 New conversation", use_container_width=True):
        st.session_state[f"qa_history_{episode['id']}"] = []
        st.rerun()

# Suggested questions
st.markdown("**Suggested:**")
suggestions = [
    "What's the guest's main view on EM rates?",
    "Which countries were discussed most?",
    "What are the top 3 risks they flagged?",
    "Did the guest disagree with consensus on anything?",
]
sug_cols = st.columns(len(suggestions))
suggested_q: Optional[str] = None
for i, s in enumerate(suggestions):
    with sug_cols[i]:
        if st.button(s, key=f"sug_{i}", use_container_width=True):
            suggested_q = s

st.markdown("---")

# Chat history
hist_key = f"qa_history_{episode['id']}"
if hist_key not in st.session_state:
    st.session_state[hist_key] = []

# Render past turns
for turn in st.session_state[hist_key]:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

# Input
user_q = st.chat_input("Ask anything about this episode…")
question = suggested_q or user_q

if question:
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state[hist_key].append({"role": "user", "content": question})

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            answer = ask(
                transcript=episode.get("full_transcript", ""),
                question=question,
                history=st.session_state[hist_key][:-1],  # exclude the just-added user msg
            )
        st.markdown(answer)
    st.session_state[hist_key].append({"role": "assistant", "content": answer})
