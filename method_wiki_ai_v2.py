"""Defensive Method Wiki structured-article helper."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from pydantic import BaseModel, Field

import ai_engine as engine
from ai_router import _openai_parse


class MethodEncyclopediaEntryV2(BaseModel):
    canonical_name: str = ""

    summary_ko: str
    summary_en: str
    principle_ko: str
    principle_en: str
    best_for_ko: str
    best_for_en: str
    limitations_ko: str
    limitations_en: str

    # Optional on purpose: mixed-version/stale outputs must not crash saving.
    key_question_ko: str = ""
    key_question_en: str = ""
    one_liner_ko: str = ""
    one_liner_en: str = ""

    principle_steps_ko: List[str] = Field(default_factory=list)
    principle_steps_en: List[str] = Field(default_factory=list)

    best_for_points_ko: List[str] = Field(default_factory=list)
    best_for_points_en: List[str] = Field(default_factory=list)

    limitation_points_ko: List[str] = Field(default_factory=list)
    limitation_points_en: List[str] = Field(default_factory=list)

    interpretation_tip_ko: str = ""
    interpretation_tip_en: str = ""


def _as_dict(result: Any) -> Dict:
    if isinstance(result, dict):
        return dict(result)
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        return result.dict()
    return {}


def _split_points(text: str, limit: int = 4) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?。])\s+|;\s+|\n+",
        text,
    )

    points = [
        p.strip(" •-\t")
        for p in parts
        if p.strip(" •-\t")
    ]

    if len(points) <= 1 and len(text) > 100:
        points = [
            p.strip()
            for p in re.split(
                r",\s+(?=[A-Za-z가-힣])",
                text,
            )
            if p.strip()
        ]

    return points[:limit]


def normalize_method_entry(
    result: Any,
    *,
    canonical_name: str,
) -> Dict:
    data = _as_dict(result)

    summary_ko = str(data.get("summary_ko") or "").strip()
    summary_en = str(data.get("summary_en") or "").strip()
    principle_ko = str(data.get("principle_ko") or "").strip()
    principle_en = str(data.get("principle_en") or "").strip()
    best_for_ko = str(data.get("best_for_ko") or "").strip()
    best_for_en = str(data.get("best_for_en") or "").strip()
    limitations_ko = str(data.get("limitations_ko") or "").strip()
    limitations_en = str(data.get("limitations_en") or "").strip()

    out = {
        "canonical_name": (
            str(data.get("canonical_name") or canonical_name).strip()
            or canonical_name
        ),

        "summary_ko": summary_ko,
        "summary_en": summary_en,
        "principle_ko": principle_ko,
        "principle_en": principle_en,
        "best_for_ko": best_for_ko,
        "best_for_en": best_for_en,
        "limitations_ko": limitations_ko,
        "limitations_en": limitations_en,

        "key_question_ko": (
            str(data.get("key_question_ko") or "").strip()
            or f"{canonical_name}은 어떤 생물학적 질문에 답하는 실험인가?"
        ),
        "key_question_en": (
            str(data.get("key_question_en") or "").strip()
            or f"What biological question does {canonical_name} answer?"
        ),

        "one_liner_ko": (
            str(data.get("one_liner_ko") or "").strip()
            or summary_ko
        ),
        "one_liner_en": (
            str(data.get("one_liner_en") or "").strip()
            or summary_en
        ),

        "principle_steps_ko": (
            list(data.get("principle_steps_ko") or [])
            or _split_points(principle_ko, 4)
        ),
        "principle_steps_en": (
            list(data.get("principle_steps_en") or [])
            or _split_points(principle_en, 4)
        ),

        "best_for_points_ko": (
            list(data.get("best_for_points_ko") or [])
            or _split_points(best_for_ko, 4)
        ),
        "best_for_points_en": (
            list(data.get("best_for_points_en") or [])
            or _split_points(best_for_en, 4)
        ),

        "limitation_points_ko": (
            list(data.get("limitation_points_ko") or [])
            or _split_points(limitations_ko, 4)
        ),
        "limitation_points_en": (
            list(data.get("limitation_points_en") or [])
            or _split_points(limitations_en, 4)
        ),

        "interpretation_tip_ko": (
            str(data.get("interpretation_tip_ko") or "").strip()
            or "이 방법이 직접 측정한 값과 그 값에서 추론한 생물학적 의미를 구분해서 읽는다."
        ),
        "interpretation_tip_en": (
            str(data.get("interpretation_tip_en") or "").strip()
            or "Distinguish the assay's direct measurement from the biological interpretation inferred from it."
        ),
    }

    # Final non-empty safety net.
    if not out["principle_steps_ko"]:
        out["principle_steps_ko"] = [principle_ko or summary_ko or canonical_name]
    if not out["principle_steps_en"]:
        out["principle_steps_en"] = [principle_en or summary_en or canonical_name]

    if not out["best_for_points_ko"]:
        out["best_for_points_ko"] = [best_for_ko or "이 방법이 직접 답할 수 있는 질문에 사용한다."]
    if not out["best_for_points_en"]:
        out["best_for_points_en"] = [best_for_en or "Use it for questions the assay can directly address."]

    if not out["limitation_points_ko"]:
        out["limitation_points_ko"] = [limitations_ko or "측정값과 생물학적 인과관계를 동일시하지 않는다."]
    if not out["limitation_points_en"]:
        out["limitation_points_en"] = [limitations_en or "Do not equate a measured association with biological causality."]

    return out


def build_method_db_payload(
    result: Any,
    *,
    canonical_name: str,
    facets: Dict,
    model: str,
) -> Dict:
    """
    Store the readability-first article WITHOUT requiring a new SQL column.

    Existing v0.5.0 columns are reused:
    - summary_*      <- one-line overview
    - principle_*    <- newline-separated conceptual steps
    - best_for_*     <- newline-separated use cases
    - limitations_*  <- newline-separated caveats

    The UI reconstructs cards from these fields.
    """

    data = normalize_method_entry(
        result,
        canonical_name=canonical_name,
    )

    def join_points(points, fallback):
        cleaned = [
            str(x).strip()
            for x in (points or [])
            if str(x).strip()
        ]

        return (
            "\n".join(cleaned)
            if cleaned
            else fallback
        )

    return {
        "canonical_name": canonical_name,

        "summary_ko": (
            data["one_liner_ko"]
            or data["summary_ko"]
        ),
        "summary_en": (
            data["one_liner_en"]
            or data["summary_en"]
        ),

        "principle_ko": join_points(
            data["principle_steps_ko"],
            data["principle_ko"],
        ),
        "principle_en": join_points(
            data["principle_steps_en"],
            data["principle_en"],
        ),

        "best_for_ko": join_points(
            data["best_for_points_ko"],
            data["best_for_ko"],
        ),
        "best_for_en": join_points(
            data["best_for_points_en"],
            data["best_for_en"],
        ),

        "limitations_ko": join_points(
            data["limitation_points_ko"],
            data["limitations_ko"],
        ),
        "limitations_en": join_points(
            data["limitation_points_en"],
            data["limitations_en"],
        ),

        "facets": facets,
        "quality_status": "AI_GENERATED",
        "source_model": model,
    }


def generate_method_encyclopedia_entry(
    *,
    canonical_name: str,
    aliases: List[str],
    category: str,
    parent_method: str,
    submethods: List[str],
    api_key: str,
):
    prompt = f"""
You are writing one highly readable experimental-method encyclopedia entry
for LALSTUDY.

METHOD
======
Canonical name: {canonical_name}
Known aliases: {json.dumps(aliases[:20], ensure_ascii=False)}
Existing ontology category: {category or "unknown"}
Parent method: {parent_method or "none"}
Known submethods: {json.dumps(submethods[:20], ensure_ascii=False)}

A life-science undergraduate should understand within 20 seconds:
- what question this method answers
- what physically happens in the experiment
- when to choose it
- what the result does NOT automatically prove

Return both Korean and English for:
- summary
- principle
- best_for
- limitations
- key_question
- one_liner
- principle_steps
- best_for_points
- limitation_points
- interpretation_tip

Keep sentences short.
Do not include paper-specific findings, kit names, concentrations, timings,
or step-by-step protocols.
"""

    result, model, usage = _openai_parse(
        api_key=api_key,
        stage="method_encyclopedia_fill_v2_1",
        prompt=prompt,
        schema=MethodEncyclopediaEntryV2,
        model_pool=engine.OPENAI_TEXT_MODELS,
    )

    return result, model, usage
