"""
EM (Emerging Markets) insight extraction from podcast summaries.

Pure-logic helpers — no Streamlit or network calls. Easily testable
and reusable from any page or background job.
"""

import re
from datetime import datetime
from typing import Any, Dict, List

# ── Constants ────────────────────────────────────────────────────────────

EM_REGIONS = [
    "Latin America", "EMEA", "Asia ex-China", "China",
    "Frontier Markets", "GCC/Middle East", "Eastern Europe",
]

EM_ASSET_CLASSES = [
    "Hard Currency Sovereigns", "Local Currency Sovereigns",
    "EM Corporates (IG)", "EM Corporates (HY)",
    "EM Equities", "EM FX",
]

REGION_KEYWORDS = {
    "Latin America": ["brazil", "mexico", "argentina", "chile", "colombia",
                       "peru", "latam", "latin america", "south america"],
    "EMEA": ["turkey", "south africa", "egypt", "nigeria", "poland",
             "hungary", "czech", "romania", "emea"],
    "Asia ex-China": ["india", "indonesia", "vietnam", "philippines",
                       "thailand", "malaysia", "korea", "taiwan", "asia"],
    "China": ["china", "chinese", "beijing", "shanghai", "renminbi", "yuan", "cny"],
    "Frontier Markets": ["frontier", "kenya", "bangladesh", "sri lanka",
                          "pakistan", "ghana", "zambia"],
    "GCC/Middle East": ["saudi", "uae", "qatar", "kuwait", "gcc",
                         "middle east", "gulf"],
    "Eastern Europe": ["russia", "ukraine", "poland", "hungary",
                        "czech", "romania", "eastern europe"],
}

ASSET_KEYWORDS = {
    "Hard Currency Sovereigns": ["hard currency", "dollar bond", "usd bond",
                                  "sovereign debt", "eurobond"],
    "Local Currency Sovereigns": ["local currency", "local bond",
                                   "domestic bond", "local rates"],
    "EM Corporates": ["corporate bond", "em corporate", "corporate credit",
                       "high yield corporate"],
    "EM Equities": ["equities", "stocks", "equity market", "stock market"],
    "EM FX": ["currency", "fx", "foreign exchange", "depreciation", "appreciation"],
}

THEME_KEYWORDS = {
    "Monetary Policy": ["rate cut", "rate hike", "central bank", "fed",
                         "monetary policy", "inflation"],
    "Credit Conditions": ["credit", "spread", "default", "restructuring",
                           "npls", "non-performing"],
    "Growth Outlook": ["gdp", "growth", "recession", "slowdown",
                        "recovery", "expansion"],
    "Political Risk": ["election", "political", "government", "reform",
                        "policy change"],
    "External Flows": ["inflows", "outflows", "capital flows",
                        "foreign investment", "fund flows"],
    "Currency Dynamics": ["currency", "depreciation", "appreciation",
                           "fx", "dollar strength"],
    "Commodity Impact": ["oil", "commodity", "metals", "energy", "agriculture"],
    "ESG/Climate": ["esg", "climate", "sustainability", "green", "transition"],
}

BULLISH_KEYWORDS = ["bullish", "optimistic", "opportunity", "undervalued",
                     "attractive", "upside", "rally", "recovery", "positive"]
BEARISH_KEYWORDS = ["bearish", "pessimistic", "risk", "overvalued", "downside",
                     "sell", "decline", "negative", "concern", "worried"]

COUNTRY_PATTERN = re.compile(
    r'\b(brazil|mexico|turkey|india|china|indonesia|south africa|argentina|'
    r'chile|colombia|poland|hungary|egypt|nigeria|pakistan|vietnam|philippines|'
    r'thailand|malaysia|romania|czech|saudi|uae|qatar)\b',
    re.IGNORECASE,
)


def _topic_categories() -> Dict[str, List[str]]:
    """Topic categories — uses current year so list updates yearly."""
    year = datetime.now().year
    return {
        "Market Outlook": ["outlook", "forecast", "expect", "predict",
                            str(year), str(year + 1), "next year", "going forward"],
        "Monetary Policy": ["rate", "fed", "central bank", "inflation",
                             "interest", "hiking", "cutting", "pause", "pivot"],
        "Growth & Economy": ["gdp", "growth", "recession", "slowdown",
                              "expansion", "economic", "economy"],
        "Credit & Fixed Income": ["credit", "bond", "spread", "yield",
                                   "duration", "default", "high yield",
                                   "investment grade"],
        "Currencies & FX": ["currency", "dollar", "fx", "depreciation",
                             "appreciation", "exchange rate", "carry"],
        "Equities": ["stock", "equity", "valuation", "earnings", "p/e",
                      "multiple", "index"],
        "Geopolitics & Policy": ["election", "political", "government",
                                  "regulation", "sanction", "trade war", "tariff"],
        "China Focus": ["china", "chinese", "beijing", "xi", "property", "evergrande"],
        "Commodities": ["oil", "commodity", "metal", "gold", "copper", "energy"],
        "Risk Factors": ["risk", "concern", "worry", "downside",
                          "volatility", "uncertainty"],
    }


