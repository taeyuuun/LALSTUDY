"""OpenAI-only AI engine for LALSTUDY."""

from __future__ import annotations

import base64
import json
import random
import time
from datetime import datetime, timezone
from typing import List, Optional, Type

from pydantic import BaseModel

import ai_engine as engine

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

StageCallError = engine.StageCallError


def openai_sdk_available() -> bool:
    return OpenAI is not None


def get_text_models() -> List[str]:
    return list(engine.OPENAI_TEXT_MODELS)


def get_figure_models() -> List[str]:
    return list(engine.OPENAI_FIGURE_MODELS)


def _record_usage(model: str, stage: str, usage) -> dict:
    def val(name: str) -> int:
        if usage is None:
            return 0
        if isinstance(usage, dict):
            return int(usage.get(name, 0) or 0)
        return int(getattr(usage, name, 0) or 0)

    input_tokens = val("input_tokens")
    output_tokens = val("output_tokens")
    total_tokens = val("total_tokens") or input_tokens + output_tokens

    usage_dict = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }

    try:
        import streamlit as st

        day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        root = st.session_state.get("lal_ai_usage_daily_v1", {}) or {}
        day = root.get(day_key, {}) or {}
        bucket = day.get("openai", {}) or {}
        bucket["input_tokens"] = int(bucket.get("input_tokens", 0) or 0) + input_tokens
        bucket["output_tokens"] = int(bucket.get("output_tokens", 0) or 0) + output_tokens
        bucket["total_tokens"] = int(bucket.get("total_tokens", 0) or 0) + total_tokens
        bucket["calls"] = int(bucket.get("calls", 0) or 0) + 1
        bucket.setdefault("models", {})
        bucket["models"][model] = int(bucket["models"].get(model, 0) or 0) + 1
        bucket.setdefault("stages", {})
        bucket["stages"][stage] = int(bucket["stages"].get(stage, 0) or 0) + 1
        day["openai"] = bucket
        root[day_key] = day
        st.session_state["lal_ai_usage_daily_v1"] = root
    except Exception:
        pass

    return usage_dict


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
    return (
        "404" in text
        or "not_found" in text
        or ("model" in text and "not available" in text)
    )


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
                usage_dict = _record_usage(
                    model_name,
                    stage,
                    getattr(response, "usage", None),
                )
                return result, model_name, usage_dict

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


def analyze_core(*, paper_text: str, api_key: str, depth: str, detected_methods: List[str]):
    prompt = f"""
You are LALSTUDY's Stage 1 scientific-reading engine.

{engine.LANGUAGE_RULE}
{engine.GROUNDING_RULE}

Learner level:
{engine.DEPTH_INSTRUCTIONS.get(depth, engine.DEPTH_INSTRUCTIONS["undergraduate"])}

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
{engine.compact_text(paper_text, 135_000)}
"""
    result, model, _usage = _openai_parse(
        api_key=api_key,
        stage="core",
        prompt=prompt,
        schema=engine.BilingualCore,
        model_pool=engine.OPENAI_TEXT_MODELS,
    )
    return result, model


def analyze_prerequisites(*, paper_text: str, core_bundle: dict, api_key: str, depth: str):
    prompt = f"""
You are LALSTUDY's prerequisite-learning module.

{engine.LANGUAGE_RULE}
{engine.GROUNDING_RULE}

Learner level:
{engine.DEPTH_INSTRUCTIONS.get(depth, engine.DEPTH_INSTRUCTIONS["undergraduate"])}

CORE ANALYSIS
=============
{_core_context(core_bundle)}

TASK
Identify approximately 6-12 prerequisite concepts that would most reduce the
reader's difficulty understanding THIS paper.
For each concept explain why it is needed, the standalone science, how it appears
in this paper, and what should be learned first.

PAPER TEXT
==========
{engine.compact_text(paper_text, 100_000)}
"""
    result, model, _usage = _openai_parse(
        api_key=api_key,
        stage="prerequisites",
        prompt=prompt,
        schema=engine.BilingualPrerequisites,
        model_pool=engine.OPENAI_TEXT_MODELS,
    )
    return result, model


def analyze_experiments(*, paper_text: str, core_bundle: dict, api_key: str, detected_methods: List[str]):
    prompt = f"""
You are LALSTUDY's experimental-strategy module.

{engine.LANGUAGE_RULE}
{engine.GROUNDING_RULE}

CORE ANALYSIS
=============
{_core_context(core_bundle)}

Ontology hints:
{", ".join(detected_methods[:30]) if detected_methods else "none"}

TASK
Select the paper's major experiments / analyses, not every procedural detail.
For each, explain the scientific question, sample/model, manipulation/comparison,
readout, why the method answers the question, what the result supports, key
limitation, and evidence location.

PAPER TEXT
==========
{engine.compact_text(paper_text, 125_000)}
"""
    result, model, _usage = _openai_parse(
        api_key=api_key,
        stage="experiments",
        prompt=prompt,
        schema=engine.BilingualExperiments,
        model_pool=engine.OPENAI_TEXT_MODELS,
    )
    return result, model


def analyze_figures(*, pdf_bytes: bytes, core_bundle: dict, api_key: str):
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise ValueError("Figure analysis currently supports PDFs up to 50 MB.")

    prompt = f"""
You are LALSTUDY's Figure-reading module.

{engine.LANGUAGE_RULE}
{engine.GROUNDING_RULE}

CORE ANALYSIS
=============
{_core_context(core_bundle)}

TASK
Inspect the uploaded PDF and reconstruct the MAIN scientific Figures.
Do not analyze supplementary Figures unless essential. Explain each Figure's role,
main question, panel-level WHAT/HOW/RESULT/INTERPRETATION where readable, methods,
overall takeaway, what it supports, and what it does not establish.
"""
    result, model, _usage = _openai_parse(
        api_key=api_key,
        stage="figures",
        prompt=prompt,
        schema=engine.BilingualFigures,
        model_pool=engine.OPENAI_FIGURE_MODELS,
        pdf_bytes=pdf_bytes,
    )
    return result, model


