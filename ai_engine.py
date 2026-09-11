import base64
import json
import os
import random
import time
from typing import List, Literal, Optional, Type

from pydantic import BaseModel, Field

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# Current stable fallback pools.
TEXT_MODELS = [
    x.strip()
    for x in os.getenv(
        "LALSTUDY_TEXT_MODELS",
        "gemini-3.8-flash,gemini-3.5-flash,gemini-3.5-flash-lite",
    ).split(",")
    if x.strip()
]

FIGURE_MODELS = [
    x.strip()
    for x in os.getenv(
        "LALSTUDY_FIGURE_MODELS",
        "gemini-3.8-flash,gemini-3.5-flash",
    ).split(",")
    if x.strip()
]

OPENAI_FIGURE_MODELS = [
    x.strip()
    for x in os.getenv(
        "LALSTUDY_OPENAI_FIGURE_MODELS",
        "gpt-5.6-luna,gpt-5.6-terra",
    ).split(",")
    if x.strip()
]


# ============================================================
# SCHEMAS
# ============================================================

class LogicStep(BaseModel):
    order: int
    question: str
    experiment_or_analysis: str
    observation: str
    inference: str
    evidence_location: str


class PaperOverview(BaseModel):
    title: str
    field: str
    one_sentence_takeaway: str
    research_question: str
    why_it_matters: str
    knowledge_gap: str
    hypothesis: str
    novelty: str
    conclusion: str


class CoreAnalysis(BaseModel):
    overview: PaperOverview
    logic_map: List[LogicStep] = Field(default_factory=list)


class PrerequisiteConcept(BaseModel):
    name: str
    difficulty: Literal["basic", "intermediate", "advanced"]
    why_needed: str
    explanation: str
    paper_context: str
    prerequisites: List[str] = Field(default_factory=list)


class PrerequisiteAnalysis(BaseModel):
    prerequisites: List[PrerequisiteConcept] = Field(default_factory=list)


class ExperimentAnalysis(BaseModel):
    method: str
    scientific_question: str
    sample_or_model: str
    manipulated_variable: str
    readout: str
    why_this_method: str
    result_meaning: str
    limitation: str
    evidence_location: str


class ExperimentsAnalysis(BaseModel):
    experiments: List[ExperimentAnalysis] = Field(default_factory=list)


class PanelAnalysis(BaseModel):
    panel_label: str
    what: str
    how: str
    result: str
    interpretation: str
    methods: List[str] = Field(default_factory=list)


class FigureAnalysis(BaseModel):
    figure_label: str
    role_in_story: str
    main_question: str
    panels: List[PanelAnalysis] = Field(default_factory=list)
    overall_takeaway: str
    what_it_proves: str
    what_it_does_not_prove: str


class FiguresAnalysis(BaseModel):
    figures: List[FigureAnalysis] = Field(default_factory=list)


class CriticalReading(BaseModel):
    strongest_evidence: str
    weakest_link: str
    alternative_explanations: List[str] = Field(default_factory=list)
    missing_control_or_experiment: str
    author_stated_limitations: List[str] = Field(default_factory=list)
    reviewer_questions: List[str] = Field(default_factory=list)


class LearningItem(BaseModel):
    order: int
    topic: str
    why_now: str
    action: str


class CriticalLearningAnalysis(BaseModel):
    critical_reading: CriticalReading
    learning_path: List[LearningItem] = Field(default_factory=list)


class BilingualCore(BaseModel):
    ko: CoreAnalysis
    en: CoreAnalysis


class BilingualPrerequisites(BaseModel):
    ko: PrerequisiteAnalysis
    en: PrerequisiteAnalysis


class BilingualExperiments(BaseModel):
    ko: ExperimentsAnalysis
    en: ExperimentsAnalysis


class BilingualFigures(BaseModel):
    ko: FiguresAnalysis
    en: FiguresAnalysis


class BilingualSingleFigure(BaseModel):
    ko: FigureAnalysis
    en: FigureAnalysis


class BilingualCriticalLearning(BaseModel):
    ko: CriticalLearningAnalysis
    en: CriticalLearningAnalysis



class ConceptExplanation(BaseModel):
    requested_term: str
    canonical_name: str
    aliases: List[str] = Field(default_factory=list)

    definition_ko: str
    definition_en: str

    mechanism_ko: str
    mechanism_en: str

    why_it_matters_ko: str
    why_it_matters_en: str

    prerequisites: List[str] = Field(default_factory=list)

    difficulty: Literal[
        "basic",
        "intermediate",
        "advanced",
    ] = "intermediate"


