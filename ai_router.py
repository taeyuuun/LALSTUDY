"""Provider router for LALSTUDY AI calls.

The selected provider is explicit: Gemini stays Gemini, OpenAI stays OpenAI.
There is no silent cross-provider fallback.
"""

from __future__ import annotations

import base64
import json
import random
import time
from datetime import datetime, timezone
from typing import List, Optional, Type

from pydantic import BaseModel

import ai_engine as gemini_engine

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


OPENAI_TEXT_MODELS = [
    x.strip()
    for x in __import__("os").getenv(
        "LALSTUDY_OPENAI_TEXT_MODELS",
        "gpt-5.6-luna,gpt-5.6-terra",
    ).split(",")
    if x.strip()
]

OPENAI_FIGURE_MODELS = gemini_engine.OPENAI_FIGURE_MODELS


# Re-export the exception so existing page-level error handling still works.
StageCallError = gemini_engine.StageCallError


def provider_sdk_available(provider: str) -> bool:
    provider = (provider or "gemini").lower()
    if provider == "openai":
        return OpenAI is not None
    return gemini_engine.sdk_available()


def get_text_models(provider: str) -> List[str]:
    return OPENAI_TEXT_MODELS if provider == "openai" else gemini_engine.TEXT_MODELS


def get_figure_models(provider: str) -> List[str]:
    return OPENAI_FIGURE_MODELS if provider == "openai" else gemini_engine.FIGURE_MODELS


def _record_usage(provider: str, model: str, stage: str, usage) -> None:
    """Best-effort Streamlit session usage tracking for the sidebar fallback."""
    try:
        import streamlit as st
    except Exception:
        return

    if usage is None:
        return

    def val(name: str) -> int:
        if isinstance(usage, dict):
            return int(usage.get(name, 0) or 0)
        return int(getattr(usage, name, 0) or 0)

    input_tokens = val("input_tokens")
    output_tokens = val("output_tokens")
    total_tokens = val("total_tokens") or input_tokens + output_tokens
    day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        root = st.session_state.get("lal_ai_usage_daily_v1", {}) or {}
        day = root.get(day_key, {}) or {}
        bucket = day.get(provider, {}) or {}
        bucket["input_tokens"] = int(bucket.get("input_tokens", 0) or 0) + input_tokens
        bucket["output_tokens"] = int(bucket.get("output_tokens", 0) or 0) + output_tokens
        bucket["total_tokens"] = int(bucket.get("total_tokens", 0) or 0) + total_tokens
        bucket["calls"] = int(bucket.get("calls", 0) or 0) + 1
        bucket.setdefault("models", {})
        bucket["models"][model] = int(bucket["models"].get(model, 0) or 0) + 1
        bucket.setdefault("stages", {})
        bucket["stages"][stage] = int(bucket["stages"].get(stage, 0) or 0) + 1
        day[provider] = bucket
        root[day_key] = day
        st.session_state["lal_ai_usage_daily_v1"] = root
    except Exception:
        pass


def _is_transient(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in [
            "429",
            "rate limit",
            "500",
            "502",
            "503",
            "504",
            "temporarily",
            "timeout",
            "internal",
            "unavailable",
        ]
    )


def _is_model_unavailable(exc: Exception) -> bool:
    text = str(exc).lower()
    return "404" in text or "not_found" in text or ("model" in text and "not available" in text)


def _openai_parse(
    *,
    api_key: str,
    stage: str,
    prompt: str,
    schema: Type[BaseModel],
    model_pool: List[str],
    image_bytes: Optional[bytes] = None,
    image_mime_type: str = "image/png",
    pdf_bytes: Optional[bytes] = None,
):
    if OpenAI is None:
        raise RuntimeError("openai is not installed.")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")
    if image_bytes is not None and pdf_bytes is not None:
        raise ValueError("Provide image_bytes or pdf_bytes, not both.")

    client = OpenAI(api_key=api_key)

    if image_bytes is not None:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        user_input = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:{image_mime_type};base64,{encoded}",
                        "detail": "high",
                    },
                ],
            }
        ]
    elif pdf_bytes is not None:
        encoded = base64.b64encode(pdf_bytes).decode("ascii")
        user_input = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": "paper.pdf",
                        "file_data": f"data:application/pdf;base64,{encoded}",
                    },
                    {"type": "input_text", "text": prompt},
                ],
            }
        ]
    else:
        user_input = prompt

    errors = []
    for model_name in model_pool:
        for attempt in range(2):
            try:
                response = client.responses.parse(
                    model=model_name,
                    input=user_input,
                    text_format=schema,
                )
                parsed = getattr(response, "output_parsed", None)
                if parsed is None:
                    raise RuntimeError(f"{model_name} returned no structured output.")
                result = parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
                usage = getattr(response, "usage", None)
                _record_usage("openai", model_name, stage, usage)
                return result, model_name
            except Exception as exc:
                errors.append(f"OpenAI {model_name} attempt {attempt + 1}: {exc}")
                if _is_model_unavailable(exc):
                    break
                if not _is_transient(exc):
                    break
                if attempt == 0:
                    time.sleep(1.0 + random.uniform(0.0, 0.5))

    raise StageCallError(stage=stage, trace=errors)


