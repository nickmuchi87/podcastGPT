"""
Dashboard — at-a-glance overview of analyzed podcast corpus.

KPIs, sentiment trend, regional/theme breakdowns, and model usage
across all stored episodes. The first page users land on.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from core import database as db

st.set_page_config(page_title="Dashboard — PodcastGPT", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; }
    .kpi {
        background: white;
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        text-align: center;
        height: 100%;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .kpi-label { color: #666; font-size: 0.9rem; margin: 0.25rem 0 0 0; }
    .kpi-sub { color: #999; font-size: 0.75rem; margin-top: 0.25rem; }
    .episode-mini {
        background: white;
        padding: 0.6rem 0.8rem;
        margin-bottom: 0.5rem;
        border-radius: 8px;
        border-left: 3px solid #667eea;
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


def kpi(value: str, label: str, sub: str = ""):
    st.markdown(
        f'<div class="kpi"><p class="kpi-value">{value}</p>'
        f'<p class="kpi-label">{label}</p>'
        f'<p class="kpi-sub">{sub}</p></div>',
        unsafe_allow_html=True,
    )


def sentiment_pill(sentiment: str) -> str:
    s = (sentiment or "").lower()
    cls = "pill-neutral"
    if "bull" in s:
        cls = "pill-bull"
    elif "bear" in s:
        cls = "pill-bear"
    return f'<span class="pill {cls}">{sentiment or "—"}</span>'


# ── Header ──────────────────────────────────────────────────────────────
st.title("📊 Dashboard")
st.caption("Bird's-eye view of your analyzed podcast corpus.")

stats = db.get_stats()
total = stats["total_episodes"]

if total == 0:
    st.info(
        "No episodes analyzed yet. Process your first podcast on the main page "
        "to populate this dashboard."
    )
    st.stop()

# ── KPI row ─────────────────────────────────────────────────────────────
counts = db.get_aggregate_counts()
total_cost = db.get_total_estimated_cost()
sentiment_breakdown = stats["sentiment_breakdown"]

# Hours saved estimate: assume 45 min per episode
hours_saved = round(total * 0.75, 1)

# Most recent episode date
recent_eps = db.list_episodes(limit=1)
latest = recent_eps[0]["created_at"] if recent_eps else ""
try:
    latest_dt = datetime.fromisoformat(latest)
    days_ago = (datetime.now() - latest_dt).days
    latest_label = (
        "today" if days_ago == 0
        else "yesterday" if days_ago == 1
        else f"{days_ago}d ago"
    )
except (ValueError, TypeError):
    latest_label = "—"

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    kpi(str(total), "Episodes Analyzed", f"latest: {latest_label}")
with c2:
    kpi(f"{hours_saved}", "Hours Saved", "vs. listening live")
with c3:
    kpi(
        str(sentiment_breakdown.get("Bullish", 0)),
        "Bullish",
        f"{sentiment_breakdown.get('Bullish', 0)/total:.0%} of total",
    )
with c4:
    kpi(
        str(sentiment_breakdown.get("Bearish", 0)),
        "Bearish",
        f"{sentiment_breakdown.get('Bearish', 0)/total:.0%} of total",
    )
with c5:
    kpi(f"${total_cost:.2f}", "Total LLM Cost", "estimated")

st.markdown("---")

# ── Sentiment trend ─────────────────────────────────────────────────────
all_eps = db.list_episodes(limit=500)
trend_rows: List[Dict[str, Any]] = []
for e in reversed(all_eps):  # chronological
    try:
        ts = datetime.fromisoformat(e["created_at"])
    except (ValueError, TypeError):
        continue
    trend_rows.append({
        "date": ts.date(),
        "net_sentiment": e["bullish_score"] - e["bearish_score"],
        "bullish": e["bullish_score"],
        "bearish": e["bearish_score"],
    })

if trend_rows:
    df = pd.DataFrame(trend_rows)
    daily = df.groupby("date").agg({
        "net_sentiment": "mean",
        "bullish": "sum",
        "bearish": "sum",
    }).reset_index()

    chart_col, info_col = st.columns([3, 1])
    with chart_col:
        st.markdown("### 📈 Sentiment Trend")
        st.caption("Average net sentiment per day (bullish − bearish signals)")
        st.line_chart(daily.set_index("date")["net_sentiment"], height=260)
    with info_col:
        latest_net = trend_rows[-1]["net_sentiment"]
        avg_net = df["net_sentiment"].mean()
        st.markdown("### Mood")
        if latest_net > 1:
            st.success(f"📈 Positive\n\nLatest: +{latest_net}")
        elif latest_net < -1:
            st.error(f"📉 Negative\n\nLatest: {latest_net}")
        else:
            st.warning(f"➖ Neutral\n\nLatest: {latest_net:+.0f}")
        st.caption(f"Corpus average: {avg_net:+.1f}")

st.markdown("---")

# ── Regions / Themes / Countries ────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### 🌍 Top Regions Discussed")
    region_data = sorted(counts["regions"].items(), key=lambda x: -x[1])[:10]
    if region_data:
        df_r = pd.DataFrame(region_data, columns=["Region", "Episodes"])
        st.bar_chart(df_r.set_index("Region")["Episodes"], height=260)
    else:
        st.caption("No regional data yet.")

    st.markdown("### 🎯 Top Themes")
    theme_data = sorted(counts["themes"].items(), key=lambda x: -x[1])[:10]
    if theme_data:
        df_t = pd.DataFrame(theme_data, columns=["Theme", "Episodes"])
        st.bar_chart(df_t.set_index("Theme")["Episodes"], height=260)

with col_right:
    st.markdown("### 🏳️ Top Countries Mentioned")
    country_data = sorted(counts["countries"].items(), key=lambda x: -x[1])[:12]
    if country_data:
        df_c = pd.DataFrame(country_data, columns=["Country", "Episodes"])
        st.bar_chart(df_c.set_index("Country")["Episodes"], height=260)
    else:
        st.caption("No country data yet.")

    st.markdown("### 💼 Asset Class Coverage")
    ac_data = sorted(counts["asset_classes"].items(), key=lambda x: -x[1])[:8]
    if ac_data:
        df_ac = pd.DataFrame(ac_data, columns=["Asset Class", "Episodes"])
        st.bar_chart(df_ac.set_index("Asset Class")["Episodes"], height=260)

st.markdown("---")

# ── Model usage + recent episodes ────────────────────────────────────────
col_m, col_r = st.columns([1, 2])

with col_m:
    st.markdown("### 🤖 Model Usage")
    usage = db.get_model_usage()
    if usage:
        for model, n in list(usage.items())[:8]:
            pct = n / total
            st.markdown(f"**{model}** &nbsp;`{n}`")
            st.progress(pct)
    else:
        st.caption("No model usage data yet.")

with col_r:
    st.markdown("### 🆕 Most Recent Analyses")
    for e in db.list_episodes(limit=8):
        try:
            ts = datetime.fromisoformat(e["created_at"]).strftime("%b %d")
        except (ValueError, TypeError):
            ts = ""
        regions = ", ".join(e.get("regions", [])[:2]) or "—"
        st.markdown(
            f'<div class="episode-mini">'
            f'<div style="font-weight: 600; font-size: 0.95rem;">{e["episode_title"][:80]}</div>'
            f'<div style="color: #888; font-size: 0.8rem; margin-top: 0.2rem;">'
            f'🎙️ {e["podcast_title"]} · 📅 {ts} · 🌍 {regions} '
            f'</div>'
            f'<div style="margin-top: 0.3rem;">{sentiment_pill(e.get("sentiment", ""))}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")
st.caption(
    "💡 Tip: Use the **Library** page to filter and search, "
    "**Compare** to diff two episodes, or **Q&A** to chat with any transcript."
)