# ── Public API ──────────────────────────────────────────────────────────

def format_highlights(highlights: str) -> List[str]:
    """Parse highlights string into a list."""
    if not highlights:
        return []
    return [h.strip() for h in highlights.split("\n") if h.strip()]


def extract_em_insights(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract EM-focused insights from a podcast analysis result."""
    summary = result.get("podcast_summary", "")
    highlights = result.get("podcast_highlights", "")
    details = result.get("podcast_details", "")
    full_text = f"{summary} {highlights} {details}".lower()

    regions_mentioned = [
        region for region, kws in REGION_KEYWORDS.items()
        if any(kw in full_text for kw in kws)
    ]

    asset_classes_mentioned = [
        ac for ac, kws in ASSET_KEYWORDS.items()
        if any(kw in full_text for kw in kws)
    ]

    bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in full_text)
    bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in full_text)

    if bullish_count > bearish_count + 2:
        sentiment = "Bullish"
    elif bearish_count > bullish_count + 2:
        sentiment = "Bearish"
    else:
        sentiment = "Neutral/Mixed"

    themes_identified = [
        theme for theme, kws in THEME_KEYWORDS.items()
        if any(kw in full_text for kw in kws)
    ]

    countries = list({m.title() for m in COUNTRY_PATTERN.findall(full_text)})[:8]

    return {
        "regions": regions_mentioned or ["Global/Broad EM"],
        "asset_classes": asset_classes_mentioned or ["Multiple"],
        "sentiment": sentiment,
        "themes": themes_identified or ["General Market Commentary"],
        "countries": countries,
        "bullish_score": bullish_count,
        "bearish_score": bearish_count,
    }


def parse_summary_into_topics(result: Dict[str, Any]) -> Dict[str, List[str]]:
    """Group sentences from summary/details into topic-based bullets."""
    summary = result.get("podcast_summary", "")
    details = result.get("podcast_details", "")
    highlights = result.get("podcast_highlights", "")

    full_text = f"{summary} {details}"
    sentences = re.split(r"(?<=[.!?])\s+", full_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    categorized: Dict[str, List[str]] = {}
    used = set()

    for topic, keywords in _topic_categories().items():
        topic_sentences: List[str] = []
        for i, sentence in enumerate(sentences):
            if i in used:
                continue
            if any(kw in sentence.lower() for kw in keywords):
                clean = sentence.strip()
                if clean and len(clean) > 30:
                    topic_sentences.append(clean)
                    used.add(i)
        if topic_sentences:
            categorized[topic] = topic_sentences[:4]

    if highlights:
        items = [h.strip().lstrip("•-* ") for h in highlights.split("\n") if h.strip()]
        if items:
            categorized["Key Takeaways"] = items[:6]

    other = [sentences[i] for i in range(len(sentences))
             if i not in used and len(sentences[i]) > 50][:4]
    if other:
        categorized["Other Insights"] = other

    return categorized


def format_topics_as_markdown(topics: Dict[str, List[str]]) -> str:
    """Format topic dict as markdown."""
    if not topics:
        return "No structured topics extracted."
    parts: List[str] = []
    for topic, points in topics.items():
        parts.append(f"### {topic}")
        for p in points:
            if len(p) > 300:
                p = p[:297] + "..."
            parts.append(f"- {p}")
        parts.append("")
    return "\n".join(parts)


def format_investment_summary(result: Dict[str, Any], em_insights: Dict[str, Any]) -> str:
    """Format the analysis as a structured investment summary block."""
    summary = result.get("podcast_summary", "No summary available.")
    highlight_items = format_highlights(result.get("podcast_highlights", ""))

    return f"""
**Overall Sentiment:** {em_insights['sentiment']}

**Key Investment Themes:**
{chr(10).join(f"• {t}" for t in em_insights['themes'])}

**Regional Focus:**
{chr(10).join(f"• {r}" for r in em_insights['regions'])}

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