def _core_context(core_bundle: dict) -> str:
    if not core_bundle:
        return "{}"
    source = core_bundle.get("en", core_bundle)
    return json.dumps(source, ensure_ascii=False, indent=2)[:30_000]


def analyze_core(*, paper_text: str, api_key: str, depth: str, detected_methods: List[str], provider: str = "gemini"):
    if provider != "openai":
        return gemini_engine.analyze_core(
            paper_text=paper_text,
            api_key=api_key,
            depth=depth,
            detected_methods=detected_methods,
        )

    prompt = f"""
You are LALSTUDY's Stage 1 scientific-reading engine.

{gemini_engine.LANGUAGE_RULE}
{gemini_engine.GROUNDING_RULE}

Learner level:
{gemini_engine.DEPTH_INSTRUCTIONS.get(depth, gemini_engine.DEPTH_INSTRUCTIONS["undergraduate"])}

Possible methods detected by a separate rule-based system:
{", ".join(detected_methods[:25]) if detected_methods else "none"}
Use them only as hints.

TASK
Create ONLY:
1. Paper overview
2. A concise logic map of the major argument

Keep the logic map to roughly 5-10 major steps.
Do NOT generate detailed prerequisite lessons, exhaustive experiment cards,
Figure panel analysis, or reviewer critique yet.

For the logic map, emphasize:
Question → experiment/analysis → direct observation → inference → next question.

PAPER TEXT
==========
{gemini_engine.compact_text(paper_text, 135_000)}
"""
    return _openai_parse(
        api_key=api_key,
        stage="core",
        prompt=prompt,
        schema=gemini_engine.BilingualCore,
        model_pool=OPENAI_TEXT_MODELS,
    )


def analyze_prerequisites(*, paper_text: str, core_bundle: dict, api_key: str, depth: str, provider: str = "gemini"):
    if provider != "openai":
        return gemini_engine.analyze_prerequisites(
            paper_text=paper_text,
            core_bundle=core_bundle,
            api_key=api_key,
            depth=depth,
        )

    prompt = f"""
You are LALSTUDY's prerequisite-learning module.

{gemini_engine.LANGUAGE_RULE}
{gemini_engine.GROUNDING_RULE}

Learner level:
{gemini_engine.DEPTH_INSTRUCTIONS.get(depth, gemini_engine.DEPTH_INSTRUCTIONS["undergraduate"])}

CORE ANALYSIS
=============
{_core_context(core_bundle)}

TASK
Identify approximately 6-12 prerequisite concepts that would most reduce the
reader's difficulty understanding THIS paper.

For each concept:
- why it is needed for this paper,
- a standalone scientific explanation,
- how it appears in this paper,
- what should be learned first.

Do not create a generic glossary. Prefer concepts that are central to the paper's
mechanism, model system, or analysis.

PAPER TEXT
==========
{gemini_engine.compact_text(paper_text, 100_000)}
"""
    return _openai_parse(
        api_key=api_key,
        stage="prerequisites",
        prompt=prompt,
        schema=gemini_engine.BilingualPrerequisites,
        model_pool=OPENAI_TEXT_MODELS,
    )


def analyze_experiments(*, paper_text: str, core_bundle: dict, api_key: str, detected_methods: List[str], provider: str = "gemini"):
    if provider != "openai":
        return gemini_engine.analyze_experiments(
            paper_text=paper_text,
            core_bundle=core_bundle,
            api_key=api_key,
            detected_methods=detected_methods,
        )

    prompt = f"""
You are LALSTUDY's experimental-strategy module.

{gemini_engine.LANGUAGE_RULE}
{gemini_engine.GROUNDING_RULE}

CORE ANALYSIS
=============
{_core_context(core_bundle)}

Ontology hints:
{", ".join(detected_methods[:30]) if detected_methods else "none"}

TASK
Select the paper's major experiments / analyses, not every procedural detail.
For each, explain:
- scientific question
- sample/model
- manipulated variable or comparison
- readout
- WHY this method answers the question
- what the result supports
- key limitation
- evidence location

Aim for roughly 5-12 high-value experiment cards.
Use conventional English method names whenever possible.

PAPER TEXT
==========
{gemini_engine.compact_text(paper_text, 125_000)}
"""
    return _openai_parse(
        api_key=api_key,
        stage="experiments",
        prompt=prompt,
        schema=gemini_engine.BilingualExperiments,
        model_pool=OPENAI_TEXT_MODELS,
    )