class ConceptBatchAnalysis(BaseModel):
    concepts: List[
        ConceptExplanation
    ] = Field(default_factory=list)


# ============================================================
# PROMPT HELPERS
# ============================================================

DEPTH_INSTRUCTIONS = {
    "foundation": (
        "The learner is new to the field. Explain foundational biology before "
        "advanced mechanisms and do not assume experimental-design familiarity."
    ),
    "undergraduate": (
        "The learner is a life-science undergraduate. Assume general molecular "
        "and cell biology, but explain field-specific mechanisms, omics, and "
        "experimental logic."
    ),
    "advanced": (
        "The learner is an advanced undergraduate or graduate reader. Keep basic "
        "background concise and emphasize mechanism, causal inference, controls, "
        "statistics, and limitations."
    ),
}


LANGUAGE_RULE = r"""
Return TWO semantically equivalent versions: `ko` and `en`.

`en`: clear scientific English.

`ko`: natural Korean explanatory prose, BUT use English-first life-science
terminology. Keep conventional technical nouns in English whenever researchers
commonly use them in English. Prefer:
- lysosome의 acidification
- autophagy flux
- Flow cytometry로 Treg population을 분석
- STAT5 phosphorylation
- single-cell RNA sequencing
- gene/protein symbols exactly as written

Avoid unnecessary Hangul transliterations such as 리소좀, 엔도좀, 오토파지,
and avoid translating conventional assay names.

The Korean and English versions must contain the SAME scientific interpretation.
"""


GROUNDING_RULE = r"""
GROUNDING RULES
1. Claims about this study must come from the provided paper content.
2. General background knowledge is allowed only where the task explicitly asks
   for teaching/background.
3. Never invent sample sizes, statistics, panels, experiments, mechanisms, or results.
4. Separate direct observation from interpretation.
5. If evidence is unclear, say so.
6. Association is not causation.
7. Preserve conventional English method names for LALSTUDY ontology linking.
"""


def sdk_available():
    return genai is not None and types is not None


def openai_sdk_available():
    return OpenAI is not None


def compact_text(text: str, max_chars: int = 150_000) -> str:
    """
    Reduce unnecessary payload while keeping both beginning and later Results /
    Discussion content. References are removed when a clear heading is found.
    """
    text = (text or "").strip()

    ref_match = re_search_references(text)
    if ref_match is not None:
        text = text[:ref_match]

    if len(text) <= max_chars:
        return text

    head = int(max_chars * 0.68)
    tail = max_chars - head

    return (
        text[:head]
        + "\n\n[... middle of paper omitted for request size ...]\n\n"
        + text[-tail:]
    )


def re_search_references(text: str):
    import re

    matches = list(
        re.finditer(
            r"(?im)^\s*(references|bibliography)\s*$",
            text,
        )
    )

    if not matches:
        return None

    # Prefer a late References heading, avoiding inline mentions.
    late = [
        m.start()
        for m in matches
        if m.start() > len(text) * 0.55
    ]

    return late[0] if late else None


def _is_transient(exc: Exception) -> bool:
    s = str(exc).lower()

    return any(
        marker in s
        for marker in [
            "429",
            "resource_exhausted",
            "rate limit",
            "500",
            "502",
            "503",
            "504",
            "unavailable",
            "high demand",
            "temporarily",
            "timeout",
            "deadline",
            "internal",
            "bad gateway",
            "gateway timeout",
        ]
    )


def _is_model_unavailable(exc: Exception) -> bool:
    s = str(exc).lower()

    return (
        "404" in s
        or "not_found" in s
        or (
            "model" in s
            and "not available" in s
        )
    )


class StageCallError(RuntimeError):
    def __init__(self, stage: str, trace: List[str]):
        self.stage = stage
        self.trace = trace

        super().__init__(
            f"{stage} analysis could not be completed after retry/fallback."
        )


