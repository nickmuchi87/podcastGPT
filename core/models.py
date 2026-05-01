"""
Smart model router — balances cost, quality, and task fit.

Supports four providers: Anthropic (Claude), OpenAI (GPT),
Google (Gemini), and DeepSeek. Picks the best model for each
task based on transcript length, user priority, and which API
keys are available.

Usage:
    from core.models import generate_summary, select_model

    result = generate_summary(transcript, task="summary", priority="balanced")
    # result["_model_used"] tells you which model handled it
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# Optional deps — handled gracefully
try:
    from openai import OpenAI as OpenAIClient  # also used for DeepSeek
    _OPENAI_OK = True
except ImportError:
    _OPENAI_OK = False
    OpenAIClient = None

try:
    import anthropic
    _ANTHROPIC_OK = True
except ImportError:
    _ANTHROPIC_OK = False

try:
    import google.generativeai as genai
    _GEMINI_OK = True
except Exception:  # ImportError or pyo3 panic from old crypto bindings
    _GEMINI_OK = False
    genai = None


# ── Model registry ──────────────────────────────────────────────────────
# Costs are USD per 1M tokens (input, output). Approximate as of 2025-2026.

@dataclass(frozen=True)
class ModelSpec:
    name: str             # human-readable label
    provider: str         # "anthropic" | "openai" | "gemini" | "deepseek"
    model_id: str         # provider-specific model identifier
    cost_in: float        # $/Mtok input
    cost_out: float       # $/Mtok output
    context_window: int   # input tokens
    tier: int             # 1 = top, 2 = good, 3 = budget
    quality_score: int    # 0–100, normalized cross-provider quality
    tasks: Tuple[str, ...] = field(default_factory=tuple)
    speed: int = 3        # 1 (slow) … 5 (fast)


MODELS: List[ModelSpec] = [
    # ── Gemini (huge context, Flash Lite is the cheapest option) ────────
    ModelSpec(
        name="Gemini 3.1 Flash Lite",
        provider="gemini",
        model_id="gemini-2.5-flash-lite",
        cost_in=0.10, cost_out=0.40,
        context_window=1_000_000,
        tier=3, quality_score=65,
        tasks=("summary", "qa", "classification", "long_context", "batch"),
        speed=5,
    ),
    ModelSpec(
        name="Gemini 2.5 Flash",
        provider="gemini",
        model_id="gemini-2.5-flash-preview-04-17",
        cost_in=0.30, cost_out=2.50,
        context_window=1_000_000,
        tier=2, quality_score=78,
        tasks=("summary", "qa", "classification", "long_context"),
        speed=5,
    ),
    ModelSpec(
        name="Gemini 3.1 Pro",
        provider="gemini",
        model_id="gemini-2.5-pro-preview-03-25",
        cost_in=1.25, cost_out=10.0,
        context_window=1_000_000,
        tier=1, quality_score=90,
        tasks=("summary", "deep_summary", "qa", "long_context"),
        speed=3,
    ),

    # ── Anthropic ───────────────────────────────────────────────────────
    ModelSpec(
        name="Claude Opus 4.7",
        provider="anthropic",
        model_id="claude-opus-4-7",
        cost_in=15.0, cost_out=75.0,
        context_window=200_000,
        tier=1, quality_score=98,
        tasks=("summary", "deep_summary", "complex_reasoning", "qa"),
        speed=2,
    ),
    ModelSpec(
        name="Claude Sonnet 4.6",
        provider="anthropic",
        model_id="claude-sonnet-4-6",
        cost_in=3.0, cost_out=15.0,
        context_window=200_000,
        tier=1, quality_score=92,
        tasks=("summary", "deep_summary", "qa"),
        speed=4,
    ),
    ModelSpec(
        name="Claude Haiku 4.5",
        provider="anthropic",
        model_id="claude-haiku-4-5-20251001",
        cost_in=1.0, cost_out=5.0,
        context_window=200_000,
        tier=2, quality_score=82,
        tasks=("summary", "qa", "classification", "batch", "long_context"),
        speed=5,
    ),

    # ── OpenAI ──────────────────────────────────────────────────────────
    ModelSpec(
        name="GPT-4o",
        provider="openai",
        model_id="gpt-4o",
        cost_in=2.50, cost_out=10.0,
        context_window=128_000,
        tier=1, quality_score=89,
        tasks=("summary", "deep_summary", "qa"),
        speed=4,
    ),
    ModelSpec(
        name="GPT-4o-mini",
        provider="openai",
        model_id="gpt-4o-mini",
        cost_in=0.15, cost_out=0.60,
        context_window=128_000,
        tier=2, quality_score=68,
        tasks=("summary", "qa", "classification"),
        speed=5,
    ),

    # ── DeepSeek ────────────────────────────────────────────────────────
    ModelSpec(
        name="DeepSeek V3",
        provider="deepseek",
        model_id="deepseek-chat",
        cost_in=0.27, cost_out=1.10,
        context_window=128_000,
        tier=2, quality_score=75,
        tasks=("summary", "qa", "classification"),
        speed=3,
    ),
    ModelSpec(
        name="DeepSeek R1",
        provider="deepseek",
        model_id="deepseek-reasoner",
        cost_in=0.55, cost_out=2.19,
        context_window=64_000,
        tier=1, quality_score=86,
        tasks=("deep_summary", "complex_reasoning"),
        speed=2,
    ),
]


# ── Provider availability ───────────────────────────────────────────────

def _provider_key(provider: str) -> Optional[str]:
    """Look up the API key for a provider (env or Streamlit session state)."""
    keys = {
        "openai": ("OPENAI_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY",),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "deepseek": ("DEEPSEEK_API_KEY",),
    }
    for env_name in keys.get(provider, ()):
        v = os.environ.get(env_name)
        if v:
            return v
    # Try Streamlit session state (lazy import to keep module pure)
    try:
        import streamlit as st
        for env_name in keys.get(provider, ()):
            v = st.session_state.get(env_name.lower())
            if v:
                return v
    except Exception:
        pass
    return None


def available_providers() -> Set[str]:
    """Return set of providers with both an API key and SDK installed."""
    avail = set()
    if _OPENAI_OK and _provider_key("openai"):
        avail.add("openai")
    if _ANTHROPIC_OK and _provider_key("anthropic"):
        avail.add("anthropic")
    if _GEMINI_OK and _provider_key("gemini"):
        avail.add("gemini")
    # DeepSeek uses the OpenAI SDK (compatible API)
    if _OPENAI_OK and _provider_key("deepseek"):
        avail.add("deepseek")
    return avail


# ── Routing ─────────────────────────────────────────────────────────────

def estimate_cost(
    model: ModelSpec, transcript_chars: int, output_tokens: int = 1500
) -> float:
    """Rough USD cost estimate for one inference call."""
    # Rough chars→tokens conversion: 1 token ≈ 4 chars
    in_tokens = transcript_chars / 4
    return (in_tokens / 1_000_000) * model.cost_in + (
        output_tokens / 1_000_000
    ) * model.cost_out


def select_model(
    task: str = "summary",
    transcript_chars: int = 0,
    priority: str = "balanced",
    available: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None,
) -> Optional[ModelSpec]:
    """
    Pick the best model for a given task, balancing cost/quality/speed.

    task:
      - "summary" — default podcast analysis
      - "deep_summary" — high-quality long-form analysis
      - "qa" — chat over transcript
      - "classification" — short tagging tasks
      - "long_context" — transcripts > 200k chars
    priority:
      - "cost" — cheapest model that can do the job
      - "quality" — best tier-1 model regardless of cost
      - "balanced" — quality minus cost penalty (default)
      - "speed" — fastest
    """
    avail = available if available is not None else available_providers()
    excluded = exclude or set()

    # Estimated input tokens (chars / 4) with 50% buffer
    needed_tokens = int((transcript_chars / 4) * 1.5)

    # Filter to viable candidates
    candidates = [
        m for m in MODELS
        if m.provider in avail
        and m.model_id not in excluded
        and m.context_window >= max(needed_tokens, 8_000)
        and (task in m.tasks or task == "summary" and "summary" in m.tasks)
    ]

    # Fallback: if no model handles this task, drop the task constraint
    if not candidates:
        candidates = [
            m for m in MODELS
            if m.provider in avail
            and m.model_id not in excluded
            and m.context_window >= max(needed_tokens, 8_000)
        ]

    if not candidates:
        return None

    def score(m: ModelSpec) -> float:
        # Estimated USD cost for this specific call (input + output)
        est_cost = estimate_cost(m, transcript_chars)
        # Cost-per-call weighting (we care more about output cost)
        weighted_cost = m.cost_in + m.cost_out * 2

        if priority == "cost":
            # Among capable models, pick cheapest
            return -weighted_cost
        if priority == "quality":
            # Pick highest quality_score; cost is a tiny tiebreaker
            return m.quality_score - weighted_cost * 0.001
        if priority == "speed":
            return m.speed * 30 + m.quality_score * 0.3 - weighted_cost * 0.1

        # balanced: quality minus estimated $ cost penalty
        # Calibration: $0.10 ≈ 5 quality points
        # so 8-point quality boost (e.g. Pro vs V3) is worth up to ~$0.16
        quality_value = m.quality_score
        cost_penalty = est_cost * 50
        task_match_bonus = 5 if task in m.tasks else 0
        return quality_value - cost_penalty + task_match_bonus

    candidates.sort(key=score, reverse=True)
    return candidates[0]


# ── Provider invocation ─────────────────────────────────────────────────

def _build_summary_prompt(transcript: str) -> str:
    return f"""You are an expert analyst helping Emerging Markets Portfolio Managers extract actionable insights from podcasts.

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

