"""
Transcript discovery — search for existing transcripts before
falling back to Whisper.

Pure functions, no Streamlit dependency. Used by both the main
app (with optional progress callback) and the auto-fetch cron.

Search order:
  1. Listen Notes (provided URL or auto-search)
  2. Episode's own webpage (from RSS link)
  3. Web search (Google) for "[podcast] [episode] transcript"
"""

import json
import re
from typing import Optional

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ── Listen Notes ────────────────────────────────────────────────────────

def extract_listennotes_transcript(url: str) -> Optional[str]:
    """Try to extract transcript from a Listen Notes episode page."""
    if "listennotes.com" not in url.lower():
        return None
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        resp.raise_for_status()
        html = resp.text

        # JSON-LD
        for m in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            html, re.DOTALL,
        ):
            try:
                data = json.loads(m)
                if isinstance(data, dict):
                    if "transcript" in data:
                        return data["transcript"]
                    media = data.get("associatedMedia")
                    if isinstance(media, dict) and "transcript" in media:
                        return media["transcript"]
            except json.JSONDecodeError:
                continue

        # div / section / inline JSON
        for pattern in (
            r'<div[^>]*class="[^"]*transcript[^"]*"[^>]*>(.*?)</div>',
            r'<section[^>]*id="transcript"[^>]*>(.*?)</section>',
            r'"transcript"\s*:\s*"([^"]+)"',
        ):
            for m in re.findall(pattern, html, re.DOTALL | re.IGNORECASE):
                clean = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m)).strip()
                if len(clean) > 500:
                    return clean
    except Exception:
        pass
    return None


def search_listennotes_for_episode(podcast_name: str, episode_title: str) -> Optional[str]:
    """Find a Listen Notes episode page URL via search."""
    try:
        query = re.sub(r"[^\w\s]", " ", f"{podcast_name} {episode_title}")
        query = " ".join(query.split()[:10])
        url = f"https://www.listennotes.com/search/?q={requests.utils.quote(query)}&type=episode"
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        resp.raise_for_status()
        matches = re.findall(r'href="(/podcasts/[^"]+/[^"]+/)"', resp.text)
        if matches:
            return f"https://www.listennotes.com{matches[0]}"
    except Exception:
        pass
    return None


# ── Generic webpage scraping ────────────────────────────────────────────

def extract_transcript_from_webpage(url: str) -> Optional[str]:
    """Scrape any podcast webpage for transcript content."""
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        resp.raise_for_status()
        html = resp.text

        container_patterns = [
            r'<div[^>]*class="[^"]*transcript[^"]*"[^>]*>(.*?)</div>',
            r'<section[^>]*class="[^"]*transcript[^"]*"[^>]*>(.*?)</section>',
            r'<div[^>]*id="transcript[^"]*"[^>]*>(.*?)</div>',
            r'<section[^>]*id="transcript[^"]*"[^>]*>(.*?)</section>',
            r'<div[^>]*class="[^"]*show-notes[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*episode-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*post-content[^"]*"[^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
        ]
        for pat in container_patterns:
            for m in re.findall(pat, html, re.DOTALL | re.IGNORECASE):
                clean = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m)).strip()
                if len(clean) > 1000:
                    return clean

        # JSON-LD fallback
        for m in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
        ):
            try:
                data = json.loads(m)
                if isinstance(data, dict):
                    if "transcript" in data:
                        return data["transcript"]
                    if "articleBody" in data and len(data["articleBody"]) > 1000:
                        return data["articleBody"]
                    if "text" in data and len(data["text"]) > 1000:
                        return data["text"]
            except (json.JSONDecodeError, TypeError):
                continue

        # "Transcript" heading followed by content
        head = re.findall(
            r"<h[1-4][^>]*>[^<]*transcript[^<]*</h[1-4]>\s*"
            r"(.*?)(?=<h[1-4]|<footer|</article|</main|$)",
            html, re.DOTALL | re.IGNORECASE,
        )
        for m in head:
            clean = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m)).strip()
            if len(clean) > 1000:
                return clean
    except Exception:
        pass
    return None


# ── Web search ──────────────────────────────────────────────────────────

def search_web_for_transcript(podcast_name: str, episode_title: str) -> Optional[str]:
    """Google for transcripts and scrape top candidates."""
    clean_pod = re.sub(r"[^\w\s]", "", podcast_name).strip()
    clean_ep = " ".join(re.sub(r"[^\w\s]", "", episode_title).strip().split()[:8])
    headers = {"User-Agent": UA}

    for query in (
        f"{clean_pod} {clean_ep} transcript",
        f"{clean_pod} {clean_ep} full transcript text",
    ):
        try:
            resp = requests.get(
                f"https://www.google.com/search?q={requests.utils.quote(query)}",
                headers=headers, timeout=10,
            )
            if resp.status_code != 200:
                continue
            html = resp.text

            urls = re.findall(r'<a[^>]+href="/url\?q=(https?://[^"&]+)', html)
            if not urls:
                urls = re.findall(r'href="(https?://(?:www\.)?[^"]+)"', html)

            skip = ("google.com", "youtube.com", "facebook.com", "twitter.com",
                    "instagram.com", "tiktok.com", "reddit.com", "wikipedia.org",
                    "apple.com/podcasts", "spotify.com")
            cleaned = [
                u for u in urls
                if not any(d in u.lower() for d in skip)
            ]
            # Prioritize transcript-like URLs
            cleaned.sort(key=lambda u: 0 if any(
                kw in u.lower() for kw in ("transcript", "show-notes", "episode")
            ) else 1)

            for u in cleaned[:3]:
                t = extract_transcript_from_webpage(u)
                if t:
                    return t
        except Exception:
            continue
    return None


# ── High-level entry point ──────────────────────────────────────────────

def find_transcript(
    podcast_name: str,
    episode_title: str,
    episode_page_url: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Run the full transcript-search pipeline. Returns (transcript, source).
    Source is one of: "Listen Notes", "episode webpage", "web search", or None.
    """
    if episode_page_url and "listennotes.com" in episode_page_url.lower():
        t = extract_listennotes_transcript(episode_page_url)
        if t:
            return t, "Listen Notes"

    if episode_page_url and "listennotes.com" not in episode_page_url.lower():
        t = extract_transcript_from_webpage(episode_page_url)
        if t:
            return t, "episode webpage"

    if podcast_name and episode_title:
        ln_url = search_listennotes_for_episode(podcast_name, episode_title)
        if ln_url:
            t = extract_listennotes_transcript(ln_url)
            if t:
                return t, "Listen Notes"

        t = search_web_for_transcript(podcast_name, episode_title)
        if t:
            return t, "web search"

    return None, None
