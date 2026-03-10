"""
PodcastGPT - AI-Powered Podcast Transcription & Summarization
A seamless app for Emerging Markets Portfolio Managers to get actionable insights from podcasts.
"""

import streamlit as st
import json
import os
import re
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
import time
import tempfile
from openai import OpenAI, APIError, RateLimitError, APIConnectionError
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except (ImportError, OSError):
    PYDUB_AVAILABLE = False
    AudioSegment = None

# ============================================================================
# Configuration & Constants
# ============================================================================

APP_TITLE = "PodcastGPT"
APP_ICON = "🎙️"
APP_DESCRIPTION = "AI-Powered Podcast Analysis for EM Portfolio Managers"

# Sample podcasts - EM and Macro focused (using reliable RSS feeds)
SAMPLE_PODCASTS = {
    # Primary EM-focused podcasts
    "Odd Lots (Bloomberg)": "https://www.omnycontent.com/d/playlist/e73c998e-6e60-432f-8610-ae210140c5b1/8a94442e-5a74-4fa2-8b8d-ae27003a8d6b/982f5071-765c-403d-969d-ae27003a8d83/podcast.rss",
    "EM Podcast (Tellimer)": "https://anchor.fm/s/4ad0dd20/podcast/rss",
    "Moody's EM Decoded": "https://feeds.megaphone.fm/moodystalksemergingmarketsdecoded",
    "Clauses & Controversies": "https://feeds.soundcloud.com/users/soundcloud:users:863571279/sounds.rss",
    "Geopolitics (Frank McKenna)": "https://feeds.simplecast.com/geopolitics_with_frank_mckenna",
    # Additional macro/finance podcasts
    "All-In Podcast": "https://feeds.megaphone.fm/all-in-with-chamath-jason-sacks-friedberg",
    "Macro Voices": "https://feeds.megaphone.fm/macrovoices",
    "Invest Like the Best": "https://feeds.megaphone.fm/investlikethebest",
}

# EM Regions for analysis
EM_REGIONS = [
    "Latin America", "EMEA", "Asia ex-China", "China",
    "Frontier Markets", "GCC/Middle East", "Eastern Europe"
]

# Asset classes for EM analysis
EM_ASSET_CLASSES = [
    "Hard Currency Sovereigns", "Local Currency Sovereigns",
    "EM Corporates (IG)", "EM Corporates (HY)",
    "EM Equities", "EM FX"
]

# Topic categories for structured summaries
TOPIC_CATEGORIES = {
    "Market Outlook": ["outlook", "forecast", "expect", "predict", "2024", "2025", "next year", "going forward"],
    "Monetary Policy": ["rate", "fed", "central bank", "inflation", "interest", "hiking", "cutting", "pause", "pivot"],
    "Growth & Economy": ["gdp", "growth", "recession", "slowdown", "expansion", "economic", "economy"],
    "Credit & Fixed Income": ["credit", "bond", "spread", "yield", "duration", "default", "high yield", "investment grade"],
    "Currencies & FX": ["currency", "dollar", "fx", "depreciation", "appreciation", "exchange rate", "carry"],
    "Equities": ["stock", "equity", "valuation", "earnings", "p/e", "multiple", "index"],
    "Geopolitics & Policy": ["election", "political", "government", "regulation", "sanction", "trade war", "tariff"],
    "China Focus": ["china", "chinese", "beijing", "xi", "property", "evergrande"],
    "Commodities": ["oil", "commodity", "metal", "gold", "copper", "energy"],
    "Risk Factors": ["risk", "concern", "worry", "downside", "volatility", "uncertainty"],
}

# ============================================================================
# Page Configuration
# ============================================================================

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# Custom CSS for Modern UI
# ============================================================================

st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Header styling */
    .app-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        color: white;
    }

    .app-header h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 700;
    }

    .app-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 1.1rem;
    }

    /* Card styling */
    .podcast-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid #667eea;
    }

    /* Summary section styling */
    .summary-section {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }

    .summary-section h3 {
        color: #667eea;
        margin-bottom: 1rem;
        font-size: 1.2rem;
    }

    /* Highlight items */
    .highlight-item {
        background: #f0f4ff;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        border-left: 3px solid #667eea;
    }

    /* Guest card */
    .guest-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
    }

    .guest-card h4 {
        color: #333;
        margin-bottom: 0.5rem;
    }

    .guest-card p {
        color: #666;
        font-size: 0.9rem;
    }

    /* Status indicators */
    .status-processing {
        background: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }

    .status-success {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }

    .status-error {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 8px;
    }

    /* Episode selector */
    .episode-item {
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        background: white;
        border: 1px solid #e0e0e0;
        transition: all 0.2s ease;
    }

    .episode-item:hover {
        border-color: #667eea;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.15);
    }

    /* Sidebar styling */
    .css-1d391kg {
        background: #f8f9fa;
    }

    /* Button styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 0.5rem 1rem;
    }

    /* Metric cards */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }

    .metric-card h2 {
        color: #667eea;
        font-size: 2rem;
        margin: 0;
    }

    .metric-card p {
        color: #666;
        margin: 0.5rem 0 0 0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Session State Initialization
# ============================================================================

def init_session_state():
    """Initialize session state variables."""
    if 'processed_podcasts' not in st.session_state:
        st.session_state.processed_podcasts = {}

    if 'history' not in st.session_state:
        st.session_state.history = []

    if 'current_episodes' not in st.session_state:
        st.session_state.current_episodes = {}

    if 'selected_episode' not in st.session_state:
        st.session_state.selected_episode = None

    if 'processing' not in st.session_state:
        st.session_state.processing = False

    if 'last_result' not in st.session_state:
        st.session_state.last_result = None

    if 'episode_listennotes_url' not in st.session_state:
        st.session_state.episode_listennotes_url = None

    if 'processing_start_time' not in st.session_state:
        st.session_state.processing_start_time = None


# ============================================================================
# Utility Functions
# ============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def parse_podcast_feed(feed_url: str) -> Dict[str, Any]:
    """Parse a podcast RSS feed and extract episode information using requests + XML."""
    try:
        # Fetch the RSS feed
        headers = {
            'User-Agent': 'PodcastGPT/1.0 (Podcast Aggregator)'
        }
        response = requests.get(feed_url, headers=headers, timeout=15)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)

        # Handle different RSS namespaces
        namespaces = {
            'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
            'media': 'http://search.yahoo.com/mrss/',
            'content': 'http://purl.org/rss/1.0/modules/content/'
        }

        # Get channel info
        channel = root.find('channel')
        if channel is None:
            return {"error": "Invalid RSS feed format."}

        podcast_title = channel.findtext('title', 'Unknown Podcast')

        # Get podcast image
        podcast_image = ''
        image_elem = channel.find('image')
        if image_elem is not None:
            podcast_image = image_elem.findtext('url', '')
        if not podcast_image:
            itunes_image = channel.find('itunes:image', namespaces)
            if itunes_image is not None:
                podcast_image = itunes_image.get('href', '')

        # Get episodes (items)
        items = channel.findall('item')[:10]  # Get latest 10 episodes

        if not items:
            return {"error": "No episodes found in this feed."}

        episodes = {}
        for item in items:
            title = item.findtext('title', 'Untitled Episode')

            # Get audio URL from enclosure
            audio_url = ''
            enclosure = item.find('enclosure')
            if enclosure is not None:
                enc_type = enclosure.get('type', '')
                if enc_type.startswith('audio/') or enc_type == '':
                    audio_url = enclosure.get('url', '')

            # Get episode image
            episode_image = podcast_image
            itunes_img = item.find('itunes:image', namespaces)
            if itunes_img is not None:
                episode_image = itunes_img.get('href', episode_image)

            # Get description
            description = item.findtext('description', '')
            if not description:
                itunes_summary = item.find('itunes:summary', namespaces)
                description = (itunes_summary.text if itunes_summary is not None else '') or ''
            # Clean HTML tags and truncate
            description = re.sub(r'<[^>]+>', '', description)[:200]

            # Get published date
            published = item.findtext('pubDate', '')

            # Get episode page URL (useful for transcript extraction)
            episode_link = item.findtext('link', '')

            if audio_url:  # Only add if we have an audio URL
                episodes[title] = {
                    'audio_url': audio_url,
                    'image': episode_image,
                    'description': description,
                    'published': published,
                    'podcast_title': podcast_title,
                    'link': episode_link
                }

        if not episodes:
            return {"error": "No episodes with audio found in this feed."}

        return {
            "success": True,
            "podcast_title": podcast_title,
            "podcast_image": podcast_image,
            "episodes": episodes
        }

    except requests.exceptions.ConnectionError as e:
        return {"error": "Connection failed. The feed URL may be blocked or the server is unreachable. Try a different podcast or check your network."}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. The server took too long to respond. Please try again."}
    except requests.RequestException as e:
        error_msg = str(e)
        if "NameResolutionError" in error_msg or "Name or service not known" in error_msg:
            return {"error": "Could not resolve the feed URL. This feed may be unavailable in your network. Try a different podcast."}
        return {"error": f"Failed to fetch feed: {error_msg[:100]}"}
    except ET.ParseError as e:
        return {"error": "The URL returned invalid XML. Make sure it's a valid RSS feed URL."}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)[:100]}"}


