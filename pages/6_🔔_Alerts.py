"""
Alerts — saved searches that trigger Telegram notifications.

When auto_fetch processes a new episode (or you manually process one),
each enabled alert is evaluated. If it matches, a Telegram alert fires.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from typing import Any, Dict

import streamlit as st

from core import database as db

st.set_page_config(page_title="Alerts — PodcastGPT", page_icon="🔔", layout="wide")

st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; }
    .alert-card {
        background: white;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid #f59e0b;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    .alert-card.disabled { opacity: 0.6; border-left-color: #999; }
    .alert-meta { color: #666; font-size: 0.85rem; margin-top: 0.3rem; }
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
    .pill-criteria { background: #fef3c7; color: #92400e; }
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
st.title("🔔 Alerts")
st.caption(
    "Saved searches that fire when a new episode matches. "
    "Triggers Telegram if `TELEGRAM_BOT_TOKEN` is set."
)

with st.expander("ℹ️ How alerts work", expanded=False):
    st.markdown("""
**Each alert can match on any combination of:**
- **Keyword** — substring search across title / summary / highlights
- **Region** — must include this region (LatAm, EMEA, China, etc.)
- **Theme** — must include this investment theme
- **Country** — must include this country
- **Sentiment** — must match exactly (Bullish / Bearish / Neutral/Mixed)

Multiple criteria are AND-ed together. Leave fields blank to skip them.

**When alerts fire:**
- Auto-fetch script (`scripts/auto_fetch.py`) checks every newly-processed episode
- If `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set, you get a 🔔 message
- Each alert tracks its trigger count and last-triggered episode
""")

# ── Add new alert ───────────────────────────────────────────────────────
st.markdown("### ➕ Add a new alert")

with st.form("add_alert", clear_on_submit=True):
    name = st.text_input(
        "Alert name",
        placeholder="e.g., Brazil rate cut commentary",
    )

    a1, a2 = st.columns(2)
    with a1:
        keyword = st.text_input(
            "Keyword (optional)",
            placeholder="e.g., rate cut, default, restructuring",
        )
        region = st.selectbox(
            "Region (optional)",
            ["", "Latin America", "EMEA", "Asia ex-China", "China",
             "Frontier Markets", "GCC/Middle East", "Eastern Europe"],
        )
        country = st.text_input(
            "Country (optional)",
            placeholder="e.g., Brazil, Turkey, India",
        )
    with a2:
        theme = st.selectbox(
            "Theme (optional)",
            ["", "Monetary Policy", "Credit Conditions", "Growth Outlook",
             "Political Risk", "External Flows", "Currency Dynamics",
             "Commodity Impact", "ESG/Climate"],
        )
        sentiment = st.selectbox(
            "Sentiment (optional)",
            ["", "Bullish", "Bearish", "Neutral/Mixed"],
        )
        enabled = st.checkbox("Enabled", value=True)

    submitted = st.form_submit_button("Save alert", type="primary", use_container_width=True)
    if submitted:
        if not name.strip():
            st.error("Alert needs a name.")
        elif not any([keyword, region, theme, country, sentiment]):
            st.error("Set at least one match criterion.")
        else:
            db.add_alert(
                name=name.strip(),
                keyword=keyword.strip(),
                region=region or "",
                theme=theme or "",
                country=country.strip(),
                sentiment=sentiment or "",
                enabled=enabled,
            )
            st.success(f"Saved: {name}")
            st.rerun()

st.markdown("---")

# ── Existing alerts ─────────────────────────────────────────────────────
alerts = db.list_alerts()
st.markdown(f"### 📋 Saved alerts ({len(alerts)})")

if not alerts:
    st.info("No alerts yet. Create one above.")
else:
    for alert in alerts:
        disabled_cls = "" if alert["enabled"] else " disabled"
        on_pill = (
            '<span class="pill pill-on">ON</span>'
            if alert["enabled"]
            else '<span class="pill pill-off">OFF</span>'
        )

        criteria = []
        if alert.get("keyword"):
            criteria.append(f'<span class="pill pill-criteria">📝 {alert["keyword"]}</span>')
        if alert.get("region"):
            criteria.append(f'<span class="pill pill-criteria">🌍 {alert["region"]}</span>')
        if alert.get("country"):
            criteria.append(f'<span class="pill pill-criteria">🏳️ {alert["country"]}</span>')
        if alert.get("theme"):
            criteria.append(f'<span class="pill pill-criteria">🎯 {alert["theme"]}</span>')
        if alert.get("sentiment"):
            criteria.append(f'<span class="pill pill-criteria">📊 {alert["sentiment"]}</span>')

        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(
                f'<div class="alert-card{disabled_cls}">'
                f'<div style="font-weight: 600;">{alert["name"]}</div>'
                f'<div style="margin-top: 0.4rem;">{on_pill}{"".join(criteria)}</div>'
                f'<div class="alert-meta">'
                f'🔔 Triggered <strong>{alert["trigger_count"]}</strong> time(s)'
                f' · last: {fmt_time(alert.get("last_triggered_at", ""))}'
                f' · episode: {(alert.get("last_triggered_episode") or "—")[:60]}'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with c2:
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                action = "Disable" if alert["enabled"] else "Enable"
                if st.button(action, key=f"toggle_{alert['id']}", use_container_width=True):
                    db.update_alert(alert["id"], enabled=not alert["enabled"])
                    st.rerun()
            with sub_c2:
                if st.button("Delete", key=f"del_{alert['id']}", use_container_width=True):
                    db.delete_alert(alert["id"])
                    st.rerun()

# ── Quick-add presets ──────────────────────────────────────────────────
st.markdown("---")
with st.expander("⚡ Quick-add common alert templates", expanded=False):
    PRESETS = [
        ("Bearish China property", {"keyword": "property", "country": "China", "sentiment": "Bearish"}),
        ("Brazil rate-cut signals", {"keyword": "rate", "country": "Brazil", "theme": "Monetary Policy"}),
        ("Turkey/lira distress", {"keyword": "lira", "country": "Turkey", "sentiment": "Bearish"}),
        ("LatAm bullish flow", {"region": "Latin America", "sentiment": "Bullish"}),
        ("EM credit defaults", {"keyword": "default", "theme": "Credit Conditions"}),
        ("India structural bull", {"country": "India", "sentiment": "Bullish"}),
    ]
    cols = st.columns(2)
    for i, (label, kwargs) in enumerate(PRESETS):
        with cols[i % 2]:
            if st.button(f"+ {label}", key=f"preset_{i}", use_container_width=True):
                db.add_alert(name=label, **kwargs)
                st.rerun()
