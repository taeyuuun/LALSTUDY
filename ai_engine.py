import hashlib
import json
import os
import time
import random
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None


DEFAULT_MODELS = [
    x.strip()
    for x in os.getenv(
        "LALSTUDY_GEMINI_MODELS",
        "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash",
    ).split(",")
    if x.strip()
]
DEFAULT_MODEL = DEFAULT_MODELS[0]


# ============================================================
# STRUCTURED OUTPUT SCHEMA
# ============================================================

class LogicStep(BaseModel):
    order: int = Field(description="Order in the paper's argument.")
    question: str = Field(description="Scientific question addressed at this step.")
    experiment_or_analysis: str = Field(description="What the authors did.")
    observation: str = Field(description="What was directly observed.")
    inference: str = Field(description="What the authors infer from the observation.")
    evidence_location: str = Field(
        description="Figure/panel/section supporting the step, or 'not clearly identifiable'."
    )


class PrerequisiteConcept(BaseModel):
    name: str
    difficulty: Literal["basic", "intermediate", "advanced"]
    why_needed: str = Field(description="Why this concept is needed to understand this paper.")
    explanation: str = Field(
        description="Standalone background explanation using general scientific knowledge."
    )
    paper_context: str = Field(
        description="How the concept is specifically used in this paper."
    )
    prerequisites: List[str] = Field(default_factory=list)


class ExperimentAnalysis(BaseModel):
    method: str = Field(
        description="Conventional scientific method name, preferably canonical English name."
    )
    scientific_question: str
    sample_or_model: str
    manipulated_variable: str
    readout: str
    why_this_method: str
    result_meaning: str
    limitation: str
    evidence_location: str


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


class PaperAnalysis(BaseModel):
    overview: PaperOverview
    logic_map: List[LogicStep] = Field(default_factory=list)
    prerequisites: List[PrerequisiteConcept] = Field(default_factory=list)
    experiments: List[ExperimentAnalysis] = Field(default_factory=list)
    figures: List[FigureAnalysis] = Field(default_factory=list)
    critical_reading: CriticalReading
    learning_path: List[LearningItem] = Field(default_factory=list)


class BilingualPaperAnalysis(BaseModel):
    """
    One PDF analysis contains BOTH display languages.
    Language switching in the UI therefore never requires another PDF analysis.
    """
    ko: PaperAnalysis
    en: PaperAnalysis


# ============================================================
# PROMPT
# ============================================================

DEPTH_INSTRUCTIONS = {
    "foundation": """
The learner is new to the field.
Explain foundational biology explicitly before advanced mechanisms.
Avoid assuming familiarity with common experimental logic.
""",
    "undergraduate": """
The learner is a life-science undergraduate.
Assume general molecular/cell biology knowledge, but explain specialized
pathways, experimental design, omics analyses, and field-specific concepts.
""",
    "advanced": """
The learner is an advanced undergraduate / graduate reader.
Keep basic explanations concise and emphasize mechanism, causal inference,
experimental design, statistics, limitations, and interpretation.
""",
}


