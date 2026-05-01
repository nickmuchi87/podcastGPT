"""
SQLite-backed persistence for PodcastGPT.

Stores full episode analyses including transcripts, summaries, and
extracted insights. Replaces the brittle JSON-file approach with a
queryable database that supports search, filter, and trend analysis.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "content", "podcastgpt.db")
LEGACY_HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "content", "podcast_history.json")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_title TEXT NOT NULL,
                podcast_title TEXT NOT NULL,
                guest TEXT,
                guest_title TEXT,
                guest_org TEXT,
                summary TEXT,
                highlights TEXT,
                details TEXT,
                full_transcript TEXT,
                transcript_source TEXT,
                model_used TEXT,
                sentiment TEXT,
                regions TEXT,         -- JSON array
                themes TEXT,          -- JSON array
                countries TEXT,       -- JSON array
                asset_classes TEXT,   -- JSON array
                bullish_score INTEGER DEFAULT 0,
                bearish_score INTEGER DEFAULT 0,
                full_result TEXT,     -- JSON of full result dict
                created_at TEXT NOT NULL,
                UNIQUE(episode_title, podcast_title)
            );

            CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_episodes_sentiment ON episodes(sentiment);
            CREATE INDEX IF NOT EXISTS idx_episodes_podcast ON episodes(podcast_title);

            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                rss_url TEXT NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1,
                telegram_notify INTEGER NOT NULL DEFAULT 1,
                routing_priority TEXT DEFAULT 'balanced',
                last_checked_at TEXT,
                last_episode_processed TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                keyword TEXT,           -- free-text match against title/summary/highlights
                region TEXT,            -- specific EM region to match
                theme TEXT,             -- specific theme to match
                country TEXT,           -- specific country to match
                sentiment TEXT,         -- match Bullish/Bearish/Neutral if set
                enabled INTEGER NOT NULL DEFAULT 1,
                trigger_count INTEGER NOT NULL DEFAULT 0,
                last_triggered_at TEXT,
                last_triggered_episode TEXT,
                created_at TEXT NOT NULL
            );
        """)
        conn.commit()


def save_episode(
    episode_title: str,
    podcast_title: str,
    result: Dict[str, Any],
    em_insights: Optional[Dict[str, Any]] = None,
    full_transcript: Optional[str] = None,
) -> int:
    """Persist an analyzed episode. Returns the row id (overwrites if dup)."""
    init_db()
    em = em_insights or {}
    now = datetime.now().isoformat()

    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO episodes (
                episode_title, podcast_title, guest, guest_title, guest_org,
                summary, highlights, details, full_transcript, transcript_source,
                model_used, sentiment, regions, themes, countries, asset_classes,
                bullish_score, bearish_score, full_result, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(episode_title, podcast_title) DO UPDATE SET
                guest=excluded.guest,
                guest_title=excluded.guest_title,
                guest_org=excluded.guest_org,
                summary=excluded.summary,
                highlights=excluded.highlights,
                details=excluded.details,
                full_transcript=excluded.full_transcript,
                transcript_source=excluded.transcript_source,
                model_used=excluded.model_used,
                sentiment=excluded.sentiment,
                regions=excluded.regions,
                themes=excluded.themes,
                countries=excluded.countries,
                asset_classes=excluded.asset_classes,
                bullish_score=excluded.bullish_score,
                bearish_score=excluded.bearish_score,
                full_result=excluded.full_result,
                created_at=excluded.created_at
        """, (
            episode_title,
            podcast_title,
            result.get("podcast_guest", "Unknown"),
            result.get("podcast_guest_title", ""),
            result.get("podcast_guest_org", ""),
            result.get("podcast_summary", ""),
            result.get("podcast_highlights", ""),
            result.get("podcast_details", ""),
            full_transcript or result.get("_full_transcript", ""),
            result.get("_transcript_source", ""),
            result.get("_model_used", ""),
            em.get("sentiment", ""),
            json.dumps(em.get("regions", [])),
            json.dumps(em.get("themes", [])),
            json.dumps(em.get("countries", [])),
            json.dumps(em.get("asset_classes", [])),
            em.get("bullish_score", 0),
            em.get("bearish_score", 0),
            json.dumps(result),
            now,
        ))
        conn.commit()
        return cur.lastrowid or 0


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    for key in ("regions", "themes", "countries", "asset_classes"):
        try:
            d[key] = json.loads(d.get(key) or "[]")
        except (json.JSONDecodeError, TypeError):
            d[key] = []
    try:
        d["full_result"] = json.loads(d.get("full_result") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["full_result"] = {}
    return d


def list_episodes(
    search: str = "",
    sentiment: Optional[str] = None,
    podcast: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Return episodes ordered by most recent, with optional filters."""
    init_db()
    sql = "SELECT * FROM episodes WHERE 1=1"
    params: List[Any] = []

    if search:
        sql += " AND (episode_title LIKE ? OR podcast_title LIKE ? OR guest LIKE ? OR summary LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like, like])
    if sentiment:
        sql += " AND sentiment = ?"
        params.append(sentiment)
    if podcast:
        sql += " AND podcast_title = ?"
        params.append(podcast)
    if region:
        sql += " AND regions LIKE ?"
        params.append(f"%{region}%")

    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]