def _call_structured(
    *,
    api_key: str,
    stage: str,
    prompt: str,
    schema: Type[BaseModel],
    model_pool: List[str],
    pdf_bytes: Optional[bytes] = None,
    image_bytes: Optional[bytes] = None,
    image_mime_type: str = "image/png",
    thinking_level: str = "low",
):
    if not sdk_available():
        raise RuntimeError("google-genai is not installed.")

    if not api_key:
        raise ValueError("Server GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)

    if pdf_bytes is not None and image_bytes is not None:
        raise ValueError("Provide either pdf_bytes or image_bytes, not both.")

    if pdf_bytes is not None:
        contents = [
            types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf",
            ),
            prompt,
        ]
    elif image_bytes is not None:
        contents = [
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=image_mime_type,
            ),
            prompt,
        ]
    else:
        contents = prompt

    errors = []

    # Two tries per model: enough for transient spikes without making the user
    # wait through a long wall of retries.
    for model_name in model_pool:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                        response_schema=schema,
                        thinking_config=types.ThinkingConfig(
                            thinking_level=thinking_level
                        ),
                    ),
                )

                parsed = getattr(
                    response,
                    "parsed",
                    None,
                )

                if parsed is not None:
                    if isinstance(parsed, schema):
                        return parsed, model_name

                    return (
                        schema.model_validate(parsed),
                        model_name,
                    )

                body = getattr(
                    response,
                    "text",
                    None,
                )

                if not body:
                    raise RuntimeError(
                        f"{model_name} returned no text."
                    )

                return (
                    schema.model_validate_json(body),
                    model_name,
                )

            except Exception as exc:
                errors.append(
                    f"{model_name} attempt {attempt + 1}: {exc}"
                )

                if _is_model_unavailable(exc):
                    break

                if not _is_transient(exc):
                    break

                if attempt == 0:
                    time.sleep(
                        1.2
                        + random.uniform(0.0, 0.6)
                    )

    raise StageCallError(
        stage=stage,
        trace=errors,
    )



def _call_openai_figure_structured(
    *,
    api_key: str,
    stage: str,
    prompt: str,
    image_bytes: bytes,
    image_mime_type: str,
    schema: Type[BaseModel],
    model_pool: List[str],
):
    if not openai_sdk_available():
        raise RuntimeError("openai is not installed.")

    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=api_key)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{image_mime_type};base64,{encoded}"

    errors = []

    for model_name in model_pool:
        for attempt in range(2):
            try:
                response = client.responses.parse(
                    model=model_name,
                    input=[
                        {
                            "role": "system",
                            "content": (
                                "You are a rigorous scientific figure-reading engine. "
                                "Do not invent panel labels, statistics, methods, or results."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": prompt,
                                },
                                {
                                    "type": "input_image",
                                    "image_url": data_url,
                                    "detail": "high",
                                },
                            ],
                        },
                    ],
                    text_format=schema,
                )

                parsed = getattr(response, "output_parsed", None)

                if parsed is None:
                    raise RuntimeError(
                        f"{model_name} returned no structured output."
                    )

                if isinstance(parsed, schema):
                    result = parsed
                else:
                    result = schema.model_validate(parsed)

                usage = getattr(response, "usage", None)
                usage_dict = None

                if usage is not None:
                    usage_dict = {
                        "input_tokens": getattr(usage, "input_tokens", None),
                        "output_tokens": getattr(usage, "output_tokens", None),
                        "total_tokens": getattr(usage, "total_tokens", None),
                    }

                return result, model_name, usage_dict

            except Exception as exc:
                errors.append(
                    f"OpenAI {model_name} attempt {attempt + 1}: {exc}"
                )

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

    # English copy is enough as grounding context for later stages.
    source = core_bundle.get(
        "en",
        core_bundle,
    )

    return json.dumps(
        source,
        ensure_ascii=False,
        indent=2,
    )[:30_000]


# ============================================================
# STAGE 1: CORE
# ============================================================

def analyze_core(
    *,
    paper_text: str,
    api_key: str,
    depth: str,
    detected_methods: List[str],
):
    prompt = f"""
You are LALSTUDY's Stage 1 scientific-reading engine.

{LANGUAGE_RULE}
{GROUNDING_RULE}

Learner level:
{DEPTH_INSTRUCTIONS.get(depth, DEPTH_INSTRUCTIONS["undergraduate"])}

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
{compact_text(paper_text, 135_000)}
"""

    return _call_structured(
        api_key=api_key,
        stage="core",
        prompt=prompt,
        schema=BilingualCore,
        model_pool=TEXT_MODELS,
        thinking_level="low",
    )


# ============================================================
# STAGE 2: PREREQUISITES
# ============================================================

def analyze_prerequisites(
    *,
    paper_text: str,
    core_bundle: dict,
    api_key: str,
    depth: str,
):
    prompt = f"""
You are LALSTUDY's prerequisite-learning module.

{LANGUAGE_RULE}
{GROUNDING_RULE}

Learner level:
{DEPTH_INSTRUCTIONS.get(depth, DEPTH_INSTRUCTIONS["undergraduate"])}

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
{compact_text(paper_text, 100_000)}
"""

    return _call_structured(
        api_key=api_key,
        stage="prerequisites",
        prompt=prompt,
        schema=BilingualPrerequisites,
        model_pool=TEXT_MODELS,
        thinking_level="low",
    )