def build_prompt(depth: str, detected_methods: List[str]) -> str:
    method_hint = ", ".join(detected_methods[:30]) if detected_methods else "none provided"

    return f"""
You are the scientific-learning engine for LALSTUDY.

Your task is NOT merely to summarize the uploaded paper.
Reconstruct the paper as a learning system for a reader who wants to understand:
(1) why the study was necessary,
(2) the prerequisite knowledge,
(3) the logic connecting experiments,
(4) what each experiment and Figure actually establishes,
(5) what remains uncertain.

IMPORTANT OUTPUT LANGUAGE RULE
------------------------------
Return TWO semantically equivalent versions of the complete analysis:

- `en`: clear scientific English.
- `ko`: natural Korean explanatory prose using an ENGLISH-FIRST life-science terminology style.

For `ko`, DO NOT mechanically transliterate or translate specialized biological
terms into Hangul when researchers commonly use the English term.

Use Korean grammar/connective prose, but preserve technical nouns and phrases
in English whenever practical, especially:
- organelles and cellular structures
- pathways and molecular processes
- gene/protein names
- cell types and immune subsets
- assay / experimental method names
- omics and bioinformatics terms
- pharmacology / molecular biology terminology

Preferred Korean-style examples:
- "lysosome의 acidification이 감소했다"
- "autophagy flux를 측정했다"
- "Flow cytometry로 Treg population을 분석했다"
- "STAT5 phosphorylation이 증가했다"
- "single-cell RNA sequencing으로 cell state를 구분했다"

Avoid forms such as:
- "리소좀" when `lysosome` is appropriate
- "엔도좀" when `endosome` is appropriate
- "오토파지" when `autophagy` is appropriate
- unnecessarily translating standard method names

When a technical term appears in the PDF, preferentially preserve its original
English spelling/capitalization in the Korean version.

The Korean and English versions MUST represent the same scientific interpretation.
Do not independently invent different claims between languages.

Learner depth:
{DEPTH_INSTRUCTIONS.get(depth, DEPTH_INSTRUCTIONS["undergraduate"])}

LALSTUDY's rule-based detector independently found these possible methods:
{method_hint}

Treat this only as a hint. Verify methods against the PDF itself.
Do not force a method into the analysis if the PDF does not support it.

STRICT GROUNDING RULES
----------------------
1. Every statement about THIS study's question, design, results, sample,
   statistics, Figures, claims, or limitations must be grounded in the PDF.
2. General scientific background may use established background knowledge,
   but keep it clearly separated in the prerequisite explanation fields.
3. Never invent a sample size, p-value, method, panel, mechanism, or result.
4. Distinguish direct OBSERVATION from author INTERPRETATION.
5. If evidence is unclear or unavailable, explicitly say so rather than guessing.
6. Figure and panel labels must only be used when you can identify them from the PDF.
7. "What it proves" should be conservative. Association is not causation.
8. "What it does not prove" should identify the key inference boundary.
9. For experiments, explain WHY the chosen method answers the scientific question,
   not merely what the method generally does.
10. Prefer conventional English method names so they can link to LALSTUDY ontology.

OUTPUT GOAL
-----------
For BOTH `ko` and `en`, build:
- a compact paper overview,
- a causal/argument logic map,
- prerequisite concepts with dependency relationships,
- the main experimental strategy,
- Figure-by-Figure interpretation,
- a critical-reading section,
- an ordered learning path.

For the logic map:
Background → Gap → Question/Hypothesis → Experiment → Observation → Inference → Next question → Conclusion.

For each Figure:
WHAT question is asked?
HOW is it tested?
WHAT is directly observed?
WHY does that matter?
WHAT does it support?
WHAT does it NOT establish?

Do not include references merely cited by the paper as if they were findings of this study.
"""


# ============================================================
# GEMINI
# ============================================================

def sdk_available() -> bool:
    return genai is not None and types is not None


def make_cache_key(
    pdf_bytes: bytes,
    language: str,
    depth: str,
    model: str,
) -> str:
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    return f"{digest}:bilingual:{depth}:{model}"


def _transient(exc):
    s = str(exc).lower()
    return any(x in s for x in [
        "429","rate limit","resource_exhausted","500","502","503","504",
        "unavailable","high demand","timeout","deadline","internal",
        "bad gateway","gateway timeout"
    ])

def _model_bad(exc):
    s = str(exc).lower()
    return "404" in s or "not_found" in s or ("model" in s and "not available" in s)

def analyze_pdf(
    pdf_bytes: bytes,
    api_key: str,
    language: str = "ko",
    depth: str = "undergraduate",
    detected_methods: Optional[List[str]] = None,
    model: Optional[str] = None,
) -> BilingualPaperAnalysis:
    if not sdk_available():
        raise RuntimeError("google-genai is not installed.")
    if not api_key:
        raise ValueError("Server GEMINI_API_KEY is not configured.")
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise ValueError("This beta supports PDFs up to 50 MB.")

    client = genai.Client(api_key=api_key)
    prompt = build_prompt(
        depth=depth,
        detected_methods=detected_methods or [],
    )

    models = []
    if model:
        models.append(model)
    for m in DEFAULT_MODELS:
        if m not in models:
            models.append(m)

    errors = []

    for model_name in models:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(
                            data=pdf_bytes,
                            mime_type="application/pdf",
                        ),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=BilingualPaperAnalysis,
                    ),
                )

                if getattr(response, "parsed", None) is not None:
                    parsed = response.parsed
                    if isinstance(parsed, BilingualPaperAnalysis):
                        return parsed
                    return BilingualPaperAnalysis.model_validate(parsed)

                body = getattr(response, "text", None)
                if not body:
                    raise RuntimeError(f"{model_name} returned no text.")

                return BilingualPaperAnalysis.model_validate_json(body)

            except Exception as exc:
                errors.append(f"{model_name} attempt {attempt + 1}: {exc}")

                if _model_bad(exc):
                    break

                if not _transient(exc):
                    break

                if attempt < 2:
                    time.sleep(
                        1.5 * (2 ** attempt)
                        + random.uniform(0, 0.8)
                    )

    raise RuntimeError(
        "All configured Gemini models failed. "
        + " | ".join(errors[-4:])
    )