def get_episode(episode_id: int) -> Optional[Dict[str, Any]]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
        return _row_to_dict(row) if row else None


def get_episode_by_title(episode_title: str, podcast_title: str) -> Optional[Dict[str, Any]]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM episodes WHERE episode_title = ? AND podcast_title = ?",
            (episode_title, podcast_title),
        ).fetchone()
        return _row_to_dict(row) if row else None


def delete_episode(episode_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
        conn.commit()


def get_distinct_podcasts() -> List[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT podcast_title FROM episodes ORDER BY podcast_title"
        ).fetchall()
        return [r["podcast_title"] for r in rows if r["podcast_title"]]


def get_stats() -> Dict[str, Any]:
    """Aggregate stats for dashboards."""
    init_db()
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM episodes").fetchone()["n"]
        sentiment_counts = conn.execute("""
            SELECT sentiment, COUNT(*) AS n FROM episodes
            WHERE sentiment != '' GROUP BY sentiment
        """).fetchall()
        sentiments = {r["sentiment"]: r["n"] for r in sentiment_counts}

        recent_rows = conn.execute("""
            SELECT created_at, sentiment, bullish_score, bearish_score
            FROM episodes ORDER BY created_at DESC LIMIT 30
        """).fetchall()
        timeline = [dict(r) for r in recent_rows]

    return {
        "total_episodes": total,
        "sentiment_breakdown": sentiments,
        "recent_timeline": timeline,
    }


def get_aggregate_counts() -> Dict[str, Dict[str, int]]:
    """Count occurrences of each region/theme/country/asset_class across all episodes."""
    init_db()
    counts = {"regions": {}, "themes": {}, "countries": {}, "asset_classes": {}}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT regions, themes, countries, asset_classes FROM episodes"
        ).fetchall()
    for r in rows:
        for key in counts:
            try:
                items = json.loads(r[key] or "[]")
            except (json.JSONDecodeError, TypeError):
                items = []
            for item in items:
                counts[key][item] = counts[key].get(item, 0) + 1
    return counts


def get_model_usage() -> Dict[str, int]:
    """Count episodes processed per model."""
    init_db()
    with _connect() as conn:
        rows = conn.execute("""
            SELECT model_used, COUNT(*) AS n FROM episodes
            WHERE model_used != '' GROUP BY model_used ORDER BY n DESC
        """).fetchall()
        return {r["model_used"]: r["n"] for r in rows}


def get_total_estimated_cost() -> float:
    """Sum of _estimated_cost across all stored episodes (parses full_result JSON)."""
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT full_result FROM episodes").fetchall()
    total = 0.0
    for r in rows:
        try:
            d = json.loads(r["full_result"] or "{}")
            v = d.get("_estimated_cost")
            if isinstance(v, (int, float)):
                total += float(v)
        except (json.JSONDecodeError, TypeError):
            continue
    return total


# ── Watchlist CRUD ──────────────────────────────────────────────────────

