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

# ============================================================================
# Configuration & Constants
# ============================================================================

APP_TITLE = "PodcastGPT"
APP_ICON = "🎙️"
APP_DESCRIPTION = "AI-Powered Podcast Analysis for EM Portfolio Managers"

# Sample podcasts - EM and Macro focused (using reliable RSS feeds)
SAMPLE_PODCASTS = {
    "All-In Podcast": "https://feeds.megaphone.fm/all-in-with-chamath-jason-sacks-friedberg",
    "Invest Like the Best": "https://feeds.megaphone.fm/investlikethebest",
    "Macro Voices": "https://feeds.megaphone.fm/macrovoices",
    "Real Vision Daily Briefing": "https://feeds.megaphone.fm/realvision",
    "The Prof G Pod": "https://feeds.megaphone.fm/profgpod",
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


# ============================================================================
# Utility Functions
# ============================================================================

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
                description = item.findtext('itunes:summary', namespaces) or ''
            # Clean HTML tags and truncate
            description = re.sub(r'<[^>]+>', '', description)[:200]

            # Get published date
            published = item.findtext('pubDate', '')

            if audio_url:  # Only add if we have an audio URL
                episodes[title] = {
                    'audio_url': audio_url,
                    'image': episode_image,
                    'description': description,
                    'published': published,
                    'podcast_title': podcast_title
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


def process_podcast(audio_url: str) -> Dict[str, Any]:
    """Process a podcast episode using Modal backend or local sample data."""
    try:
        # First, try to use Modal backend
        import modal
        f = modal.Function.lookup("corise-podcast-project", "process_podcast")
        result = f.remote(audio_url, '/content/')
        return result
    except Exception as e:
        # If Modal fails, check for sample data
        sample_files = ['podcast-1.json', 'podcast-2.json']
        for sample_file in sample_files:
            if os.path.exists(sample_file):
                try:
                    with open(sample_file, 'r') as f:
                        return json.load(f)
                except:
                    continue

        # Return demo data if nothing else works
        return {
            "podcast_summary": "Unable to process this podcast. The Modal backend is not configured or the sample data files are not available. Please ensure Modal is properly set up with the 'corise-podcast-project' project.",
            "podcast_guest": "N/A",
            "podcast_guest_title": "Backend not configured",
            "podcast_guest_org": "Please configure Modal backend",
            "podcast_highlights": "• Configure Modal backend for live transcription\n• Ensure API keys are set up\n• Check network connectivity"
        }


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
                           em_insights: Dict[str, Any], episode_info: Optional[Dict] = None) -> str:
    """Generate a professional EM research note format."""
    guest_name = result.get('podcast_guest', 'Unknown')
    guest_title = result.get('podcast_guest_title', '')
    guest_org = result.get('podcast_guest_org', '')
    podcast_title = episode_info.get('podcast_title', 'Podcast') if episode_info else 'Podcast'

    highlights = format_highlights(result.get('podcast_highlights', ''))
    takeaways = '\n'.join(f"{i+1}. {h.lstrip('•-* ').strip()}"
                          for i, h in enumerate(highlights) if h.strip())

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


def render_sidebar():
    """Render the sidebar with podcast input options."""
    with st.sidebar:
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

        else:  # RSS Feed URL
            st.markdown("##### Enter RSS Feed")
            feed_url = st.text_input(
                "Paste RSS feed URL:",
                placeholder="https://example.com/podcast/feed.xml",
                help="Find RSS feeds on podcast platforms or Listen Notes"
            )

            with st.expander("💡 How to find RSS feeds"):
                st.markdown("""
                1. Go to [Listen Notes](https://www.listennotes.com/)
                2. Search for your podcast
                3. Click on the podcast page
                4. Find the **RSS** button and copy the link
                """)

        st.markdown("---")

        # Demo mode - load directly
        if use_demo and demo_data:
            if st.button("📊 Load Demo Analysis", use_container_width=True, type="primary"):
                filepath = demo_data[selected_demo]
                try:
                    with open(filepath, 'r') as f:
                        result = json.load(f)
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
                    st.success("Demo loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load demo: {str(e)}")

        # Fetch episodes button (for non-demo modes)
        elif st.button("🔍 Fetch Episodes", use_container_width=True, type="primary"):
            if feed_url:
                with st.spinner("Fetching episodes..."):
                    result = parse_podcast_feed(feed_url)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.current_episodes = result
                        st.success(f"Found {len(result['episodes'])} episodes!")
            else:
                st.warning("Please enter an RSS feed URL")

        # Display episodes if available
        if st.session_state.current_episodes and "episodes" in st.session_state.current_episodes:
            st.markdown("---")
            st.markdown("##### 📋 Episodes")

            episodes = st.session_state.current_episodes["episodes"]
            episode_titles = list(episodes.keys())

            selected = st.selectbox(
                "Select an episode:",
                options=episode_titles,
                format_func=lambda x: x[:50] + "..." if len(x) > 50 else x
            )

            if selected:
                st.session_state.selected_episode = selected

                # Show episode info
                ep_info = episodes[selected]
                if ep_info.get('description'):
                    st.caption(ep_info['description'][:100] + "...")

                # Process button
                if st.button("🚀 Process Episode", use_container_width=True, type="primary"):
                    st.session_state.processing = True
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

    # Extract EM-focused insights
    em_insights = extract_em_insights(result)

    # Episode header
    st.markdown(f"## 📻 {episode_title}")
    if episode_info and episode_info.get('podcast_title'):
        st.caption(f"From: {episode_info['podcast_title']}")

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

    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["📈 EM Analysis", "📝 Full Summary", "👤 Guest Info"])

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

    with tab3:
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
    research_note = generate_research_note(episode_title, result, em_insights, episode_info)

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
    """Render the processing screen with progress indicators."""
    st.markdown("### 🔄 Processing Podcast...")

    progress_container = st.empty()
    status_container = st.empty()

    steps = [
        ("📥 Fetching audio...", 0.2),
        ("🎤 Transcribing content...", 0.5),
        ("🤖 Analyzing with AI...", 0.7),
        ("📝 Generating summary...", 0.9),
        ("✅ Complete!", 1.0),
    ]

    progress_bar = progress_container.progress(0)

    for step_text, progress in steps:
        status_container.markdown(f"""
        <div class="status-processing">
            {step_text}
        </div>
        """, unsafe_allow_html=True)
        progress_bar.progress(progress)
        time.sleep(0.5)  # Simulate processing steps

    return True


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

            if audio_url:
                with st.spinner("Finalizing..."):
                    result = process_podcast(audio_url)
                    st.session_state.last_result = result
                    st.session_state.processing = False

                    # Add to history
                    add_to_history(
                        st.session_state.selected_episode,
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

        # Clear button
        st.markdown("---")
        if st.button("🔄 Process Another Episode", use_container_width=True):
            st.session_state.last_result = None
            st.session_state.selected_episode = None
            st.rerun()

    else:
        # Home screen
        render_home()


if __name__ == '__main__':
    main()
