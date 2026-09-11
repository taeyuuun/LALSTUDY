"""Method Wiki AI helper.

Kept separate from ai_router public imports so Method Wiki can be deployed
safely even when Streamlit Cloud temporarily has an older ai_router.py from a
previous patch.
"""

from __future__ import annotations

import json
from typing import List

from pydantic import BaseModel

import ai_engine as engine
from ai_router import _openai_parse


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


def generate_method_encyclopedia_entry(
    *,
    canonical_name: str,
    aliases: List[str],
    category: str,
    parent_method: str,
    submethods: List[str],
    api_key: str,
):
    """Generate one concise reusable Method Wiki entry."""

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
        schema=MethodEncyclopediaEntry,
        model_pool=engine.OPENAI_TEXT_MODELS,
    )

    return result, model, usage