def analyze_single_figure(
    *,
    figure_label: str,
    legend: str,
    image_bytes: bytes,
    image_mime_type: str,
    core_bundle: dict,
    api_key: str,
):
    if not image_bytes:
        raise ValueError("Figure image is empty.")

    figure_label = (figure_label or "Figure").strip()
    legend = (legend or "").strip()

    prompt = f"""
You are LALSTUDY's single-Figure scientific reading module.

{engine.LANGUAGE_RULE}
{engine.GROUNDING_RULE}

CORE ANALYSIS
=============
{_core_context(core_bundle)}

TARGET FIGURE
=============
Label: {figure_label}

ORIGINAL FIGURE LEGEND
======================
{legend[:18_000] or "No legend was extracted."}

TASK
Analyze ONLY the single Figure image supplied with this request.
The image and its original legend are the primary evidence.
Use the Core Analysis only to understand where this Figure fits in the paper.

Return one FigureAnalysis in Korean and one semantically equivalent English version.
Explain:
- role in the paper's story
- main scientific question
- panel-by-panel WHAT / HOW / RESULT / INTERPRETATION when labels are readable
- methods used in each panel when supported by the image or legend
- overall takeaway
- what this Figure supports
- what it does NOT establish

Do not invent unreadable labels, values, statistics, or methods.
If a panel is ambiguous, state the uncertainty instead of guessing.
Preserve the target label as `{figure_label}`.
"""

    result, model, usage = _openai_parse(
        api_key=api_key,
        stage=f"single_figure:{figure_label}",
        prompt=prompt,
        schema=engine.BilingualSingleFigure,
        model_pool=engine.OPENAI_FIGURE_MODELS,
        image_bytes=image_bytes,
        image_mime_type=image_mime_type,
    )
    return result, model, "OpenAI", usage


def analyze_critical_learning(
    *,
    paper_text: str,
    core_bundle: dict,
    experiments_bundle: Optional[dict],
    api_key: str,
    depth: str,
):
    exp_context = json.dumps(
        (experiments_bundle.get("en", experiments_bundle) if experiments_bundle else {}),
        ensure_ascii=False,
        indent=2,
    )[:25_000]

    prompt = f"""
You are LALSTUDY's critical-reading and learning-planning module.

{engine.LANGUAGE_RULE}
{engine.GROUNDING_RULE}

Learner level:
{engine.DEPTH_INSTRUCTIONS.get(depth, engine.DEPTH_INSTRUCTIONS["undergraduate"])}

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
{engine.compact_text(paper_text, 105_000)}
"""
    result, model, _usage = _openai_parse(
        api_key=api_key,
        stage="critical_learning",
        prompt=prompt,
        schema=engine.BilingualCriticalLearning,
        model_pool=engine.OPENAI_TEXT_MODELS,
    )
    return result, model


def explain_concepts_batch(
    *,
    concepts: List[str],
    api_key: str,
    depth: str = "undergraduate",
    paper_context: str = "",
):
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
{engine.DEPTH_INSTRUCTIONS.get(depth, engine.DEPTH_INSTRUCTIONS["undergraduate"])}

Paper context is ONLY for disambiguation. Never archive paper-specific findings.
PAPER CONTEXT
=============
{context or "none"}

For every requested term create a compact reusable card with requested_term,
canonical_name, true aliases, Korean/English definition, mechanism, why it
matters, prerequisites, and difficulty. Korean should use English-first
scientific terminology. The card must be reusable for a different paper/user.
"""
    result, model, _usage = _openai_parse(
        api_key=api_key,
        stage="knowledge_archive_fill",
        prompt=prompt,
        schema=engine.ConceptBatchAnalysis,
        model_pool=engine.OPENAI_TEXT_MODELS,
    )
    return result, model


def generate_method_encyclopedia_entry(
    *,
    canonical_name: str,
    aliases: List[str],
    category: str,
    parent_method: str,
    submethods: List[str],
    api_key: str,
):
    """
    Generate a concise reusable encyclopedia entry for an experimental method.
    This content is method-level knowledge, never paper-specific.
    """
    prompt = f"""
You are writing one compact entry for LALSTUDY's experimental-method encyclopedia.

METHOD
======
Canonical name: {canonical_name}
Known aliases: {json.dumps(aliases[:20], ensure_ascii=False)}
Existing ontology category: {category or "unknown"}
Parent method: {parent_method or "none"}
Known submethods: {json.dumps(submethods[:20], ensure_ascii=False)}

TASK
====
Write ONLY the reusable scientific essentials of this method.

Return:
1. summary — what the method is and what question it answers
2. principle — the core experimental principle, not a protocol
3. best_for — when a researcher would choose this method
4. limitations — the most important interpretation caveats

Rules:
- Be concise. This is a wiki card, not a textbook chapter.
- Do not invent a protocol, concentrations, timings, kits, or paper-specific findings.
- Preserve conventional English assay names and technical terms.
- Korean should be natural but English-first for established scientific terminology.
- Korean and English must be semantically equivalent.
- Mention important distinctions only when they prevent a common misunderstanding
  (for example FACS vs flow cytometry, qPCR vs endpoint PCR).
"""
    result, model, usage = _openai_parse(
        api_key=api_key,
        stage="method_encyclopedia_fill",
        prompt=prompt,
        schema=engine.MethodEncyclopediaEntry,
        model_pool=engine.OPENAI_TEXT_MODELS,
    )
    return result, model, usage