# ============================================================
# STAGE 3: EXPERIMENTS
# ============================================================

def analyze_experiments(
    *,
    paper_text: str,
    core_bundle: dict,
    api_key: str,
    detected_methods: List[str],
):
    prompt = f"""
You are LALSTUDY's experimental-strategy module.

{LANGUAGE_RULE}
{GROUNDING_RULE}

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
{compact_text(paper_text, 125_000)}
"""

    return _call_structured(
        api_key=api_key,
        stage="experiments",
        prompt=prompt,
        schema=BilingualExperiments,
        model_pool=TEXT_MODELS,
        thinking_level="low",
    )


# ============================================================
# STAGE 4: FIGURES — PDF ONLY WHEN REQUESTED
# ============================================================

def analyze_figures(
    *,
    pdf_bytes: bytes,
    core_bundle: dict,
    api_key: str,
):
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise ValueError(
            "Figure analysis currently supports PDFs up to 50 MB."
        )

    prompt = f"""
You are LALSTUDY's Figure-reading module.

{LANGUAGE_RULE}
{GROUNDING_RULE}

CORE ANALYSIS
=============
{_core_context(core_bundle)}

TASK
Inspect the uploaded PDF and reconstruct the MAIN scientific Figures.
Do not analyze supplementary Figures unless essential.

For each Figure:
- role in the paper's story
- main scientific question
- panel-by-panel WHAT / HOW / RESULT / INTERPRETATION when labels are clear
- methods used
- overall takeaway
- what the Figure supports
- what it does NOT establish

Be conservative with panel labels. If a panel cannot be identified reliably,
do not invent it.

Keep the output focused rather than exhaustive.
"""

    return _call_structured(
        api_key=api_key,
        stage="figures",
        prompt=prompt,
        schema=BilingualFigures,
        model_pool=FIGURE_MODELS,
        pdf_bytes=pdf_bytes,
        thinking_level="low",
    )



# ============================================================
# SINGLE FIGURE ANALYSIS — OPENAI PRIMARY, GEMINI FALLBACK
# ============================================================

def analyze_single_figure(
    *,
    figure_label: str,
    image_bytes: bytes,
    image_mime_type: str,
    legend: str,
    core_bundle: dict,
    openai_api_key: str = "",
    gemini_api_key: str = "",
):
    if not image_bytes:
        raise ValueError("Figure image is empty.")

    figure_label = (figure_label or "Figure").strip()
    legend = (legend or "").strip()

    prompt = f"""
You are LALSTUDY's single-Figure scientific reading module.

{LANGUAGE_RULE}
{GROUNDING_RULE}

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
For this Figure explain:
- role in the paper's story
- main scientific question
- panel-by-panel WHAT / HOW / RESULT / INTERPRETATION when panel labels are readable
- methods used in each panel when supported by the image or legend
- overall takeaway
- what this Figure supports
- what it does NOT establish

IMPORTANT
- Do not analyze any other Figure.
- Preserve the target label as `{figure_label}`.
- Do not invent unreadable panel labels, values, statistics, or methods.
- If a panel is visually ambiguous, state the uncertainty instead of guessing.
- Distinguish observation from inference.
"""

    provider_errors = []

    if openai_api_key and openai_sdk_available():
        try:
            result, model, usage = _call_openai_figure_structured(
                api_key=openai_api_key,
                stage=f"single_figure:{figure_label}",
                prompt=prompt,
                image_bytes=image_bytes,
                image_mime_type=image_mime_type,
                schema=BilingualSingleFigure,
                model_pool=OPENAI_FIGURE_MODELS,
            )
            return result, model, "OpenAI", usage
        except StageCallError as exc:
            provider_errors.extend(exc.trace)
        except Exception as exc:
            provider_errors.append(f"OpenAI setup/call: {exc}")

    if gemini_api_key and sdk_available():
        try:
            result, model = _call_structured(
                api_key=gemini_api_key,
                stage=f"single_figure:{figure_label}",
                prompt=prompt,
                schema=BilingualSingleFigure,
                model_pool=FIGURE_MODELS,
                image_bytes=image_bytes,
                image_mime_type=image_mime_type,
                thinking_level="low",
            )
            return result, model, "Gemini fallback", None
        except StageCallError as exc:
            provider_errors.extend(exc.trace)
        except Exception as exc:
            provider_errors.append(f"Gemini fallback setup/call: {exc}")

    if not provider_errors:
        provider_errors.append(
            "No usable Figure AI provider is configured. Add OPENAI_API_KEY or GEMINI_API_KEY."
        )

    raise StageCallError(
        stage=f"single_figure:{figure_label}",
        trace=provider_errors,
    )