def analyze_figures(*, pdf_bytes: bytes, core_bundle: dict, api_key: str, provider: str = "gemini"):
    if provider != "openai":
        return gemini_engine.analyze_figures(
            pdf_bytes=pdf_bytes,
            core_bundle=core_bundle,
            api_key=api_key,
        )

    prompt = f"""
You are LALSTUDY's Figure-reading module.

{gemini_engine.LANGUAGE_RULE}
{gemini_engine.GROUNDING_RULE}

CORE ANALYSIS
=============
{_core_context(core_bundle)}

TASK
Inspect the uploaded PDF and reconstruct the MAIN scientific Figures.
Do not analyze supplementary Figures unless essential.
For each Figure explain its role, main question, panel-level observation and
interpretation where readable, methods, overall takeaway, what it supports,
and what it does not establish. Do not invent unreadable labels or values.
"""
    return _openai_parse(
        api_key=api_key,
        stage="figures",
        prompt=prompt,
        schema=gemini_engine.BilingualFigures,
        model_pool=OPENAI_FIGURE_MODELS,
        pdf_bytes=pdf_bytes,
    )


def analyze_single_figure(
    *,
    figure_label: str,
    legend: str,
    image_bytes: bytes,
    image_mime_type: str,
    core_bundle: dict,
    api_key: str,
    provider: str = "openai",
):
    """Analyze exactly one Figure with exactly the provider the user selected."""
    if provider == "openai":
        # Reuse the mature v0.3.3 per-Figure implementation, but pass no Gemini
        # key so there is no silent cross-provider fallback.
        result, model, _provider_label, usage = gemini_engine.analyze_single_figure(
            figure_label=figure_label,
            legend=legend,
            image_bytes=image_bytes,
            image_mime_type=image_mime_type,
            core_bundle=core_bundle,
            openai_api_key=api_key,
            gemini_api_key="",
        )
        _record_usage("openai", model, f"single_figure:{figure_label}", usage)
        return result, model, "OpenAI", usage

    result, model, _provider_label, usage = gemini_engine.analyze_single_figure(
        figure_label=figure_label,
        legend=legend,
        image_bytes=image_bytes,
        image_mime_type=image_mime_type,
        core_bundle=core_bundle,
        openai_api_key="",
        gemini_api_key=api_key,
    )
    return result, model, "Gemini", usage


def analyze_critical_learning(*, paper_text: str, core_bundle: dict, experiments_bundle: Optional[dict], api_key: str, depth: str, provider: str = "gemini"):
    if provider != "openai":
        return gemini_engine.analyze_critical_learning(
            paper_text=paper_text,
            core_bundle=core_bundle,
            experiments_bundle=experiments_bundle,
            api_key=api_key,
            depth=depth,
        )

    exp_context = json.dumps(
        (experiments_bundle.get("en", experiments_bundle) if experiments_bundle else {}),
        ensure_ascii=False,
        indent=2,
    )[:25_000]

    prompt = f"""
You are LALSTUDY's critical-reading and learning-planning module.

{gemini_engine.LANGUAGE_RULE}
{gemini_engine.GROUNDING_RULE}

Learner level:
{gemini_engine.DEPTH_INSTRUCTIONS.get(depth, gemini_engine.DEPTH_INSTRUCTIONS["undergraduate"])}

CORE ANALYSIS
=============
{_core_context(core_bundle)}

EXPERIMENT ANALYSIS IF AVAILABLE
================================
{exp_context}

TASK A — Critical reading
Identify the strongest evidence, weakest inferential link, plausible alternative
explanations, one informative missing control/experiment, author-stated
limitations, and reviewer-style questions.

TASK B — Learning path
Create a short ordered plan for what the reader should learn/review next.

PAPER TEXT
==========
{gemini_engine.compact_text(paper_text, 105_000)}
"""
    return _openai_parse(
        api_key=api_key,
        stage="critical_learning",
        prompt=prompt,
        schema=gemini_engine.BilingualCriticalLearning,
        model_pool=OPENAI_TEXT_MODELS,
    )


def explain_concepts_batch(*, concepts: List[str], api_key: str, depth: str = "undergraduate", paper_context: str = "", provider: str = "gemini"):
    if provider != "openai":
        return gemini_engine.explain_concepts_batch(
            concepts=concepts,
            api_key=api_key,
            depth=depth,
            paper_context=paper_context,
        )

    cleaned = []
    seen = set()
    for value in concepts:
        value = (value or "").strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value[:160])

    if not cleaned:
        raise ValueError("No concepts were supplied.")
    if len(cleaned) > 8:
        raise ValueError("A maximum of 8 concepts can be explained in one batch.")

    context = (paper_context or "").strip()[:8000]
    prompt = f"""
You are building LALSTUDY's reusable scientific Knowledge Archive.

Selected concepts/phrases:
{json.dumps(cleaned, ensure_ascii=False)}

Reader level:
{gemini_engine.DEPTH_INSTRUCTIONS.get(depth, gemini_engine.DEPTH_INSTRUCTIONS["undergraduate"])}

Paper context is only for disambiguation. Never archive paper-specific findings.
PAPER CONTEXT
=============
{context or "none"}

For every requested term create a compact reusable card with requested_term,
canonical_name, true aliases, Korean/English definition, mechanism, why it
matters, prerequisites, and difficulty. Korean should use English-first
scientific terminology. The card must be reusable for a different paper/user.
"""
    return _openai_parse(
        api_key=api_key,
        stage="knowledge_archive_fill",
        prompt=prompt,
        schema=gemini_engine.ConceptBatchAnalysis,
        model_pool=OPENAI_TEXT_MODELS,
    )