def extract_rss_from_listennotes(url: str) -> Dict[str, Any]:
    """
    Extract RSS feed URL from a Listen Notes podcast page.
    Supports URLs like: https://www.listennotes.com/podcasts/podcast-name-id/
    """
    try:
        # Check if it's a Listen Notes URL
        if 'listennotes.com' not in url.lower():
            return {"error": "Not a Listen Notes URL", "is_listennotes": False}

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        html_content = response.text

        # Try to find RSS feed URL in the page
        # Listen Notes typically has the RSS in a specific format
        rss_patterns = [
            r'href="(https?://[^"]*(?:feed|rss)[^"]*)"',
            r'"rss_url":\s*"([^"]+)"',
            r'<link[^>]*type="application/rss\+xml"[^>]*href="([^"]+)"',
            r'data-rss="([^"]+)"',
        ]

        for pattern in rss_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                if match and 'listennotes' not in match.lower():
                    return {
                        "success": True,
                        "rss_url": match,
                        "is_listennotes": True
                    }

        # If we can't find RSS, return helpful message
        return {
            "error": "Could not extract RSS feed. Try clicking the RSS button on Listen Notes and copying the direct RSS URL.",
            "is_listennotes": True
        }

    except requests.RequestException as e:
        return {"error": f"Failed to fetch Listen Notes page: {str(e)[:100]}", "is_listennotes": True}
    except Exception as e:
        return {"error": f"Error processing URL: {str(e)[:100]}", "is_listennotes": True}


@st.cache_data(ttl=3600, show_spinner=False)
def detect_and_process_url(url: str) -> Dict[str, Any]:
    """
    Intelligently detect URL type and process accordingly.
    Handles: RSS feeds, Listen Notes URLs, Apple Podcasts, Spotify (with guidance)
    """
    url = url.strip()

    if not url:
        return {"error": "Please enter a URL"}

    # Check for Listen Notes
    if 'listennotes.com' in url.lower():
        result = extract_rss_from_listennotes(url)
        if result.get('success'):
            return parse_podcast_feed(result['rss_url'])
        return result

    # Check for Apple Podcasts - provide guidance
    if 'podcasts.apple.com' in url.lower():
        return {
            "error": "Apple Podcasts URLs don't contain RSS feeds directly. Please use Listen Notes to find the RSS feed for this podcast.",
            "suggestion": "Go to listennotes.com, search for the podcast, and copy the RSS feed URL."
        }

    # Check for Spotify - provide guidance
    if 'spotify.com' in url.lower():
        return {
            "error": "Spotify doesn't provide public RSS feeds. Please use Listen Notes to find the RSS feed for this podcast.",
            "suggestion": "Go to listennotes.com, search for the podcast, and copy the RSS feed URL."
        }

    # Assume it's an RSS feed URL
    return parse_podcast_feed(url)


def parse_summary_into_topics(result: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Parse the podcast summary and details into topic-based bullet points.
    Returns a dictionary with topic categories as keys and bullet points as values.
    """
    summary = result.get('podcast_summary', '')
    details = result.get('podcast_details', '')
    highlights = result.get('podcast_highlights', '')

    # Combine all text for analysis
    full_text = f"{summary} {details}"

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', full_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    # Categorize sentences into topics
    categorized = {}
    used_sentences = set()

    for topic, keywords in TOPIC_CATEGORIES.items():
        topic_sentences = []
        for i, sentence in enumerate(sentences):
            if i in used_sentences:
                continue
            sentence_lower = sentence.lower()
            if any(kw in sentence_lower for kw in keywords):
                # Clean up the sentence
                clean_sentence = sentence.strip()
                if clean_sentence and len(clean_sentence) > 30:
                    topic_sentences.append(clean_sentence)
                    used_sentences.add(i)

        if topic_sentences:
            # Limit to top 4 most relevant points per topic
            categorized[topic] = topic_sentences[:4]

    # Add highlights as "Key Takeaways" if not empty
    if highlights:
        highlight_list = [h.strip().lstrip('•-* ') for h in highlights.split('\n') if h.strip()]
        if highlight_list:
            categorized["Key Takeaways"] = highlight_list[:6]

    # If we have uncategorized important sentences, add them to "Other Insights"
    other_sentences = [sentences[i] for i in range(len(sentences))
                       if i not in used_sentences and len(sentences[i]) > 50][:4]
    if other_sentences:
        categorized["Other Insights"] = other_sentences

    return categorized


def format_topics_as_markdown(topics: Dict[str, List[str]]) -> str:
    """Format topic-based summary as markdown."""
    if not topics:
        return "No structured topics extracted."

    md_parts = []
    for topic, points in topics.items():
        md_parts.append(f"### {topic}")
        for point in points:
            # Truncate very long points
            if len(point) > 300:
                point = point[:297] + "..."
            md_parts.append(f"- {point}")
        md_parts.append("")  # Empty line between sections

    return "\n".join(md_parts)


def get_openai_client() -> Optional[OpenAI]:
    """Get OpenAI client if API key is configured."""
    api_key = os.environ.get('OPENAI_API_KEY') or st.session_state.get('openai_api_key')
    if api_key:
        return OpenAI(api_key=api_key)
    return None


def extract_listennotes_transcript(url: str) -> Optional[str]:
    """
    Try to extract transcript from Listen Notes episode page.
    Only ~1% of episodes have transcripts, so this often returns None.
    """
    if 'listennotes.com' not in url.lower():
        return None

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text

        # Look for transcript in various possible locations
        # Listen Notes embeds transcript in JSON-LD or specific div elements

        # Method 1: Check for transcript in JSON-LD schema
        json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
        json_ld_matches = re.findall(json_ld_pattern, html, re.DOTALL)

        for match in json_ld_matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict):
                    # Check for transcript field
                    if 'transcript' in data:
                        return data['transcript']
                    # Check in associatedMedia
                    if 'associatedMedia' in data:
                        media = data['associatedMedia']
                        if isinstance(media, dict) and 'transcript' in media:
                            return media['transcript']
            except json.JSONDecodeError:
                continue

        # Method 2: Look for transcript div/section
        transcript_patterns = [
            r'<div[^>]*class="[^"]*transcript[^"]*"[^>]*>(.*?)</div>',
            r'<section[^>]*id="transcript"[^>]*>(.*?)</section>',
            r'"transcript"\s*:\s*"([^"]+)"',
        ]

        for pattern in transcript_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                # Clean HTML tags
                clean_text = re.sub(r'<[^>]+>', ' ', match)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                if len(clean_text) > 500:  # Likely a real transcript
                    return clean_text

        return None

    except Exception as e:
        return None


def search_listennotes_for_episode(podcast_name: str, episode_title: str) -> Optional[str]:
    """
    Search Listen Notes for an episode and return the episode page URL.
    Returns None if not found.
    """
    try:
        # Clean up search query
        query = f"{podcast_name} {episode_title}"
        # Remove special characters that might break search
        query = re.sub(r'[^\w\s]', ' ', query)
        query = ' '.join(query.split()[:10])  # Limit to first 10 words

        search_url = f"https://www.listennotes.com/search/?q={requests.utils.quote(query)}&type=episode"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text

        # Look for episode links in search results
        # Listen Notes episode URLs look like: /podcasts/podcast-name/episode-title-XXXXX/
        episode_pattern = r'href="(/podcasts/[^"]+/[^"]+/)"'
        matches = re.findall(episode_pattern, html)

        if matches:
            # Return the first match (most relevant)
            episode_path = matches[0]
            return f"https://www.listennotes.com{episode_path}"

        return None

    except Exception as e:
        return None


def extract_transcript_from_webpage(url: str) -> Optional[str]:
    """
    Scrape a webpage (episode page, show notes, blog post) for transcript content.
    Works with podcast websites that publish transcripts alongside episodes.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        html = response.text

        # Method 1: Look for structured transcript containers
        transcript_container_patterns = [
            # Common transcript div/section patterns
            r'<div[^>]*class="[^"]*transcript[^"]*"[^>]*>(.*?)</div>',
            r'<section[^>]*class="[^"]*transcript[^"]*"[^>]*>(.*?)</section>',
            r'<div[^>]*id="transcript[^"]*"[^>]*>(.*?)</div>',
            r'<section[^>]*id="transcript[^"]*"[^>]*>(.*?)</section>',
            # Show notes / episode content that often contains transcripts
            r'<div[^>]*class="[^"]*show-notes[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*episode-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*post-content[^"]*"[^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
        ]

        for pattern in transcript_container_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                clean_text = re.sub(r'<[^>]+>', ' ', match)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                # A real transcript is typically > 1000 chars
                if len(clean_text) > 1000:
                    return clean_text

        # Method 2: Check JSON-LD structured data for transcript
        json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
        json_ld_matches = re.findall(json_ld_pattern, html, re.DOTALL)
        for match in json_ld_matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict):
                    if 'transcript' in data:
                        return data['transcript']
                    if 'articleBody' in data and len(data['articleBody']) > 1000:
                        return data['articleBody']
                    if 'text' in data and len(data['text']) > 1000:
                        return data['text']
            except (json.JSONDecodeError, TypeError):
                continue

        # Method 3: Look for a "transcript" heading followed by content
        # Many podcasts put transcript under an <h2>Transcript</h2> or similar
        transcript_heading_pattern = r'<h[1-4][^>]*>[^<]*transcript[^<]*</h[1-4]>\s*(.*?)(?=<h[1-4]|<footer|</article|</main|$)'
        heading_matches = re.findall(transcript_heading_pattern, html, re.DOTALL | re.IGNORECASE)
        for match in heading_matches:
            clean_text = re.sub(r'<[^>]+>', ' ', match)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            if len(clean_text) > 1000:
                return clean_text

        return None

    except Exception:
        return None