# ============================================================
# STAGE 5: CRITICAL READING + LEARNING PATH
# ============================================================

def analyze_critical_learning(
    *,
    paper_text: str,
    core_bundle: dict,
    experiments_bundle: Optional[dict],
    api_key: str,
    depth: str,
):
    exp_context = (
        json.dumps(
            (
                experiments_bundle.get("en", experiments_bundle)
                if experiments_bundle
                else {}
            ),
            ensure_ascii=False,
            indent=2,
        )[:25_000]
    )

    prompt = f"""
You are LALSTUDY's critical-reading and learning-planning module.

{LANGUAGE_RULE}
{GROUNDING_RULE}

Learner level:
{DEPTH_INSTRUCTIONS.get(depth, DEPTH_INSTRUCTIONS["undergraduate"])}

CORE ANALYSIS
=============
{_core_context(core_bundle)}

EXPERIMENT ANALYSIS IF AVAILABLE
================================
{exp_context}

TASK A — Critical reading
Identify:
- strongest evidence
- weakest inferential link
- plausible alternative explanations
- one especially informative missing control / experiment
- limitations explicitly stated by the authors
- reviewer-style questions

TASK B — Learning path
Create an ordered short plan for what this reader should learn/review before
reading the paper again. Prioritize concepts or methods that unlock multiple
parts of the paper.

PAPER TEXT
==========
{compact_text(paper_text, 105_000)}
"""

    return _call_structured(
        api_key=api_key,
        stage="critical_learning",
        prompt=prompt,
        schema=BilingualCriticalLearning,
        model_pool=TEXT_MODELS,
        thinking_level="low",
    )

# ============================================================
# KNOWLEDGE ARCHIVE MISS FILLER
# ============================================================

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
        value = (
            value
            or ""
        ).strip()

        if not value:
            continue

        key = value.casefold()

        if key in seen:
            continue

        seen.add(
            key
        )

        cleaned.append(
            value[:160]
        )

    if not cleaned:
        raise ValueError(
            "No concepts were supplied."
        )

    if len(cleaned) > 8:
        raise ValueError(
            "A maximum of 8 concepts can be explained in one batch."
        )

    context = (
        paper_context
        or ""
    ).strip()[:8000]

    prompt = f"""
You are building LALSTUDY's reusable scientific Knowledge Archive.

The user selected these concepts/phrases while reading a life-science paper:

{json.dumps(cleaned, ensure_ascii=False)}

Reader level:
{DEPTH_INSTRUCTIONS.get(depth, DEPTH_INSTRUCTIONS["undergraduate"])}

Optional paper context is provided ONLY to disambiguate what a selected phrase
means. DO NOT archive paper-specific results, sample sizes, Figure findings,
author claims, or conclusions as general knowledge.

PAPER CONTEXT FOR DISAMBIGUATION
================================
{context or "none"}

TASK
For every requested term, create a compact, reusable prerequisite-knowledge card.

Rules:
1. `requested_term` must preserve the user's input.
2. `canonical_name` should be the conventional English scientific concept name.
3. `aliases` should contain only true synonyms / common alternate names.
4. `definition_*` answers "what is this?"
5. `mechanism_*` explains how it works or the causal/structural logic when relevant.
6. `why_it_matters_*` explains why a life-science reader commonly needs this concept.
7. `prerequisites` lists 0-5 simpler concepts that help understand it.
8. Do not pretend a relation is universally true if it is context dependent.
9. Do not cite or summarize this particular paper.
10. The output must be suitable for reuse for a DIFFERENT USER reading a DIFFERENT paper.

KOREAN STYLE
============
Korean prose must use conventional English-first scientific terminology.
Prefer expressions such as:
- lysosome의 acidification
- p53 conformational change
- zinc homeostasis
- Flow cytometry
Do not unnecessarily transliterate technical English terms into Hangul.

Generate BOTH Korean and English fields in the same object.
"""

    return _call_structured(
        api_key=api_key,
        stage="knowledge_archive_fill",
        prompt=prompt,
        schema=ConceptBatchAnalysis,
        model_pool=TEXT_MODELS,
        thinking_level="low",
    )

