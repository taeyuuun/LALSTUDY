"""Structured Method Wiki AI helper."""

from __future__ import annotations

import json
from typing import List

from pydantic import BaseModel, Field

import ai_engine as engine
from ai_router import _openai_parse


class MethodEncyclopediaEntry(BaseModel):
    canonical_name: str

    # Backward-compatible concise fields.
    summary_ko: str
    summary_en: str
    principle_ko: str
    principle_en: str
    best_for_ko: str
    best_for_en: str
    limitations_ko: str
    limitations_en: str

    # Readability-first structured article fields.
    key_question_ko: str
    key_question_en: str

    one_liner_ko: str
    one_liner_en: str

    principle_steps_ko: List[str] = Field(min_length=3, max_length=5)
    principle_steps_en: List[str] = Field(min_length=3, max_length=5)

    best_for_points_ko: List[str] = Field(min_length=2, max_length=5)
    best_for_points_en: List[str] = Field(min_length=2, max_length=5)

    limitation_points_ko: List[str] = Field(min_length=2, max_length=5)
    limitation_points_en: List[str] = Field(min_length=2, max_length=5)

    interpretation_tip_ko: str
    interpretation_tip_en: str


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
    Generate one reusable, readability-first Method Wiki entry.

    The answer is method-level knowledge only. It must never depend on a
    specific paper.
    """

    prompt = f"""
You are writing one compact, highly readable encyclopedia entry for
LALSTUDY's experimental-method wiki.

METHOD
======
Canonical name: {canonical_name}
Known aliases: {json.dumps(aliases[:20], ensure_ascii=False)}
Existing ontology category: {category or "unknown"}
Parent method: {parent_method or "none"}
Known submethods: {json.dumps(submethods[:20], ensure_ascii=False)}

GOAL
====
A life-science undergraduate should understand, within 20 seconds:
- what question this method answers,
- what physically happens in the experiment,
- when to choose it,
- what result it does NOT automatically prove.

OUTPUT STYLE
============
Write concise reusable scientific knowledge, not a textbook chapter.

Required:
1. key_question
   - one short question the method is best suited to answer.
2. one_liner
   - one sentence, <= 35 Korean eojeol / <= 35 English words.
3. principle_steps
   - 3-5 short ordered conceptual steps.
   - explain the experimental logic, NOT a protocol.
4. best_for_points
   - 2-5 concrete use cases.
5. limitation_points
   - 2-5 interpretation caveats.
6. interpretation_tip
   - one especially useful "read the result correctly" sentence.

Also return the legacy summary/principle/best_for/limitations strings so older
LALSTUDY versions remain compatible.

Rules:
- No paper-specific findings.
- No kit names, concentrations, timings, or procedural recipes.
- Do not use vague marketing language.
- Use standard scientific terminology in English where conventional.
- Korean must use natural spacing and short sentences.
- Avoid long mixed Korean-English sentences.
- If an English technical noun needs explanation, explain it once in Korean.
- Distinguish closely related terms when the distinction matters
  (for example FACS vs flow cytometry).
- Korean and English must be semantically equivalent.
"""

    result, model, usage = _openai_parse(
        api_key=api_key,
        stage="method_encyclopedia_fill_v2",
        prompt=prompt,
        schema=MethodEncyclopediaEntry,
        model_pool=engine.OPENAI_TEXT_MODELS,
    )

    return result, model, usage