def search_web_for_transcript(podcast_name: str, episode_title: str) -> Optional[str]:
    """
    Search the web for an existing transcript of the podcast episode.
    Tries common transcript aggregator sites and general search.
    """
    # Clean up search terms
    clean_podcast = re.sub(r'[^\w\s]', '', podcast_name).strip()
    clean_episode = re.sub(r'[^\w\s]', '', episode_title).strip()
    # Use first 8 words of episode title to keep query focused
    clean_episode_short = ' '.join(clean_episode.split()[:8])

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # Strategy 1: Search common transcript/podcast sites via Google
    search_queries = [
        f"{clean_podcast} {clean_episode_short} transcript",
        f"{clean_podcast} {clean_episode_short} full transcript text",
    ]

    for query in search_queries:
        try:
            search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
            response = requests.get(search_url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue

            html = response.text

            # Extract URLs from search results
            url_pattern = r'<a[^>]+href="/url\?q=(https?://[^"&]+)'
            result_urls = re.findall(url_pattern, html)

            # Also try direct href patterns
            if not result_urls:
                url_pattern2 = r'href="(https?://(?:www\.)?[^"]+)"'
                result_urls = re.findall(url_pattern2, html)

            # Filter to likely transcript pages, skip Google/search engine URLs
            skip_domains = ['google.com', 'youtube.com', 'facebook.com', 'twitter.com',
                           'instagram.com', 'tiktok.com', 'reddit.com', 'wikipedia.org',
                           'apple.com/podcasts', 'spotify.com']

            transcript_urls = []
            for url in result_urls:
                url_lower = url.lower()
                if any(domain in url_lower for domain in skip_domains):
                    continue
                # Prioritize URLs that look like transcript pages
                if any(kw in url_lower for kw in ['transcript', 'show-notes', 'episode', 'podcast']):
                    transcript_urls.insert(0, url)
                else:
                    transcript_urls.append(url)

            # Try the top 3 most promising URLs
            for url in transcript_urls[:3]:
                try:
                    transcript = extract_transcript_from_webpage(url)
                    if transcript:
                        return transcript
                except Exception:
                    continue

        except Exception:
            continue

    return None


def extract_transcript_from_episode_page(episode_url: str) -> Optional[str]:
    """
    Try to extract transcript from a podcast episode page.
    Handles Listen Notes, podcast websites, and general webpages.
    Returns transcript text if found, None otherwise.
    """
    if not episode_url:
        return None

    # Try Listen Notes specifically
    if 'listennotes.com' in episode_url.lower():
        transcript = extract_listennotes_transcript(episode_url)
        if transcript:
            return transcript

    # Try scraping the episode's own webpage for transcript
    transcript = extract_transcript_from_webpage(episode_url)
    if transcript:
        return transcript

    return None


def download_audio(audio_url: str, max_retries: int = 2) -> Optional[str]:
    """Download audio file to a temporary location with retry support."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            headers = {'User-Agent': 'PodcastGPT/1.0'}
            timeout = 120 + (attempt * 60)  # Extend timeout on retries
            response = requests.get(audio_url, headers=headers, stream=True, timeout=timeout)
            response.raise_for_status()

            # Determine file type from content-type or URL
            content_type = response.headers.get('content-type', '')
            if 'audio/mp4' in content_type or 'm4a' in audio_url:
                suffix = '.m4a'
            elif 'audio/wav' in content_type:
                suffix = '.wav'
            elif 'audio/ogg' in content_type:
                suffix = '.ogg'
            else:
                suffix = '.mp3'

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    tmp_file.write(chunk)
                    downloaded += len(chunk)
                return tmp_file.name

        except requests.exceptions.Timeout:
            last_error = "Download timed out - the audio file may be very large."
            if attempt < max_retries:
                st.warning(f"Download timed out, retrying with longer timeout (attempt {attempt + 2}/{max_retries + 1})...")
                time.sleep(2 * (attempt + 1))
        except requests.exceptions.ConnectionError:
            last_error = "Connection failed - check your network connection."
            if attempt < max_retries:
                st.warning(f"Connection failed, retrying (attempt {attempt + 2}/{max_retries + 1})...")
                time.sleep(2 * (attempt + 1))
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 'unknown'
            if status == 404:
                st.error("Audio file not found (404). The episode may have been removed.")
            elif status == 403:
                st.error("Access denied (403). This podcast may restrict automated downloads.")
            else:
                st.error(f"Server error ({status}). Try again later.")
            return None
        except Exception as e:
            last_error = str(e)[:150]
            break

    st.error(f"Failed to download audio after {max_retries + 1} attempts: {last_error}")
    return None


def split_audio_into_chunks(audio_path: str, chunk_duration_ms: int = 600000) -> List[str]:
    """
    Split audio file into chunks for Whisper API (25MB limit).
    Default chunk is 10 minutes (600000ms) which typically stays under 25MB.
    """
    if not PYDUB_AVAILABLE:
        # Without pydub/ffmpeg, send file as-is and let Whisper handle it
        return [audio_path] if os.path.exists(audio_path) else []
    chunk_paths = []
    try:
        # Load audio file
        audio = AudioSegment.from_file(audio_path)
        total_duration = len(audio)

        # If audio is short enough, return as-is
        if total_duration <= chunk_duration_ms:
            return [audio_path]

        # Split into chunks
        num_chunks = (total_duration // chunk_duration_ms) + 1
        st.info(f"Audio is {total_duration // 60000} minutes - splitting into {num_chunks} chunks...")

        for i in range(0, total_duration, chunk_duration_ms):
            chunk = audio[i:i + chunk_duration_ms]

            # Export chunk to temp file
            chunk_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3').name
            chunk.export(chunk_path, format='mp3', bitrate='64k')
            chunk_paths.append(chunk_path)

        # Clean up original file
        try:
            os.unlink(audio_path)
        except:
            pass

        return chunk_paths

    except Exception as e:
        st.error(f"Failed to split audio: {str(e)[:100]}")
        # Return original file if splitting fails
        return [audio_path] if os.path.exists(audio_path) else []


def transcribe_audio(client: OpenAI, audio_path: str) -> Optional[str]:
    """Transcribe audio using OpenAI Whisper with chunking support."""
    chunk_paths = []
    try:
        # Split audio into chunks if needed
        chunk_paths = split_audio_into_chunks(audio_path)

        if not chunk_paths:
            st.error("No audio chunks to transcribe")
            return None

        # Transcribe each chunk
        transcripts = []
        for i, chunk_path in enumerate(chunk_paths):
            if len(chunk_paths) > 1:
                st.info(f"Transcribing chunk {i + 1}/{len(chunk_paths)}...")

            with open(chunk_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            transcripts.append(transcript)

        # Combine all transcripts
        return " ".join(transcripts)

    except RateLimitError:
        st.error("OpenAI rate limit reached. Please wait a minute and try again, or check your API usage limits.")
        return None
    except APIConnectionError:
        st.error("Could not connect to OpenAI API. Check your network connection.")
        return None
    except APIError as e:
        st.error(f"OpenAI API error: {str(e)[:150]}")
        return None
    except Exception as e:
        st.error(f"Transcription failed: {str(e)[:150]}")
        return None
    finally:
        # Clean up all temp files
        for path in chunk_paths:
            try:
                os.unlink(path)
            except:
                pass


def generate_em_summary(client: OpenAI, transcript: str) -> Dict[str, Any]:
    """Generate EM Portfolio Manager focused summary using GPT."""

    # Truncate transcript if too long (GPT-4 context limit)
    max_chars = 100000
    if len(transcript) > max_chars:
        st.warning(f"Transcript is very long ({len(transcript):,} chars) - analyzing first {max_chars:,} characters.")
        transcript = transcript[:max_chars] + "... [truncated]"

    prompt = f"""You are an expert analyst helping Emerging Markets Portfolio Managers extract actionable insights from podcasts.

Analyze this podcast transcript and provide a structured summary:

TRANSCRIPT:
{transcript}

Please provide your analysis in the following JSON format:
{{
    "podcast_summary": "A 3-4 paragraph executive summary focusing on key investment themes, market views, and actionable insights relevant to EM investors",
    "podcast_guest": "Name of the main guest/speaker (or 'Multiple Speakers' if unclear)",
    "podcast_guest_title": "Their title/role",
    "podcast_guest_org": "Their organization",
    "podcast_highlights": "5-7 bullet points (each starting with •) of the most important takeaways for portfolio managers",
    "podcast_details": "Additional context and detailed notes from the discussion"
}}

Focus on: regional views (LatAm, EMEA, Asia, China), asset class opinions (rates, credit, FX, equities), macro themes, risk factors, and investment opportunities discussed."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a financial analyst specializing in Emerging Markets. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )

        result_text = response.choices[0].message.content

        # Try to parse JSON from response
        # Handle markdown code blocks if present
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        result = json.loads(result_text.strip())
        return result

    except json.JSONDecodeError:
        # If JSON parsing fails, create structured response from text
        return {
            "podcast_summary": result_text[:2000] if result_text else "Summary generation failed",
            "podcast_guest": "Unknown",
            "podcast_guest_title": "",
            "podcast_guest_org": "",
            "podcast_highlights": "• Analysis complete - see summary above",
            "podcast_details": ""
        }
    except Exception as e:
        return {
            "podcast_summary": f"GPT summarization failed: {str(e)[:200]}",
            "podcast_guest": "N/A",
            "podcast_guest_title": "",
            "podcast_guest_org": "",
            "podcast_highlights": "",
            "podcast_details": "",
            "_is_fallback": True
        }


def process_podcast(audio_url: str, episode_page_url: Optional[str] = None,
                    podcast_name: Optional[str] = None, episode_title: Optional[str] = None) -> Dict[str, Any]:
    """Process a podcast episode using OpenAI (Whisper + GPT).

    First checks for existing transcript on podcast platforms (Listen Notes, etc.).
    Falls back to Whisper transcription if no transcript is found.
    """

    # Check for OpenAI API key
    client = get_openai_client()
    if not client:
        return {
            "podcast_summary": "OpenAI API key not configured. Please set your OPENAI_API_KEY environment variable or enter it in the sidebar. Alternatively, use Demo Mode to explore sample podcasts.",
            "podcast_guest": "N/A",
            "podcast_guest_title": "API key required",
            "podcast_guest_org": "Setup required",
            "podcast_highlights": "• Set OPENAI_API_KEY environment variable\n• Or enter API key in the sidebar\n• Or use Demo Mode for sample analysis",
            "podcast_details": "",
            "_is_fallback": True
        }

    transcript = None
    transcript_source = None

    # =====================================================================
    # Step 1: Search for existing transcripts (free and fast)
    # Try multiple sources before falling back to expensive Whisper
    # =====================================================================

    # 1a. Check user-provided Listen Notes URL
    if not transcript and episode_page_url and 'listennotes.com' in episode_page_url.lower():
        update_progress("🔍 Checking Listen Notes for transcript...", 0.05)
        transcript = extract_listennotes_transcript(episode_page_url)
        if transcript:
            transcript_source = "Listen Notes (provided URL)"

    # 1b. Check the episode's own webpage (from RSS link field)
    if not transcript and episode_page_url and 'listennotes.com' not in episode_page_url.lower():
        update_progress("🔍 Checking episode webpage for transcript...", 0.08)
        transcript = extract_transcript_from_episode_page(episode_page_url)
        if transcript:
            transcript_source = "episode webpage"

    # 1c. Search Listen Notes for the episode
    if not transcript and podcast_name and episode_title:
        update_progress("🔍 Searching Listen Notes for transcript...", 0.12)
        ln_url = search_listennotes_for_episode(podcast_name, episode_title)
        if ln_url:
            transcript = extract_listennotes_transcript(ln_url)
            if transcript:
                transcript_source = "Listen Notes (auto-search)"

    # 1d. Search the web for an existing transcript
    if not transcript and podcast_name and episode_title:
        update_progress("🌐 Searching the web for existing transcript...", 0.18)
        transcript = search_web_for_transcript(podcast_name, episode_title)
        if transcript:
            transcript_source = "web search"

    # Notify user if transcript was found
    if transcript and transcript_source:
        st.toast(f"Found existing transcript via {transcript_source} - skipping audio transcription!")
        update_progress(f"✅ Transcript found via {transcript_source}!", 0.30)

    # =====================================================================
    # Step 2: Fall back to Whisper transcription if no existing transcript
    # =====================================================================
    if not transcript:
        update_progress("📥 No transcript found online. Downloading podcast audio...", 0.25)
        audio_path = download_audio(audio_url)
        if not audio_path:
            return {
                "podcast_summary": "Failed to download podcast audio. The file may be too large or the URL may be inaccessible.",
                "podcast_guest": "N/A",
                "podcast_guest_title": "Download failed",
                "podcast_guest_org": "",
                "podcast_highlights": "• Check if the audio URL is accessible\n• Try a shorter episode\n• Use Demo Mode for sample analysis",
                "podcast_details": "",
                "_is_fallback": True
            }

        update_progress("🎤 Transcribing with OpenAI Whisper (this may take a few minutes)...", 0.40)
        transcript = transcribe_audio(client, audio_path)
        if not transcript:
            return {
                "podcast_summary": "Transcription failed. The audio format may not be supported or there was an API error.",
                "podcast_guest": "N/A",
                "podcast_guest_title": "Transcription failed",
                "podcast_guest_org": "",
                "podcast_highlights": "• Check OpenAI API status\n• Verify API key has Whisper access\n• Try a different episode",
                "podcast_details": "",
                "_is_fallback": True
            }
        transcript_source = "Whisper transcription"

    # Generate EM-focused summary with GPT
    update_progress("🤖 Generating EM Portfolio Manager analysis...", 0.75)
    result = generate_em_summary(client, transcript)
    update_progress("✅ Analysis complete!", 1.0)

    # Add transcript to details if not present
    if not result.get('podcast_details'):
        result['podcast_details'] = transcript[:5000] + "..." if len(transcript) > 5000 else transcript

    # Store transcript source metadata
    result['_transcript_source'] = transcript_source

    return result


def format_highlights(highlights: str) -> list:
    """Parse highlights string into a list."""
    if not highlights:
        return []
    return [h.strip() for h in highlights.split('\n') if h.strip()]


def extract_em_insights(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and structure insights from an EM Portfolio Manager perspective.
    Analyzes the summary and highlights to identify investment-relevant information.
    """
    summary = result.get('podcast_summary', '')
    highlights = result.get('podcast_highlights', '')
    details = result.get('podcast_details', '')
    full_text = f"{summary} {highlights} {details}".lower()

    # Regional mentions
    regions_mentioned = []
    region_keywords = {
        "Latin America": ["brazil", "mexico", "argentina", "chile", "colombia", "peru", "latam", "latin america", "south america"],
        "EMEA": ["turkey", "south africa", "egypt", "nigeria", "poland", "hungary", "czech", "romania", "emea"],
        "Asia ex-China": ["india", "indonesia", "vietnam", "philippines", "thailand", "malaysia", "korea", "taiwan", "asia"],
        "China": ["china", "chinese", "beijing", "shanghai", "renminbi", "yuan", "cny"],
        "Frontier Markets": ["frontier", "kenya", "bangladesh", "sri lanka", "pakistan", "ghana", "zambia"],
        "GCC/Middle East": ["saudi", "uae", "qatar", "kuwait", "gcc", "middle east", "gulf"],
        "Eastern Europe": ["russia", "ukraine", "poland", "hungary", "czech", "romania", "eastern europe"],
    }

    for region, keywords in region_keywords.items():
        if any(kw in full_text for kw in keywords):
            regions_mentioned.append(region)

    # Asset class mentions
    asset_classes_mentioned = []
    asset_keywords = {
        "Hard Currency Sovereigns": ["hard currency", "dollar bond", "usd bond", "sovereign debt", "eurobond"],
        "Local Currency Sovereigns": ["local currency", "local bond", "domestic bond", "local rates"],
        "EM Corporates": ["corporate bond", "em corporate", "corporate credit", "high yield corporate"],
        "EM Equities": ["equities", "stocks", "equity market", "stock market"],
        "EM FX": ["currency", "fx", "foreign exchange", "depreciation", "appreciation"],
    }

    for asset_class, keywords in asset_keywords.items():
        if any(kw in full_text for kw in keywords):
            asset_classes_mentioned.append(asset_class)

    # Sentiment indicators
    bullish_keywords = ["bullish", "optimistic", "opportunity", "undervalued", "attractive", "upside", "rally", "recovery", "positive"]
    bearish_keywords = ["bearish", "pessimistic", "risk", "overvalued", "downside", "sell", "decline", "negative", "concern", "worried"]

    bullish_count = sum(1 for kw in bullish_keywords if kw in full_text)
    bearish_count = sum(1 for kw in bearish_keywords if kw in full_text)

    if bullish_count > bearish_count + 2:
        sentiment = "Bullish"
    elif bearish_count > bullish_count + 2:
        sentiment = "Bearish"
    else:
        sentiment = "Neutral/Mixed"

    # Key themes extraction
    theme_keywords = {
        "Monetary Policy": ["rate cut", "rate hike", "central bank", "fed", "monetary policy", "inflation"],
        "Credit Conditions": ["credit", "spread", "default", "restructuring", "npls", "non-performing"],
        "Growth Outlook": ["gdp", "growth", "recession", "slowdown", "recovery", "expansion"],
        "Political Risk": ["election", "political", "government", "reform", "policy change"],
        "External Flows": ["inflows", "outflows", "capital flows", "foreign investment", "fund flows"],
        "Currency Dynamics": ["currency", "depreciation", "appreciation", "fx", "dollar strength"],
        "Commodity Impact": ["oil", "commodity", "metals", "energy", "agriculture"],
        "ESG/Climate": ["esg", "climate", "sustainability", "green", "transition"],
    }

    themes_identified = []
    for theme, keywords in theme_keywords.items():
        if any(kw in full_text for kw in keywords):
            themes_identified.append(theme)

    # Extract any specific countries/names mentioned
    country_patterns = [
        r'\b(brazil|mexico|turkey|india|china|indonesia|south africa|argentina|chile|colombia|poland|hungary|egypt|nigeria|pakistan|vietnam|philippines|thailand|malaysia|romania|czech|saudi|uae|qatar)\b'
    ]

    countries_mentioned = []
    for pattern in country_patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        countries_mentioned.extend([m.title() for m in matches])
    countries_mentioned = list(set(countries_mentioned))[:8]  # Top 8 unique

    return {
        "regions": regions_mentioned if regions_mentioned else ["Global/Broad EM"],
        "asset_classes": asset_classes_mentioned if asset_classes_mentioned else ["Multiple"],
        "sentiment": sentiment,
        "themes": themes_identified if themes_identified else ["General Market Commentary"],
        "countries": countries_mentioned,
        "bullish_score": bullish_count,
        "bearish_score": bearish_count,
    }


def format_investment_summary(result: Dict[str, Any], em_insights: Dict[str, Any]) -> str:
    """Format the summary as a structured investment research note."""
    summary = result.get('podcast_summary', 'No summary available.')
    highlights = result.get('podcast_highlights', '')

    # Parse highlights into actionable items
    highlight_items = format_highlights(highlights)

    formatted = f"""
**Overall Sentiment:** {em_insights['sentiment']}

**Key Investment Themes:**
{chr(10).join(f"• {theme}" for theme in em_insights['themes'])}

**Regional Focus:**
{chr(10).join(f"• {region}" for region in em_insights['regions'])}

**Countries Discussed:**
{', '.join(em_insights['countries']) if em_insights['countries'] else 'Broad EM discussion'}

**Asset Classes Relevant:**
{chr(10).join(f"• {ac}" for ac in em_insights['asset_classes'])}

---

**Executive Summary:**
{summary}

---

**Key Takeaways for Portfolio Positioning:**
{chr(10).join(f"{i+1}. {h.lstrip('•-* ').strip()}" for i, h in enumerate(highlight_items) if h.strip())}
"""
    return formatted


def add_to_history(episode_title: str, podcast_title: str, result: Dict[str, Any]):
    """Add a processed podcast to history."""
    history_entry = {
        'episode_title': episode_title,
        'podcast_title': podcast_title,
        'timestamp': datetime.now().isoformat(),
        'summary': result.get('podcast_summary', '')[:200] + '...',
        'guest': result.get('podcast_guest', 'Unknown'),
        'full_result': result
    }
    st.session_state.history.insert(0, history_entry)
    # Keep only last 20 entries
    st.session_state.history = st.session_state.history[:20]


def generate_markdown_export(episode_title: str, result: Dict[str, Any]) -> str:
    """Generate a markdown export of the podcast summary."""
    md = f"""# {episode_title}

## Summary
{result.get('podcast_summary', 'No summary available.')}

## Guest Information
- **Name:** {result.get('podcast_guest', 'Unknown')}
- **Title:** {result.get('podcast_guest_title', 'N/A')}
- **Organization:** {result.get('podcast_guest_org', 'N/A')}

## Key Highlights
{result.get('podcast_highlights', 'No highlights available.')}

---
*Generated by PodcastGPT on {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    return md


def generate_research_note(episode_title: str, result: Dict[str, Any],
                           em_insights: Dict[str, Any], episode_info: Optional[Dict] = None,
                           topic_breakdown: Optional[Dict[str, List[str]]] = None) -> str:
    """Generate a professional EM research note format with topic breakdown."""
    guest_name = result.get('podcast_guest', 'Unknown')
    guest_title = result.get('podcast_guest_title', '')
    guest_org = result.get('podcast_guest_org', '')
    podcast_title = episode_info.get('podcast_title', 'Podcast') if episode_info else 'Podcast'

    highlights = format_highlights(result.get('podcast_highlights', ''))
    takeaways = '\n'.join(f"{i+1}. {h.lstrip('•-* ').strip()}"
                          for i, h in enumerate(highlights) if h.strip())

    # Format topic breakdown
    topic_section = ""
    if topic_breakdown:
        topic_parts = []
        for topic, points in topic_breakdown.items():
            topic_parts.append(f"### {topic}")
            for point in points[:4]:  # Limit to 4 points per topic
                clean_point = point[:200] + "..." if len(point) > 200 else point
                topic_parts.append(f"- {clean_point}")
            topic_parts.append("")
        topic_section = "\n".join(topic_parts)
    else:
        topic_section = "No structured topics extracted."

    note = f"""# EM Research Note: Podcast Summary
## {episode_title}

**Source:** {podcast_title}
**Date:** {datetime.now().strftime('%Y-%m-%d')}
**Analyst:** PodcastGPT AI

---

## QUICK REFERENCE

| Metric | Value |
|--------|-------|
| **Overall Sentiment** | {em_insights['sentiment']} |
| **Primary Regions** | {', '.join(em_insights['regions'])} |
| **Countries Discussed** | {', '.join(em_insights['countries']) if em_insights['countries'] else 'Broad EM'} |
| **Asset Classes** | {', '.join(em_insights['asset_classes'])} |
| **Key Themes** | {', '.join(em_insights['themes'])} |

---

## GUEST PROFILE

**{guest_name}**
{guest_title}
{guest_org}

---

## EXECUTIVE SUMMARY

{result.get('podcast_summary', 'No summary available.')}

---

## DETAILED TOPIC BREAKDOWN

{topic_section}

---

## KEY INVESTMENT THEMES

{chr(10).join(f"### {theme}" for theme in em_insights['themes'])}

---

## ACTIONABLE TAKEAWAYS

{takeaways if takeaways else 'No specific takeaways extracted.'}

---

## REGIONAL BREAKDOWN

{chr(10).join(f"- **{region}**: Discussed in this episode" for region in em_insights['regions'])}

---

## RISK CONSIDERATIONS

Based on the discussion, portfolio managers should consider:
- Sentiment indicators suggest a **{em_insights['sentiment'].lower()}** bias
- Focus areas: {', '.join(em_insights['themes'][:3])}
- Geographic exposure: {', '.join(em_insights['countries'][:5]) if em_insights['countries'] else 'Broad EM exposure'}

---

## APPENDIX: SENTIMENT ANALYSIS

- Bullish signals detected: {em_insights['bullish_score']}
- Bearish signals detected: {em_insights['bearish_score']}
- Net sentiment: {'Positive' if em_insights['bullish_score'] > em_insights['bearish_score'] else 'Negative' if em_insights['bearish_score'] > em_insights['bullish_score'] else 'Neutral'}

---

*This research note was automatically generated by PodcastGPT on {datetime.now().strftime('%Y-%m-%d %H:%M')}*
*For internal use only. Not investment advice.*
"""
    return note


def generate_quick_summary(episode_title: str, result: Dict[str, Any],
                           em_insights: Dict[str, Any]) -> str:
    """Generate a quick summary suitable for email/slack."""
    highlights = format_highlights(result.get('podcast_highlights', ''))
    takeaways = '\n'.join(f"  - {h.lstrip('•-* ').strip()}"
                          for h in highlights[:5] if h.strip())

    summary = f"""EM PODCAST SUMMARY: {episode_title}

SENTIMENT: {em_insights['sentiment']}
REGIONS: {', '.join(em_insights['regions'])}
THEMES: {', '.join(em_insights['themes'][:4])}

GUEST: {result.get('podcast_guest', 'Unknown')} ({result.get('podcast_guest_org', 'N/A')})

KEY POINTS:
{takeaways}

BOTTOM LINE:
{result.get('podcast_summary', 'No summary available.')[:500]}...

---
Generated by PodcastGPT | {datetime.now().strftime('%Y-%m-%d')}
"""
    return summary


# ============================================================================
# UI Components
# ============================================================================

def render_header():
    """Render the app header."""
    st.markdown("""
    <div class="app-header">
        <h1>🎙️ PodcastGPT</h1>
        <p>AI-Powered Podcast Analysis for Emerging Markets Portfolio Managers</p>
    </div>
    """, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_demo_data() -> Optional[Dict[str, Any]]:
    """Load demo data from local JSON files."""
    demo_files = {
        "Odd Lots - China Economy Deep Dive": "podcast-1.json",
        "EM Decoded - Emerging Markets Outlook": "podcast-2.json",
    }

    available_demos = {}
    for name, filepath in demo_files.items():
        if os.path.exists(filepath):
            available_demos[name] = filepath

    return available_demos if available_demos else None


@st.cache_data(show_spinner=False)
def _load_demo_json(filepath: str) -> Dict[str, Any]:
    """Load and cache demo JSON data."""
    with open(filepath, 'r') as f:
        return json.load(f)


def render_sidebar():
    """Render the sidebar with podcast input options."""
    with st.sidebar:
        # API Key configuration
        if 'openai_api_key' not in st.session_state:
            st.session_state.openai_api_key = os.environ.get('OPENAI_API_KEY', '')

        with st.expander("⚙️ API Configuration", expanded=not st.session_state.openai_api_key):
            api_key = st.text_input(
                "OpenAI API Key",
                value=st.session_state.openai_api_key,
                type="password",
                help="Required for live podcast processing. Get your key at platform.openai.com"
            )
            if api_key != st.session_state.openai_api_key:
                st.session_state.openai_api_key = api_key

            if st.session_state.openai_api_key:
                st.success("API key configured")
            else:
                st.warning("Enter API key for live processing, or use Demo Mode")

        st.markdown("---")
        st.markdown("### 🎧 Select Podcast")

        # Check for demo data availability
        demo_data = load_demo_data()

        # Input method selection
        input_options = ["Sample Podcasts", "RSS Feed URL"]
        if demo_data:
            input_options.insert(0, "Demo Mode (Offline)")

        input_method = st.radio(
            "Choose input method:",
            input_options,
            label_visibility="collapsed"
        )

        feed_url = None
        use_demo = False

        if input_method == "Demo Mode (Offline)":
            st.markdown("##### 🎬 Demo Mode")
            st.info("Using pre-loaded sample data - no network required!")
            if demo_data:
                selected_demo = st.selectbox(
                    "Select demo episode:",
                    options=list(demo_data.keys()),
                    help="Pre-analyzed podcast episodes for demonstration"
                )
                use_demo = True
            else:
                st.warning("No demo files found.")

        elif input_method == "Sample Podcasts":
            st.markdown("##### Quick Start")
            selected_sample = st.selectbox(
                "Select a podcast:",
                options=list(SAMPLE_PODCASTS.keys()),
                help="Choose from popular podcasts to try the app"
            )
            feed_url = SAMPLE_PODCASTS[selected_sample]

        else:  # RSS Feed URL or Listen Notes
            st.markdown("##### 🔗 Paste Any Podcast URL")
            user_url = st.text_input(
                "Podcast URL:",
                placeholder="RSS feed, Listen Notes, or podcast page URL",
                help="Paste any podcast URL - we'll auto-detect the format!"
            )

            # Show supported formats
            st.caption("✅ Supported: RSS feeds, Listen Notes URLs")
            st.caption("ℹ️ Apple/Spotify: We'll guide you to the RSS feed")

            # Store for later processing
            feed_url = user_url if user_url else None

        st.markdown("---")

        # Demo mode - load directly
        if use_demo and demo_data:
            if st.button("📊 Load Demo Analysis", use_container_width=True, type="primary"):
                filepath = demo_data[selected_demo]
                try:
                    result = _load_demo_json(filepath)
                    st.session_state.last_result = result
                    st.session_state.selected_episode = selected_demo
                    st.session_state.current_episodes = {
                        "episodes": {
                            selected_demo: {
                                'podcast_title': 'Demo Podcast',
                                'image': '',
                                'description': 'Pre-loaded demo data'
                            }
                        }
                    }
                    add_to_history(selected_demo, "Demo", result)
                    st.toast("Demo analysis loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load demo: {str(e)}")

        # Fetch episodes button (for non-demo modes)
        elif st.button("🔍 Fetch Episodes", use_container_width=True, type="primary"):
            if feed_url:
                with st.spinner("Detecting URL type and fetching episodes..."):
                    # Use smart URL detection
                    result = detect_and_process_url(feed_url)

                    if "error" in result:
                        st.error(result["error"])
                        if "suggestion" in result:
                            st.info(f"💡 {result['suggestion']}")
                    else:
                        st.session_state.current_episodes = result
                        st.toast(f"Found {len(result['episodes'])} episodes from {result.get('podcast_title', 'podcast')}!")
            else:
                st.warning("Please enter a podcast URL")

        # Display episodes if available
        if st.session_state.current_episodes and "episodes" in st.session_state.current_episodes:
            st.markdown("---")
            st.markdown("##### 📋 Episodes")

            episodes = st.session_state.current_episodes["episodes"]
            episode_titles = list(episodes.keys())

            selected = st.selectbox(
                "Select an episode:",
                options=episode_titles,
                format_func=lambda x: x[:80] + "..." if len(x) > 80 else x
            )

            if selected:
                st.session_state.selected_episode = selected

                # Show episode info
                ep_info = episodes[selected]
                if ep_info.get('description'):
                    st.caption(ep_info['description'][:100] + "...")

                # Optional Listen Notes URL for transcript
                with st.expander("📝 Have Listen Notes URL? (optional)", expanded=False):
                    ln_url = st.text_input(
                        "Listen Notes Episode URL",
                        placeholder="https://www.listennotes.com/podcasts/...",
                        help="Paste the Listen Notes URL to use their transcript (if available) instead of Whisper",
                        key="listennotes_url"
                    )
                    if ln_url:
                        st.session_state.episode_listennotes_url = ln_url
                        st.caption("Will check Listen Notes for transcript first")
                    else:
                        st.session_state.episode_listennotes_url = None

                # Show if already cached
                ep_cache_key = f"{ep_info.get('podcast_title', '')}::{selected}"
                already_processed = ep_cache_key in st.session_state.processed_podcasts

                if already_processed:
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("📊 View Cached Result", use_container_width=True, type="primary"):
                            st.session_state.last_result = st.session_state.processed_podcasts[ep_cache_key]
                            st.rerun()
                    with col_btn2:
                        if st.button("🔄 Re-process", use_container_width=True):
                            del st.session_state.processed_podcasts[ep_cache_key]
                            st.session_state.processing = True
                            st.rerun()
                else:
                    if st.button("🚀 Process Episode", use_container_width=True, type="primary"):
                        st.session_state.processing = True
                        st.session_state.processing_start_time = time.time()
                        st.rerun()

        # History section
        if st.session_state.history:
            st.markdown("---")
            st.markdown("##### 📚 Recent History")
            for i, entry in enumerate(st.session_state.history[:5]):
                with st.expander(f"{entry['episode_title'][:30]}..."):
                    st.caption(f"🎙️ {entry['podcast_title']}")
                    st.caption(f"👤 Guest: {entry['guest']}")
                    if st.button("View", key=f"history_{i}"):
                        st.session_state.last_result = entry['full_result']
                        st.session_state.selected_episode = entry['episode_title']
                        st.rerun()


def render_results(episode_title: str, result: Dict[str, Any], episode_info: Optional[Dict] = None):
    """Render the podcast processing results with EM Portfolio Manager focus."""

    # Check if this is fallback/error data
    if result.get('_is_fallback'):
        st.warning("**Processing Issue**: " + result.get('podcast_summary', 'An error occurred.')[:200])

    # Extract EM-focused insights
    em_insights = extract_em_insights(result)

    # Episode header
    st.markdown(f"## 📻 {episode_title}")
    caption_parts = []
    if episode_info and episode_info.get('podcast_title'):
        caption_parts.append(f"From: {episode_info['podcast_title']}")
    if result.get('_transcript_source'):
        caption_parts.append(f"Transcript: {result['_transcript_source']}")
    if caption_parts:
        st.caption(" | ".join(caption_parts))

    st.markdown("---")

    # Quick Investment Dashboard
    st.markdown("### 📊 Investment Dashboard")

    # Metrics row
    metric_cols = st.columns(4)

    with metric_cols[0]:
        sentiment_color = "🟢" if em_insights['sentiment'] == "Bullish" else "🔴" if em_insights['sentiment'] == "Bearish" else "🟡"
        st.metric(
            label="Sentiment",
            value=f"{sentiment_color} {em_insights['sentiment']}"
        )

    with metric_cols[1]:
        st.metric(
            label="Regions Covered",
            value=len(em_insights['regions'])
        )

    with metric_cols[2]:
        st.metric(
            label="Countries Mentioned",
            value=len(em_insights['countries'])
        )

    with metric_cols[3]:
        st.metric(
            label="Key Themes",
            value=len(em_insights['themes'])
        )

    st.markdown("---")

    # Parse summary into topics
    topic_breakdown = parse_summary_into_topics(result)

    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📈 EM Analysis", "📚 Topic Breakdown", "📝 Full Summary", "👤 Guest Info"])

    with tab1:
        # EM-focused analysis view
        col1, col2 = st.columns([3, 2])

        with col1:
            # Investment Themes
            st.markdown("#### 🎯 Key Investment Themes")
            for theme in em_insights['themes']:
                st.markdown(f"""
                <div class="highlight-item">
                    <strong>{theme}</strong>
                </div>
                """, unsafe_allow_html=True)

            # Key Takeaways
            st.markdown("#### 💡 Actionable Takeaways")
            highlights = format_highlights(result.get('podcast_highlights', ''))
            if highlights:
                for i, highlight in enumerate(highlights, 1):
                    clean_highlight = highlight.lstrip('•-* ').strip()
                    if clean_highlight:
                        st.markdown(f"""
                        <div class="highlight-item">
                            <strong>{i}.</strong> {clean_highlight}
                        </div>
                        """, unsafe_allow_html=True)

        with col2:
            # Regional Focus
            st.markdown("#### 🌍 Regional Focus")
            for region in em_insights['regions']:
                st.markdown(f"• **{region}**")

            # Countries
            if em_insights['countries']:
                st.markdown("#### 🏳️ Countries Discussed")
                st.markdown(", ".join(f"**{c}**" for c in em_insights['countries']))

            # Asset Classes
            st.markdown("#### 💼 Relevant Asset Classes")
            for ac in em_insights['asset_classes']:
                st.markdown(f"• {ac}")

            # Sentiment breakdown
            st.markdown("#### 📊 Sentiment Indicators")
            bull_score = em_insights['bullish_score']
            bear_score = em_insights['bearish_score']
            total = bull_score + bear_score if (bull_score + bear_score) > 0 else 1

            st.progress(bull_score / total if total > 0 else 0.5)
            st.caption(f"Bullish signals: {bull_score} | Bearish signals: {bear_score}")

    with tab2:
        # Topic-based breakdown view
        st.markdown("#### 📚 Summary by Topic")
        st.caption("Key points organized by investment theme")

        if topic_breakdown:
            # Display topics in two columns for better layout
            topic_items = list(topic_breakdown.items())
            mid_point = (len(topic_items) + 1) // 2

            col1, col2 = st.columns(2)

            with col1:
                for idx, (topic, points) in enumerate(topic_items[:mid_point]):
                    with st.expander(f"**{topic}** ({len(points)} points)", expanded=idx < 2):
                        for point in points:
                            display_point = point[:250] + "..." if len(point) > 250 else point
                            st.markdown(f"• {display_point}")

            with col2:
                for idx, (topic, points) in enumerate(topic_items[mid_point:]):
                    with st.expander(f"**{topic}** ({len(points)} points)", expanded=idx < 1):
                        for point in points:
                            display_point = point[:250] + "..." if len(point) > 250 else point
                            st.markdown(f"• {display_point}")
        else:
            st.info("No structured topics could be extracted from this episode.")

    with tab3:
        # Full summary view
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("#### 📝 Executive Summary")
            st.markdown(f"""
            <div class="summary-section">
                {result.get('podcast_summary', 'No summary available.')}
            </div>
            """, unsafe_allow_html=True)

        with col2:
            # Podcast image
            if episode_info and episode_info.get('image'):
                st.image(episode_info['image'], use_container_width=True)

    with tab4:
        # Guest information
        col1, col2 = st.columns([1, 2])

        with col1:
            if episode_info and episode_info.get('image'):
                st.image(episode_info['image'], use_container_width=True)

        with col2:
            guest_name = result.get('podcast_guest', 'Unknown')
            guest_title = result.get('podcast_guest_title', '')
            guest_org = result.get('podcast_guest_org', '')

            st.markdown(f"""
            <div class="guest-card">
                <h4>{guest_name}</h4>
                <p>{guest_title}</p>
                <p><strong>{guest_org}</strong></p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**Why This Matters:**")
            st.markdown(f"Understanding the guest's background helps contextualize their views on EM markets and potential biases in their analysis.")

    # Export section
    st.markdown("---")
    st.markdown("### 📤 Export Research Note")

    export_cols = st.columns(3)

    # Generate professional research note
    research_note = generate_research_note(episode_title, result, em_insights, episode_info, topic_breakdown)

    with export_cols[0]:
        st.download_button(
            label="📄 Download Research Note",
            data=research_note,
            file_name=f"EM_Research_Note_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            use_container_width=True
        )

    with export_cols[1]:
        # Quick summary for clipboard
        quick_summary = generate_quick_summary(episode_title, result, em_insights)
        st.download_button(
            label="📋 Quick Summary (Email)",
            data=quick_summary,
            file_name=f"EM_Quick_Summary_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True
        )

    with export_cols[2]:
        if st.button("👁️ Preview Note", use_container_width=True):
            with st.expander("Research Note Preview", expanded=True):
                st.markdown(research_note)


def render_home():
    """Render the home/welcome screen with EM focus."""
    st.markdown("### 👋 Welcome to PodcastGPT for EM Portfolio Managers")

    st.markdown("""
    Transform hours of macro and EM podcast content into **structured, actionable investment insights** in minutes.

    **Built for EM Portfolio Managers who need to:**
    - Stay on top of market commentary from key voices
    - Quickly extract regional views and sentiment
    - Identify investment themes and catalysts
    - Generate research notes for team distribution
    """)

    # Quick stats - EM focused
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
        <div class="metric-card">
            <h2>🌍</h2>
            <p>Regional Analysis</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="metric-card">
            <h2>📊</h2>
            <p>Sentiment Detection</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="metric-card">
            <h2>💼</h2>
            <p>Asset Class Tags</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div class="metric-card">
            <h2>📝</h2>
            <p>Research Notes</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # EM-specific features
    st.markdown("### 📈 EM-Focused Features")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Investment Analysis:**
        - Automatic sentiment scoring (Bullish/Bearish/Neutral)
        - Regional focus detection (LatAm, EMEA, Asia, etc.)
        - Country-specific mentions extraction
        - Asset class relevance tagging
        """)

    with col2:
        st.markdown("""
        **Professional Output:**
        - Structured research note format
        - Quick summary for email/Slack
        - Investment theme identification
        - Actionable takeaways extraction
        """)

    st.markdown("---")

    # Sample podcasts showcase
    st.markdown("### 🎧 Pre-loaded EM & Macro Podcasts")

    podcast_cols = st.columns(len(SAMPLE_PODCASTS))
    for i, (name, _) in enumerate(SAMPLE_PODCASTS.items()):
        with podcast_cols[i]:
            st.markdown(f"**{name.split('(')[0].strip()}**")

    st.markdown("---")
    st.info("👈 **Get started:** Select a podcast from the sidebar and fetch episodes!")


def render_processing_screen():
    """Render the processing screen with real progress tracking."""
    st.markdown("### 🔄 Processing Podcast...")
    st.caption(f"Episode: {st.session_state.selected_episode}")

    progress_bar = st.progress(0)
    status_text = st.empty()

    # Cancel button
    if st.button("Cancel Processing", type="secondary"):
        st.session_state.processing = False
        st.toast("Processing cancelled.")
        st.rerun()

    # Store progress containers in session state so process_podcast can update them
    st.session_state._progress_bar = progress_bar
    st.session_state._status_text = status_text

    return True


def update_progress(step: str, progress: float):
    """Update the processing progress bar and status text."""
    progress_bar = st.session_state.get('_progress_bar')
    status_text = st.session_state.get('_status_text')
    if progress_bar:
        progress_bar.progress(progress)
    if status_text:
        status_text.markdown(f"""
        <div class="status-processing">
            {step}
        </div>
        """, unsafe_allow_html=True)


# ============================================================================
# Main Application
# ============================================================================

def main():
    """Main application entry point."""
    init_session_state()
    render_header()
    render_sidebar()

    # Main content area
    if st.session_state.processing:
        # Processing mode
        render_processing_screen()

        # Do actual processing
        if st.session_state.selected_episode and st.session_state.current_episodes:
            episodes = st.session_state.current_episodes.get("episodes", {})
            episode_info = episodes.get(st.session_state.selected_episode, {})
            audio_url = episode_info.get('audio_url', '')
            episode_title = st.session_state.selected_episode

            # Check if we already processed this episode (deduplication)
            cache_key = f"{episode_info.get('podcast_title', '')}::{episode_title}"
            cached_result = st.session_state.processed_podcasts.get(cache_key)

            if cached_result:
                st.toast("Loaded from cache - this episode was already analyzed!")
                st.session_state.last_result = cached_result
                st.session_state.processing = False
                st.rerun()

            elif audio_url:
                # Use Listen Notes URL if provided, otherwise try RSS link
                episode_page_url = (
                    st.session_state.get('episode_listennotes_url') or
                    episode_info.get('link') or
                    episode_info.get('page_url')
                )
                # Pass podcast and episode names for auto-search
                podcast_name = episode_info.get('podcast_title', '')
                result = process_podcast(
                    audio_url,
                    episode_page_url,
                    podcast_name,
                    episode_title
                )
                # Clear the Listen Notes URL after processing
                st.session_state.episode_listennotes_url = None
                st.session_state.last_result = result
                st.session_state.processing = False

                # Cache the result for deduplication
                st.session_state.processed_podcasts[cache_key] = result

                # Record elapsed time
                if st.session_state.processing_start_time:
                    elapsed = time.time() - st.session_state.processing_start_time
                    mins, secs = divmod(int(elapsed), 60)
                    time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
                    st.toast(f"Analysis complete in {time_str}!")
                    st.session_state.processing_start_time = None

                # Add to history
                add_to_history(
                    episode_title,
                    episode_info.get('podcast_title', 'Unknown Podcast'),
                    result
                )

                st.rerun()
            else:
                st.error("No audio URL found for this episode.")
                st.session_state.processing = False

    elif st.session_state.last_result and st.session_state.selected_episode:
        # Show results
        episode_info = None
        if st.session_state.current_episodes and "episodes" in st.session_state.current_episodes:
            episode_info = st.session_state.current_episodes["episodes"].get(
                st.session_state.selected_episode
            )

        render_results(
            st.session_state.selected_episode,
            st.session_state.last_result,
            episode_info
        )

        # Navigation buttons
        st.markdown("---")
        nav_col1, nav_col2 = st.columns(2)
        with nav_col1:
            if st.button("🔄 Process Another Episode", use_container_width=True):
                st.session_state.last_result = None
                st.session_state.selected_episode = None
                st.rerun()
        with nav_col2:
            if st.session_state.history and len(st.session_state.history) > 1:
                if st.button("📚 View Last Analysis", use_container_width=True):
                    # Load the second-most-recent history entry (first is current)
                    prev = st.session_state.history[1]
                    st.session_state.last_result = prev['full_result']
                    st.session_state.selected_episode = prev['episode_title']
                    st.rerun()

    else:
        # Home screen
        render_home()


if __name__ == '__main__':
    main()
