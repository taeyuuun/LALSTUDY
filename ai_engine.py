import os
import re
from typing import List, Literal

from pydantic import BaseModel, Field

OPENAI_TEXT_MODELS = [
    x.strip()
    for x in os.getenv(
        "LALSTUDY_OPENAI_TEXT_MODELS",
        "gpt-5.6-luna,gpt-5.6-terra",
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


class MethodEncyclopediaEntry(BaseModel):
    canonical_name: str

    summary_ko: str
    summary_en: str

    principle_ko: str
    principle_en: str

    best_for_ko: str
    best_for_en: str

    limitations_ko: str
    limitations_en: str


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
    difficulty: Literal["basic", "intermediate", "advanced"] = "intermediate"


class ConceptBatchAnalysis(BaseModel):
    concepts: List[ConceptExplanation] = Field(default_factory=list)


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

Avoid unnecessary Hangul transliterations and avoid translating conventional
assay names. Korean and English must contain the same scientific interpretation.
"""


GROUNDING_RULE = r"""
GROUNDING RULES
1. Claims about this study must come from the provided paper content.
2. General background knowledge is allowed only where the task explicitly asks for it.
3. Never invent sample sizes, statistics, panels, experiments, mechanisms, or results.
4. Separate direct observation from interpretation.
5. If evidence is unclear, say so.
6. Association is not causation.
7. Preserve conventional English method names for LALSTUDY ontology linking.
"""


class StageCallError(RuntimeError):
    def __init__(self, stage: str, trace: List[str]):
        self.stage = stage
        self.trace = trace
        super().__init__(f"{stage} analysis could not be completed after retry/fallback.")


def compact_text(text: str, max_chars: int = 150_000) -> str:
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
    matches = list(
        re.finditer(
            r"(?im)^\s*(references|bibliography)\s*$",
            text,
        )
    )
    if not matches:
        return None

    late = [m.start() for m in matches if m.start() > len(text) * 0.55]
    return late[0] if late else None