def add_watchlist(
    name: str,
    rss_url: str,
    enabled: bool = True,
    telegram_notify: bool = True,
    routing_priority: str = "balanced",
) -> int:
    init_db()
    now = datetime.now().isoformat()
    with _connect() as conn:
        try:
            cur = conn.execute("""
                INSERT INTO watchlist (name, rss_url, enabled, telegram_notify,
                                       routing_priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, rss_url, int(enabled), int(telegram_notify),
                  routing_priority, now))
            conn.commit()
            return cur.lastrowid or 0
        except sqlite3.IntegrityError:
            # URL already exists
            return -1


def list_watchlist(enabled_only: bool = False) -> List[Dict[str, Any]]:
    init_db()
    sql = "SELECT * FROM watchlist"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY name"
    with _connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def update_watchlist(
    watchlist_id: int,
    enabled: Optional[bool] = None,
    telegram_notify: Optional[bool] = None,
    routing_priority: Optional[str] = None,
    last_checked_at: Optional[str] = None,
    last_episode_processed: Optional[str] = None,
) -> None:
    init_db()
    fields, params = [], []
    if enabled is not None:
        fields.append("enabled = ?")
        params.append(int(enabled))
    if telegram_notify is not None:
        fields.append("telegram_notify = ?")
        params.append(int(telegram_notify))
    if routing_priority is not None:
        fields.append("routing_priority = ?")
        params.append(routing_priority)
    if last_checked_at is not None:
        fields.append("last_checked_at = ?")
        params.append(last_checked_at)
    if last_episode_processed is not None:
        fields.append("last_episode_processed = ?")
        params.append(last_episode_processed)
    if not fields:
        return
    params.append(watchlist_id)
    with _connect() as conn:
        conn.execute(f"UPDATE watchlist SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()


def delete_watchlist(watchlist_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM watchlist WHERE id = ?", (watchlist_id,))
        conn.commit()


# ── Alerts CRUD ─────────────────────────────────────────────────────────

def add_alert(
    name: str,
    keyword: str = "",
    region: str = "",
    theme: str = "",
    country: str = "",
    sentiment: str = "",
    enabled: bool = True,
) -> int:
    init_db()
    now = datetime.now().isoformat()
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO alerts (name, keyword, region, theme, country, sentiment,
                                enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, keyword, region, theme, country, sentiment, int(enabled), now))
        conn.commit()
        return cur.lastrowid or 0


def list_alerts(enabled_only: bool = False) -> List[Dict[str, Any]]:
    init_db()
    sql = "SELECT * FROM alerts"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY name"
    with _connect() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def update_alert(
    alert_id: int,
    enabled: Optional[bool] = None,
    trigger_count: Optional[int] = None,
    last_triggered_at: Optional[str] = None,
    last_triggered_episode: Optional[str] = None,
) -> None:
    init_db()
    fields, params = [], []
    if enabled is not None:
        fields.append("enabled = ?")
        params.append(int(enabled))
    if trigger_count is not None:
        fields.append("trigger_count = ?")
        params.append(trigger_count)
    if last_triggered_at is not None:
        fields.append("last_triggered_at = ?")
        params.append(last_triggered_at)
    if last_triggered_episode is not None:
        fields.append("last_triggered_episode = ?")
        params.append(last_triggered_episode)
    if not fields:
        return
    params.append(alert_id)
    with _connect() as conn:
        conn.execute(f"UPDATE alerts SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()


def delete_alert(alert_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        conn.commit()


def evaluate_alerts_for_episode(
    episode_title: str,
    podcast_title: str,
    result: Dict[str, Any],
    em_insights: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Return list of alerts that match this episode. Caller is responsible
    for sending notifications and bumping trigger counters.
    """
    matched: List[Dict[str, Any]] = []
    summary = (result.get("podcast_summary") or "").lower()
    highlights = (result.get("podcast_highlights") or "").lower()
    title_lower = episode_title.lower()
    full_text = f"{title_lower} {summary} {highlights}"

    regions = [r.lower() for r in em_insights.get("regions", [])]
    themes = [t.lower() for t in em_insights.get("themes", [])]
    countries = [c.lower() for c in em_insights.get("countries", [])]
    sentiment = (em_insights.get("sentiment") or "").lower()

    for alert in list_alerts(enabled_only=True):
        if alert.get("keyword"):
            if alert["keyword"].lower() not in full_text:
                continue
        if alert.get("region"):
            if alert["region"].lower() not in regions:
                continue
        if alert.get("theme"):
            if alert["theme"].lower() not in themes:
                continue
        if alert.get("country"):
            if alert["country"].lower() not in countries:
                continue
        if alert.get("sentiment"):
            if alert["sentiment"].lower() != sentiment:
                continue
        matched.append(alert)

    return matched


def migrate_legacy_history() -> int:
    """One-time migration of the old JSON history file into SQLite."""
    if not os.path.exists(LEGACY_HISTORY_FILE):
        return 0
    try:
        with open(LEGACY_HISTORY_FILE) as f:
            entries = json.load(f)
    except (json.JSONDecodeError, OSError):
        return 0

    init_db()
    migrated = 0
    for entry in entries:
        ep = entry.get("episode_title", "")
        pod = entry.get("podcast_title", "Unknown")
        if not ep:
            continue
        # Skip if already in DB
        if get_episode_by_title(ep, pod):
            continue
        result = entry.get("full_result", {})
        # Try to reconstruct insights from result if not stored
        save_episode(ep, pod, result, em_insights=None)
        migrated += 1
    return migrated
