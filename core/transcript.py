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
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import parse_qs, urlparse

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


# ── YouTube transcript ─────────────────────────────────────────────────

def _extract_youtube_id(url: str) -> Optional[str]:
    """Extract video ID from various YouTube URL formats."""
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if "youtube.com" in host:
        qs = parse_qs(parsed.query)
        return qs.get("v", [None])[0]
    if "youtu.be" in host:
        return parsed.path.lstrip("/").split("/")[0] or None
    return None


def extract_youtube_transcript(url: str) -> Optional[str]:
    """
    Fetch auto-generated or manual captions from a YouTube video.
    Uses the timedtext XML API (no extra dependency needed).
    """
    video_id = _extract_youtube_id(url)
    if not video_id:
        return None

    try:
        watch_resp = requests.get(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
            timeout=15,
        )
        watch_resp.raise_for_status()
        html = watch_resp.text

        # Find caption track URLs in the player response
        caption_urls = re.findall(
            r'"captionTracks":\[(\{.*?\})\]',
            html,
        )
        if not caption_urls:
            # Try alternative pattern
            caption_urls = re.findall(
                r'"captions".*?"captionTracks":\[(.*?)\]',
                html, re.DOTALL,
            )

        if not caption_urls:
            return None

        # Parse the caption tracks JSON
        try:
            tracks_raw = "[" + caption_urls[0] + "]"
            # Fix unquoted keys for JSON parsing
            tracks_raw = re.sub(r'(?<=\{|,)(\w+)(?=:)', r'"\1"', tracks_raw)
            tracks = json.loads(tracks_raw)
        except (json.JSONDecodeError, IndexError):
            # Fallback: extract baseUrl directly with regex
            base_urls = re.findall(
                r'"baseUrl"\s*:\s*"(https://www\.youtube\.com/api/timedtext[^"]+)"',
                html,
            )
            if not base_urls:
                return None
            # Prefer English tracks
            caption_url = base_urls[0]
            for bu in base_urls:
                if "lang=en" in bu or "en" in bu:
                    caption_url = bu
                    break
            caption_url = caption_url.replace("\\u0026", "&")
            return _fetch_timedtext(caption_url)

        # Pick best track: prefer English manual, then English auto, then any
        best_url = None
        for track in tracks:
            base_url = track.get("baseUrl", "").replace("\\u0026", "&")
            lang = track.get("languageCode", "")
            kind = track.get("kind", "")
            if lang == "en" and kind != "asr":
                best_url = base_url
                break
            if lang == "en":
                best_url = base_url
            elif not best_url and base_url:
                best_url = base_url

        if not best_url:
            return None
        return _fetch_timedtext(best_url)

    except Exception:
        return None


def _fetch_timedtext(url: str) -> Optional[str]:
    """Download a timedtext XML and concatenate the text segments."""
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        segments = []
        for text_el in root.iter("text"):
            t = (text_el.text or "").strip()
            if t:
                # Unescape HTML entities
                t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                t = t.replace("&#39;", "'").replace("&quot;", '"')
                segments.append(t)
        if not segments:
            return None
        return " ".join(segments)
    except Exception:
        return None


def search_youtube_for_episode(podcast_name: str, episode_title: str) -> Optional[str]:
    """Search YouTube for a podcast episode and return the best video URL."""
    clean_pod = re.sub(r"[^\w\s]", "", podcast_name).strip()
    clean_ep = " ".join(re.sub(r"[^\w\s]", "", episode_title).strip().split()[:8])
    query = f"{clean_pod} {clean_ep} full episode"

    try:
        resp = requests.get(
            f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}",
            headers={"User-Agent": UA},
            timeout=15,
        )
        if resp.status_code != 200:
            return None

        video_ids = re.findall(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', resp.text)
        seen = []
        for vid in video_ids:
            if vid not in seen:
                seen.append(vid)
            if len(seen) >= 3:
                break

        for vid in seen:
            url = f"https://www.youtube.com/watch?v={vid}"
            transcript = extract_youtube_transcript(url)
            if transcript and len(transcript) > 500:
                return url
    except Exception:
        pass
    return None


# ── High-level entry point ──────────────────────────────────────────────

def find_transcript(
    podcast_name: str,
    episode_title: str,
    episode_page_url: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Run the full transcript-search pipeline. Returns (transcript, source).
    Source is one of: "Listen Notes", "YouTube", "episode webpage",
    "web search", or None.
    """
    # 1. Direct YouTube URL
    if episode_page_url and _extract_youtube_id(episode_page_url):
        t = extract_youtube_transcript(episode_page_url)
        if t and len(t) > 500:
            return t, "YouTube"

    # 2. Listen Notes URL
    if episode_page_url and "listennotes.com" in episode_page_url.lower():
        t = extract_listennotes_transcript(episode_page_url)
        if t:
            return t, "Listen Notes"

    # 3. Episode webpage scrape
    if episode_page_url and "listennotes.com" not in episode_page_url.lower():
        t = extract_transcript_from_webpage(episode_page_url)
        if t:
            return t, "episode webpage"

    if podcast_name and episode_title:
        # 4. Listen Notes auto-search
        ln_url = search_listennotes_for_episode(podcast_name, episode_title)
        if ln_url:
            t = extract_listennotes_transcript(ln_url)
            if t:
                return t, "Listen Notes"

        # 5. YouTube search
        yt_url = search_youtube_for_episode(podcast_name, episode_title)
        if yt_url:
            t = extract_youtube_transcript(yt_url)
            if t and len(t) > 500:
                return t, "YouTube"

        # 6. General web search
        t = search_web_for_transcript(podcast_name, episode_title)
        if t:
            return t, "web search"

    return None, None