Focus on: regional views (LatAm, EMEA, Asia, China), asset class opinions (rates, credit, FX, equities), macro themes, risk factors, VWOB/EMB ETF-relevant sovereign spread dynamics, and investment opportunities discussed.
Always respond with valid JSON only."""


def _parse_json_response(text: str) -> Dict[str, Any]:
    """Strip markdown code fences and parse JSON."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def _fallback(reason: str) -> Dict[str, Any]:
    return {
        "podcast_summary": f"Summarization failed: {reason[:200]}",
        "podcast_guest": "N/A",
        "podcast_guest_title": "",
        "podcast_guest_org": "",
        "podcast_highlights": "",
        "podcast_details": "",
        "_is_fallback": True,
    }


def _call_gemini(model: ModelSpec, prompt: str) -> Dict[str, Any]:
    api_key = _provider_key("gemini")
    if not api_key or not _GEMINI_OK:
        raise RuntimeError("Gemini SDK or API key not available")
    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(model.model_id)
    resp = m.generate_content(prompt, generation_config={"temperature": 0.3})
    return _parse_json_response(resp.text)


def _call_anthropic(model: ModelSpec, prompt: str) -> Dict[str, Any]:
    api_key = _provider_key("anthropic")
    if not api_key or not _ANTHROPIC_OK:
        raise RuntimeError("Anthropic SDK or API key not available")
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model.model_id,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json_response(msg.content[0].text)


