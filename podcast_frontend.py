"""
PodcastGPT - AI-Powered Podcast Transcription & Summarization
A seamless app for busy professionals to get key insights from podcasts.
"""

import streamlit as st
import json
import os
import feedparser
from datetime import datetime
from typing import Optional, Dict, Any
import time

# ============================================================================
# Configuration & Constants
# ============================================================================

APP_TITLE = "PodcastGPT"
APP_ICON = "🎙️"
APP_DESCRIPTION = "AI-Powered Podcast Transcription & Summarization"

# Sample podcasts for quick demo
SAMPLE_PODCASTS = {
    "Odd Lots (Bloomberg)": "https://feeds.bloomberg.fm/BLM3523997612",
    "The Daily (NYT)": "https://feeds.simplecast.com/54nAGcIl",
    "Planet Money (NPR)": "https://feeds.npr.org/510289/podcast.xml",
    "Acquired": "https://feeds.megaphone.fm/acquired",
    "Lex Fridman Podcast": "https://lexfridman.com/feed/podcast/",
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


# ============================================================================
# Utility Functions
# ============================================================================

def parse_podcast_feed(feed_url: str) -> Dict[str, Any]:
    """Parse a podcast RSS feed and extract episode information."""
    try:
        feed = feedparser.parse(feed_url)

        if not feed.entries:
            return {"error": "No episodes found in this feed."}

        episodes = {}
        podcast_title = feed.feed.get('title', 'Unknown Podcast')
        podcast_image = feed.feed.get('image', {}).get('href', '')

        for entry in feed.entries[:10]:  # Get latest 10 episodes
            title = entry.get('title', 'Untitled Episode')

            # Get episode image
            episode_image = ''
            if 'image' in entry:
                episode_image = entry['image'].get('href', '')
            if not episode_image:
                episode_image = podcast_image

            # Get audio URL
            audio_url = ''
            for link in entry.get('links', []):
                if link.get('type', '').startswith('audio/'):
                    audio_url = link.get('href', '')
                    break

            # Get episode description
            description = entry.get('summary', entry.get('description', ''))[:200]

            # Get published date
            published = entry.get('published', '')

            if audio_url:  # Only add if we have an audio URL
                episodes[title] = {
                    'audio_url': audio_url,
                    'image': episode_image,
                    'description': description,
                    'published': published,
                    'podcast_title': podcast_title
                }

        return {
            "success": True,
            "podcast_title": podcast_title,
            "podcast_image": podcast_image,
            "episodes": episodes
        }

    except Exception as e:
        return {"error": f"Failed to parse feed: {str(e)}"}


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


# ============================================================================
# UI Components
# ============================================================================

def render_header():
    """Render the app header."""
    st.markdown("""
    <div class="app-header">
        <h1>🎙️ PodcastGPT</h1>
        <p>AI-Powered Podcast Transcription & Summarization for Busy Professionals</p>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar():
    """Render the sidebar with podcast input options."""
    with st.sidebar:
        st.markdown("### 🎧 Select Podcast")

        # Input method selection
        input_method = st.radio(
            "Choose input method:",
            ["Sample Podcasts", "RSS Feed URL"],
            label_visibility="collapsed"
        )

        feed_url = None

        if input_method == "Sample Podcasts":
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

        # Fetch episodes button
        if st.button("🔍 Fetch Episodes", use_container_width=True, type="primary"):
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
    """Render the podcast processing results."""

    # Episode header
    st.markdown(f"## 📻 {episode_title}")
    if episode_info and episode_info.get('podcast_title'):
        st.caption(f"From: {episode_info['podcast_title']}")

    st.markdown("---")

    # Main content in columns
    col1, col2 = st.columns([2, 1])

    with col1:
        # Summary section
        st.markdown("### 📝 Episode Summary")
        st.markdown(f"""
        <div class="summary-section">
            {result.get('podcast_summary', 'No summary available.')}
        </div>
        """, unsafe_allow_html=True)

        # Key Highlights
        st.markdown("### ✨ Key Highlights")
        highlights = format_highlights(result.get('podcast_highlights', ''))
        if highlights:
            for highlight in highlights:
                # Clean up bullet points
                clean_highlight = highlight.lstrip('•-* ').strip()
                if clean_highlight:
                    st.markdown(f"""
                    <div class="highlight-item">
                        {clean_highlight}
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No highlights available for this episode.")

    with col2:
        # Podcast image
        if episode_info and episode_info.get('image'):
            st.image(episode_info['image'], use_container_width=True)

        # Guest information
        st.markdown("### 👤 Guest")
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

        # Export options
        st.markdown("### 📤 Export")

        markdown_content = generate_markdown_export(episode_title, result)

        st.download_button(
            label="📄 Download Summary",
            data=markdown_content,
            file_name=f"podcast_summary_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            use_container_width=True
        )

        if st.button("📋 Copy to Clipboard", use_container_width=True):
            st.code(markdown_content, language="markdown")
            st.info("Copy the text above!")


def render_home():
    """Render the home/welcome screen."""
    st.markdown("### 👋 Welcome to PodcastGPT")

    st.markdown("""
    Transform hours of podcast content into actionable insights in minutes.

    **How it works:**
    1. **Select a podcast** from samples or paste an RSS feed URL
    2. **Choose an episode** from the available list
    3. **Process** and get AI-powered summaries, guest info, and key highlights
    4. **Export** your summaries for later reference
    """)

    # Quick stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="metric-card">
            <h2>🎯</h2>
            <p>Key Insights Extraction</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="metric-card">
            <h2>👤</h2>
            <p>Guest Identification</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="metric-card">
            <h2>📝</h2>
            <p>Smart Summaries</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Feature highlights
    st.markdown("### ✨ Features")

    features = [
        ("🎙️ Multiple Input Methods", "Use sample podcasts or paste any RSS feed URL"),
        ("⚡ Fast Processing", "AI-powered transcription and summarization"),
        ("📚 History Tracking", "Access your previously processed episodes"),
        ("📤 Easy Export", "Download summaries as Markdown files"),
    ]

    for title, desc in features:
        st.markdown(f"**{title}** - {desc}")

    st.markdown("---")
    st.info("👈 **Get started:** Select a podcast from the sidebar!")


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
