#!/usr/bin/env python3
"""
Auto-fetch — process new episodes from your watchlist.

Run via cron:
    0 6 * * * cd /path/to/podcastGPT && python scripts/auto_fetch.py

For each enabled feed in your watchlist:
  1. Fetch the latest episode
  2. Skip if it's already in the Library
  3. Search for an existing transcript (Listen Notes / web)
  4. Fall back to placeholder if no transcript (Whisper requires audio
     download + ffmpeg, which is heavy for a cron — only existing
     transcripts are processed automatically)
  5. Generate analysis via the smart router
  6. Save to Library
  7. If telegram_notify is on, push a digest to Telegram

Environment variables:
  OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY / DEEPSEEK_API_KEY
    — at least one needed for analysis
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    — optional, for digest delivery

Flags:
  --dry-run       Just show what would be processed; no DB writes
  --verbose       Detailed progress per feed
  --feed-id N     Only process a single watchlist entry
  --force         Re-process even if last_episode_processed matches
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from core import database as db
from core import models as model_router
from core.exports import deliver_to_telegram
from core.insights import extract_em_insights
from core.transcript import find_transcript


# ── Feed parsing (lightweight, no caching) ──────────────────────────────

def parse_feed(rss_url: str) -> Optional[Dict[str, Any]]:
    """Return a dict with podcast_title and the latest episode."""
    try:
        resp = requests.get(rss_url, headers={"User-Agent": "PodcastGPT/1.0"}, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return None
        ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
        podcast_title = channel.findtext("title", "Unknown")
        items = channel.findall("item")
        if not items:
            return None

        latest = items[0]  # RSS feeds have most-recent first by convention
        title = latest.findtext("title", "Untitled")
        link = latest.findtext("link", "")
        published = latest.findtext("pubDate", "")

        audio_url = ""
        enc = latest.find("enclosure")
        if enc is not None:
            audio_url = enc.get("url", "")

        return {
            "podcast_title": podcast_title,
            "episode_title": title,
            "episode_link": link,
            "audio_url": audio_url,
            "published": published,
        }
    except Exception as e:
        return {"_error": str(e)[:200]}


# ── Main pipeline ───────────────────────────────────────────────────────

def process_feed(
    feed: Dict[str, Any],
    dry_run: bool = False,
    verbose: bool = False,
    force: bool = False,
) -> Tuple[bool, str]:
    """
    Process the latest episode of a watchlist feed.
    Returns (success, message).
    """
    name = feed["name"]
    url = feed["rss_url"]

    parsed = parse_feed(url)
    if not parsed or "_error" in (parsed or {}):
        return False, f"Failed to parse {name}: {parsed.get('_error') if parsed else 'no data'}"

    podcast_title = parsed["podcast_title"]
    episode_title = parsed["episode_title"]

    # Skip if we've already processed this episode
    if not force and feed.get("last_episode_processed") == episode_title:
        return True, f"{name}: nothing new (already at '{episode_title[:60]}')"

    # Skip if it's already in the DB (e.g., processed manually)
    existing = db.get_episode_by_title(episode_title, podcast_title)
    if existing and not force:
        # Update watermark anyway so we don't keep checking
        if not dry_run:
            db.update_watchlist(
                feed["id"],
                last_checked_at=datetime.now().isoformat(),
                last_episode_processed=episode_title,
            )
        return True, f"{name}: already in library — '{episode_title[:60]}'"

    if verbose:
        print(f"  → New episode: {episode_title[:80]}")

    # 1. Find transcript (no Whisper fallback in cron — too heavy)
    if verbose:
        print(f"  → Searching for transcript…")
    transcript, source = find_transcript(
        podcast_name=podcast_title,
        episode_title=episode_title,
        episode_page_url=parsed.get("episode_link"),
    )
    if not transcript:
        return False, (
            f"{name}: no online transcript found for '{episode_title[:60]}'. "
            "Process via Streamlit UI to use Whisper."
        )

    if verbose:
        print(f"  → Transcript found via {source} ({len(transcript):,} chars)")

    # 2. Run smart router
    priority = feed.get("routing_priority") or "balanced"
    if dry_run:
        chosen = model_router.select_model(
            "summary", len(transcript), priority,
        )
        cost = model_router.estimate_cost(chosen, len(transcript)) if chosen else 0
        return True, (
            f"{name}: would process '{episode_title[:60]}' via "
            f"{chosen.name if chosen else 'no model'} (~${cost:.3f})"
        )

    if verbose:
        print(f"  → Running summary (priority={priority})…")
    result = model_router.generate_summary(
        transcript=transcript,
        task="summary",
        priority=priority,
    )
    if result.get("_is_fallback"):
        return False, f"{name}: analysis failed — {result.get('podcast_summary', '')[:120]}"

    # Stash transcript meta for downstream Q&A
    result["_transcript_source"] = source
    result["_full_transcript"] = transcript

    # 3. Save to library
    em_insights = extract_em_insights(result)
    db.save_episode(
        episode_title=episode_title,
        podcast_title=podcast_title,
        result=result,
        em_insights=em_insights,
        full_transcript=transcript,
    )

    # 4. Push digest to Telegram (if enabled and configured)
    if feed.get("telegram_notify"):
        try:
            deliver_to_telegram(
                episode_title=episode_title,
                result=result,
                em_insights=em_insights,
                podcast_title=podcast_title,
            )
        except Exception:
            pass  # Non-fatal

    # 5. Update watchlist watermark
    db.update_watchlist(
        feed["id"],
        last_checked_at=datetime.now().isoformat(),
        last_episode_processed=episode_title,
    )

    return True, (
        f"{name}: ✓ '{episode_title[:60]}' — "
        f"{result.get('_model_label', '?')} "
        f"(~${result.get('_estimated_cost', 0):.3f})"
    )


def main():
    parser = argparse.ArgumentParser(description="Auto-fetch new episodes from watchlist")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed without writing")
    parser.add_argument("--verbose", action="store_true", help="Detailed per-feed output")
    parser.add_argument("--feed-id", type=int, default=None,
                        help="Only process a single watchlist entry by id")
    parser.add_argument("--force", action="store_true",
                        help="Re-process even if last_episode_processed matches")
    args = parser.parse_args()

    avail = model_router.available_providers()
    if not avail and not args.dry_run:
        print("ERROR: No AI provider API keys set. "
              "Set OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY / "
              "DEEPSEEK_API_KEY in environment.")
        sys.exit(1)

    feeds = db.list_watchlist(enabled_only=True)
    if args.feed_id:
        feeds = [f for f in feeds if f["id"] == args.feed_id]
    if not feeds:
        print("No enabled watchlist entries.")
        sys.exit(0)

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"[{datetime.now().isoformat()}] auto_fetch ({mode}) — {len(feeds)} feed(s)")
    print(f"  Available providers: {sorted(avail) or '(none)'}")

    successes = failures = skipped = 0
    for feed in feeds:
        if args.verbose:
            print(f"\n→ {feed['name']} ({feed['rss_url']})")
        ok, msg = process_feed(
            feed,
            dry_run=args.dry_run,
            verbose=args.verbose,
            force=args.force,
        )
        print(f"  {'✓' if ok else '✗'} {msg}")
        if ok:
            if "nothing new" in msg or "already in library" in msg:
                skipped += 1
            else:
                successes += 1
        else:
            failures += 1

    print(f"\nDone. ✓ {successes}  ⏭ {skipped}  ✗ {failures}")


if __name__ == "__main__":
    main()