def _call_openai_like(
    model: ModelSpec, prompt: str, base_url: Optional[str] = None
) -> Dict[str, Any]:
    """Used for both OpenAI and DeepSeek (which uses OpenAI-compatible API)."""
    api_key = _provider_key(model.provider)
    if not api_key or not _OPENAI_OK:
        raise RuntimeError(f"{model.provider} SDK or API key not available")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAIClient(**kwargs)
    resp = client.chat.completions.create(
        model=model.model_id,
        messages=[
            {"role": "system",
             "content": "You are a financial analyst specializing in Emerging Markets. Always respond with valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=4000,
        # JSON mode where supported (OpenAI). DeepSeek mostly respects too.
        response_format={"type": "json_object"} if "deepseek" not in model.provider else None,  # type: ignore
    )
    text = resp.choices[0].message.content or "{}"
    return _parse_json_response(text)


def _invoke(model: ModelSpec, prompt: str) -> Dict[str, Any]:
    """Dispatch to the right provider client."""
    if model.provider == "gemini":
        return _call_gemini(model, prompt)
    if model.provider == "anthropic":
        return _call_anthropic(model, prompt)
    if model.provider == "openai":
        return _call_openai_like(model, prompt)
    if model.provider == "deepseek":
        return _call_openai_like(model, prompt, base_url="https://api.deepseek.com")
    raise ValueError(f"Unknown provider: {model.provider}")


# ── Public entry point ─────────────────────────────────────────────────

def generate_summary(
    transcript: str,
    task: str = "summary",
    priority: str = "balanced",
    max_attempts: int = 3,
) -> Dict[str, Any]:
    """
    Pick the best model and generate an EM podcast summary.

    Falls back through up to max_attempts models on failure.
    Returns dict with summary fields + metadata:
      - _model_used: model_id of the model that succeeded
      - _model_label: human-readable name
      - _estimated_cost: rough USD estimate
      - _routing_priority: priority used
    """
    # Cap transcript length defensively (router still considers full length)
    if len(transcript) > 800_000:
        transcript = transcript[:800_000] + "... [truncated]"

    prompt = _build_summary_prompt(transcript)
    excluded: Set[str] = set()
    last_err = ""

    for attempt in range(max_attempts):
        model = select_model(
            task=task,
            transcript_chars=len(transcript),
            priority=priority,
            exclude=excluded,
        )
        if model is None:
            return _fallback(
                last_err or "No suitable model available — check API keys"
            )

        try:
            result = _invoke(model, prompt)
            result["_model_used"] = model.model_id
            result["_model_label"] = model.name
            result["_estimated_cost"] = round(
                estimate_cost(model, len(transcript)), 4
            )
            result["_routing_priority"] = priority
            return result
        except json.JSONDecodeError as e:
            last_err = f"{model.name}: invalid JSON response"
            excluded.add(model.model_id)
        except Exception as e:
            last_err = f"{model.name}: {str(e)[:150]}"
            excluded.add(model.model_id)

    return _fallback(last_err)


# ── Q&A entry point ─────────────────────────────────────────────────────

def chat_with_transcript(
    transcript: str,
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
    priority: str = "balanced",
) -> Tuple[str, Optional[ModelSpec]]:
    """
    Answer a question grounded in a podcast transcript.

    Returns (answer_text, model_used). If no model is available,
    returns an explanatory error string and None.
    """
    history = history or []
    model = select_model(
        task="qa", transcript_chars=len(transcript), priority=priority
    )
    if model is None:
        return ("No AI provider available. Set one of OPENAI_API_KEY, "
                "ANTHROPIC_API_KEY, GEMINI_API_KEY, or DEEPSEEK_API_KEY."), None

    system = (
        "You are an EM (Emerging Markets) Portfolio Manager research assistant. "
        "Answer questions strictly using the provided podcast transcript. "
        "If the transcript doesn't cover a question, say so. Be concise but "
        "specific. Quote short passages from the transcript when relevant."
    )

    # Cap transcript by model context (rough chars/token = 4)
    max_chars = max(20_000, model.context_window * 3 - 5_000)
    transcript = transcript[:max_chars]

    try:
        if model.provider == "gemini":
            api_key = _provider_key("gemini")
            genai.configure(api_key=api_key)
            m = genai.GenerativeModel(model.model_id, system_instruction=system)
            convo = m.start_chat(history=[
                {"role": "user", "parts": [f"<transcript>\n{transcript}\n</transcript>"]},
                {"role": "model", "parts": ["Got it — ask me anything about this transcript."]},
                *[{"role": ("user" if h["role"] == "user" else "model"),
                    "parts": [h["content"]]} for h in history[-6:]],
            ])
            resp = convo.send_message(question)
            return (resp.text, model)

        if model.provider == "anthropic":
            api_key = _provider_key("anthropic")
            client = anthropic.Anthropic(api_key=api_key)
            messages = [
                {"role": "user", "content": f"<transcript>\n{transcript}\n</transcript>"},
                {"role": "assistant", "content": "Got it — ask away."},
            ]
            for turn in history[-6:]:
                messages.append({"role": turn["role"], "content": turn["content"]})
            messages.append({"role": "user", "content": question})
            resp = client.messages.create(
                model=model.model_id,
                max_tokens=1024,
                system=system,
                messages=messages,
            )
            return (resp.content[0].text if resp.content else "(empty)", model)

        # OpenAI / DeepSeek (compatible APIs)
        api_key = _provider_key(model.provider)
        kwargs = {"api_key": api_key}
        if model.provider == "deepseek":
            kwargs["base_url"] = "https://api.deepseek.com"
        client = OpenAIClient(**kwargs)
        msgs = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Podcast transcript:\n\n{transcript}"},
        ]
        for turn in history[-6:]:
            msgs.append({"role": turn["role"], "content": turn["content"]})
        msgs.append({"role": "user", "content": question})
        resp = client.chat.completions.create(
            model=model.model_id,
            messages=msgs,
            max_tokens=800,
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "(empty)", model)

    except Exception as e:
        return (f"{model.name} error: {e}", model)


def list_available_models(priority: str = "balanced") -> List[Dict[str, Any]]:
    """Return models sorted by score (for UI display)."""
    avail = available_providers()
    rows: List[Dict[str, Any]] = []
    for m in MODELS:
        rows.append({
            "name": m.name,
            "provider": m.provider,
            "available": m.provider in avail,
            "tier": m.tier,
            "context": m.context_window,
            "cost_in": m.cost_in,
            "cost_out": m.cost_out,
            "speed": m.speed,
            "tasks": ", ".join(m.tasks),
        })
    return rows
