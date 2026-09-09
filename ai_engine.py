import hashlib
import json
import os
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None


DEFAULT_MODEL = os.getenv(
    "LALSTUDY_GEMINI_MODEL",
    "gemini-3.6-flash"
)


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


def build_prompt(language: str, depth: str, detected_methods: List[str]) -> str:
    if language == "ko":
        output_instruction = """
Write all explanatory prose in natural Korean.
Keep conventional scientific names, gene/protein symbols, assay names,
and method names such as Flow cytometry, Western blotting, scRNA-seq,
FOXP3, STAT5, etc. in their conventional scientific form when useful.
Do not awkwardly translate standard technical terms merely to make them Korean.
"""
    else:
        output_instruction = """
Write all explanatory prose in clear scientific English.
"""

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

{output_instruction}

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
10. Prefer the conventional English name for experimental methods so that they can
    link to LALSTUDY's method ontology.

OUTPUT GOAL
-----------
Build:
- a compact paper overview,
- a causal/argument logic map,
- prerequisite concepts with dependency relationships,
- the main experimental strategy,
- Figure-by-Figure interpretation,
- a critical-reading section,
- an ordered learning path.

For the logic map, try to reconstruct the flow:
Background → Gap → Question/Hypothesis → Experiment → Observation → Inference → Next question → Conclusion.

For each Figure, focus on:
WHAT question is asked?
HOW is it tested?
WHAT is directly observed?
WHY does that matter?
WHAT does it prove?
WHAT does it NOT prove?

Do not include references that are merely cited by the paper as if they were findings of this paper.
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
    return f"{digest}:{language}:{depth}:{model}"


def analyze_pdf(
    pdf_bytes: bytes,
    api_key: str,
    language: str = "ko",
    depth: str = "undergraduate",
    detected_methods: Optional[List[str]] = None,
    model: str = DEFAULT_MODEL,
) -> PaperAnalysis:
    if not sdk_available():
        raise RuntimeError(
            "google-genai is not installed. "
            "Run: python -m pip install -r requirements.txt"
        )

    if not api_key:
        raise ValueError("Gemini API key is required.")

    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise ValueError(
            "This beta sends PDFs inline and supports PDFs up to 50 MB."
        )

    client = genai.Client(api_key=api_key)

    prompt = build_prompt(
        language=language,
        depth=depth,
        detected_methods=detected_methods or [],
    )

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf",
            ),
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=0.15,
            response_mime_type="application/json",
            response_schema=PaperAnalysis,
        ),
    )

    # SDK versions can expose parsed output differently.
    if getattr(response, "parsed", None) is not None:
        parsed = response.parsed
        if isinstance(parsed, PaperAnalysis):
            return parsed
        return PaperAnalysis.model_validate(parsed)

    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("The model returned no text.")

    return PaperAnalysis.model_validate_json(text)
