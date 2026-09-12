"""LALSTUDY scientific terminology presentation.

v0.6.4.2
---------
The first terminology prototype used a fixed glossary. That made common terms
easy to annotate but missed exactly the difficult, paper-specific terms that
students actually need help with.

This version keeps ONE shared terminology setting, but changes bilingual mode to
use a small AI terminology-extraction step:

- UI language remains independent from scientific-term notation.
- `English only` shows the stored English-first Korean prose as-is.
- `English + 한국어 병행` identifies only difficult / field-specific terms in
  the currently displayed content and annotates their first useful occurrence.
- A small deterministic method glossary is kept only for assay/method names and
  very short labels where calling AI would be wasteful.
- Extracted glossaries are cached in Streamlit session state by content hash, so
  reruns do not repeatedly call OpenAI.
- Stored paper analysis, Knowledge Archive records, and Method Wiki records are
  never rewritten or duplicated.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

import streamlit as st


TERM_MODE_OPTIONS = {
    "English only": "en_only",
    "English + 한국어 병행": "bilingual",
}

DEFAULT_TERM_MODE_LABEL = "English + 한국어 병행"


# Only method / assay names belong in the deterministic fallback.
# Broad biology concepts are intentionally NOT hard-coded here.
METHOD_GLOSSARY = [
    ("single-cell RNA sequencing", "단일세포 RNA 시퀀싱"),
    ("single-cell RNA-seq", "단일세포 RNA 시퀀싱"),
    ("scRNA-seq", "단일세포 RNA 시퀀싱"),
    ("bulk RNA sequencing", "벌크 RNA 시퀀싱"),
    ("RNA sequencing", "RNA 시퀀싱"),
    ("RNA-seq", "RNA 시퀀싱"),
    ("Flow cytometry", "유세포분석"),
    ("fluorescence-activated cell sorting", "형광활성세포분류"),
    ("FACS", "형광활성세포분류"),
    ("mass cytometry", "질량세포분석"),
    ("Western blotting", "웨스턴 블로팅"),
    ("Western blot", "웨스턴 블롯"),
    ("immunofluorescence", "면역형광"),
    ("immunohistochemistry", "면역조직화학"),
    ("confocal microscopy", "공초점 현미경"),
    ("electron microscopy", "전자현미경"),
    ("RT-qPCR", "역전사 정량 PCR"),
    ("qPCR", "정량 PCR"),
    ("RT-PCR", "역전사 PCR"),
    ("PCR", "중합효소연쇄반응"),
    ("ELISA", "효소면역측정법"),
    ("co-immunoprecipitation", "공동면역침강"),
    ("Co-IP", "공동면역침강"),
    ("immunoprecipitation", "면역침강"),
    ("ATAC-seq", "염색질 접근성 시퀀싱"),
    ("ChIP-seq", "염색질 면역침강 시퀀싱"),
    ("CRISPR-Cas9", "CRISPR-Cas9 유전자편집"),
    ("CRISPR", "CRISPR 유전자편집"),
    ("luciferase assay", "루시퍼레이스 분석"),
    ("reporter assay", "리포터 분석"),
    ("cell viability assay", "세포 생존율 분석"),
    ("cytotoxicity assay", "세포독성 분석"),
]


# Explicitly tell the model not to waste bilingual labels on these.
# These are expected undergraduate-level basics in the LALSTUDY target audience.
BASIC_TERM_EXCLUSIONS = [
    "cell",
    "cells",
    "gene",
    "genes",
    "protein",
    "proteins",
    "DNA",
    "RNA",
    "mRNA",
    "experiment",
    "analysis",
    "sample",
    "control",
    "result",
    "figure",
    "panel",
    "expression",
    "activation",
    "receptor",
    "ligand",
    "antibody",
    "antigen",
    "mutation",
    "wild-type",
    "pathway",
]


def terminology_selector(lang: str) -> str:
    """Render the global scientific-term preference."""
    if "lalstudy_terminology_label" not in st.session_state:
        st.session_state["lalstudy_terminology_label"] = DEFAULT_TERM_MODE_LABEL

    if lang != "ko":
        return get_terminology_mode()

    label = st.sidebar.selectbox(
        "🔬 Scientific terms",
        list(TERM_MODE_OPTIONS.keys()),
        key="lalstudy_terminology_label",
        help=(
            "English only: 전공용어를 영어 중심으로 표시합니다.\n\n"
            "English + 한국어 병행: 어려운 전공용어의 첫 등장에 "
            "한국어 뜻을 함께 표시합니다."
        ),
    )

    return TERM_MODE_OPTIONS.get(
        label,
        "bilingual",
    )


def get_terminology_mode() -> str:
    label = st.session_state.get(
        "lalstudy_terminology_label",
        DEFAULT_TERM_MODE_LABEL,
    )

    return TERM_MODE_OPTIONS.get(
        label,
        "bilingual",
    )


def _collect_strings(
    value: Any,
    *,
    max_chars: int = 18_000,
) -> str:
    """Collect user-visible prose from a nested result for one glossary call."""
    chunks = []
    used = 0

    def walk(node):
        nonlocal used

        if used >= max_chars:
            return

        if isinstance(node, str):
            text = node.strip()

            if (
                len(text) < 2
                or text.startswith("http://")
                or text.startswith("https://")
            ):
                return

            room = max_chars - used
            piece = text[:room]
            chunks.append(piece)
            used += len(piece) + 1
            return

        if isinstance(node, dict):
            for child in node.values():
                walk(child)
            return

        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(value)

    return "\n".join(chunks)


def _contains_hangul(text: str) -> bool:
    return bool(
        re.search(
            r"[가-힣]",
            text or "",
        )
    )


def _already_followed_by_korean_parenthetical(
    text: str,
    end: int,
) -> bool:
    tail = text[end : end + 80]

    return bool(
        re.match(
            r"\s*\([^)]*[가-힣][^)]*\)",
            tail,
        )
    )


def _inside_parentheses(
    text: str,
    index: int,
) -> bool:
    left_open = text.rfind(
        "(",
        0,
        index,
    )
    left_close = text.rfind(
        ")",
        0,
        index,
    )

    return left_open > left_close


def _method_seed_glossary(
    text: str,
) -> list[dict]:
    """Cheap fallback for canonical assay names."""
    found = []
    lower = text.casefold()

    for english, korean in sorted(
        METHOD_GLOSSARY,
        key=lambda x: len(x[0]),
        reverse=True,
    ):
        if english.casefold() in lower:
            found.append(
                {
                    "surface": english,
                    "english": english,
                    "korean": korean,
                }
            )

    return found


def _extract_glossary_with_ai(
    text: str,
) -> list[dict]:
    """Ask OpenAI only which difficult terms deserve bilingual annotation."""
    try:
        from pydantic import BaseModel, Field
        from openai import OpenAI

        from ai_provider import get_openai_api_key
        from ai_router import get_text_models
    except Exception:
        return []

    api_key = (
        get_openai_api_key()
        or ""
    ).strip()

    if not api_key:
        return []

    class TermItem(BaseModel):
        surface: str = Field(
            description=(
                "Exact surface form already present in the input text. "
                "Prefer an English scientific term when one is present."
            )
        )
        english: str = Field(
            description="Canonical scientific English term."
        )
        korean: str = Field(
            description=(
                "Short, natural Korean meaning that actually helps comprehension. "
                "Do not merely transliterate English if a meaningful Korean term exists."
            )
        )

    class GlossaryResult(BaseModel):
        terms: list[TermItem] = Field(
            default_factory=list
        )

    exclusions = ", ".join(
        BASIC_TERM_EXCLUSIONS
    )

    prompt = f"""
You are LALSTUDY's scientific-terminology editor.

TARGET READER
A Korean life-science undergraduate reading a research paper.

TASK
From the text below, select ONLY the difficult, field-specific scientific terms
whose Korean meaning would materially help the reader continue reading.

The purpose is NOT to translate every scientific noun.
The previous system over-annotated easy words and missed hard ones.
Fix that behavior.

PRIORITIZE
- specialized molecular or cellular mechanisms
- uncommon biological processes or states
- field-specific immunology / cancer / neuroscience / genetics terminology
- biochemical modifications or mechanistic concepts
- omics / computational / statistical terminology
- specialized assay or experimental-method names
- disease- or pathway-specific concepts that are not obvious to an undergraduate

DO NOT SELECT ordinary undergraduate basics such as:
{exclusions}

RULES
1. Prefer 4-12 genuinely useful difficult terms. Fewer is fine.
2. `surface` MUST be an exact term already visible in the supplied text.
3. If the text already uses an English scientific term, keep that exact English
   spelling as `surface`.
4. `english` is the canonical English scientific term.
5. `korean` must be a concise Korean meaning, not an essay.
6. Gene/protein symbols such as TP53, IL2RA, STAT5, XAF1 are NOT translated.
7. Do not select a term merely because it is English.
8. Do not return duplicate concepts.
9. Do not rewrite or summarize the source text.

TEXT
====
{text[:18_000]}
"""

    client = OpenAI(
        api_key=api_key,
    )

    models = []

    try:
        models = list(
            get_text_models()
        )
    except Exception:
        pass

    if not models:
        models = [
            "gpt-5.6-luna",
            "gpt-5.6-terra",
        ]

    for model in models:
        try:
            response = client.responses.parse(
                model=model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt,
                            }
                        ],
                    }
                ],
                text_format=GlossaryResult,
                max_output_tokens=900,
            )

            parsed = response.output_parsed

            if parsed is None:
                continue

            output = []

            for item in parsed.terms[:14]:
                surface = (
                    item.surface
                    or ""
                ).strip()
                english = (
                    item.english
                    or ""
                ).strip()
                korean = (
                    item.korean
                    or ""
                ).strip()

                if (
                    not surface
                    or not english
                    or not korean
                ):
                    continue

                # AI must ground each annotation in an actual visible term.
                if surface.casefold() not in text.casefold():
                    continue

                # Basic-term guardrail even if the model ignored the prompt.
                if (
                    surface.casefold()
                    in {
                        x.casefold()
                        for x in BASIC_TERM_EXCLUSIONS
                    }
                ):
                    continue

                output.append(
                    {
                        "surface": surface,
                        "english": english,
                        "korean": korean,
                    }
                )

            return output

        except Exception:
            continue

    return []


def _glossary_for_text(
    text: str,
) -> list[dict]:
    """Session-cached dynamic glossary for this exact visible content."""
    text = (
        text
        or ""
    ).strip()

    if not text:
        return []

    digest = hashlib.sha256(
        text.encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()

    cache = st.session_state.setdefault(
        "_lalstudy_smart_term_glossary",
        {},
    )

    if digest in cache:
        return cache[digest]

    # Always seed canonical method names deterministically.
    glossary = _method_seed_glossary(
        text
    )

    # Very short labels/titles do not justify an extra model call.
    if len(text) >= 220:
        smart = _extract_glossary_with_ai(
            text
        )

        # Smart terms first, then deterministic method fallback.
        combined = smart + glossary
    else:
        combined = glossary

    seen = set()
    deduped = []

    for item in combined:
        key = (
            item.get("english", "")
            .strip()
            .casefold()
        )

        if (
            not key
            or key in seen
        ):
            continue

        seen.add(key)
        deduped.append(item)

    cache[digest] = deduped

    return deduped


def _replace_first(
    text: str,
    *,
    surface: str,
    english: str,
    korean: str,
) -> tuple[str, bool]:
    if not text or not surface:
        return text, False

    pattern = re.compile(
        re.escape(surface),
        flags=re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        if _inside_parentheses(
            text,
            match.start(),
        ):
            continue

        if _already_followed_by_korean_parenthetical(
            text,
            match.end(),
        ):
            return text, True

        original = match.group(0)

        if _contains_hangul(original):
            replacement = (
                f"{english} ({korean})"
            )
        else:
            replacement = (
                f"{original} ({korean})"
            )

        return (
            text[: match.start()]
            + replacement
            + text[match.end() :],
            True,
        )

    return text, False


def _apply_glossary_recursive(
    value: Any,
    *,
    glossary: list[dict],
    seen: set[str],
):
    if isinstance(value, str):
        text = value

        if (
            text.startswith("http://")
            or text.startswith("https://")
        ):
            return text

        # Longest surface first avoids annotating a short method inside a long one.
        for item in sorted(
            glossary,
            key=lambda x: len(
                x.get(
                    "surface",
                    "",
                )
            ),
            reverse=True,
        ):
            canonical = (
                item.get(
                    "english",
                    "",
                )
                .strip()
                .casefold()
            )

            if (
                not canonical
                or canonical in seen
            ):
                continue

            text, changed = _replace_first(
                text,
                surface=item.get(
                    "surface",
                    "",
                ),
                english=item.get(
                    "english",
                    "",
                ),
                korean=item.get(
                    "korean",
                    "",
                ),
            )

            if changed:
                seen.add(canonical)

        return text

    if isinstance(value, list):
        return [
            _apply_glossary_recursive(
                item,
                glossary=glossary,
                seen=seen,
            )
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            _apply_glossary_recursive(
                item,
                glossary=glossary,
                seen=seen,
            )
            for item in value
        )

    if isinstance(value, dict):
        return {
            key: _apply_glossary_recursive(
                item,
                glossary=glossary,
                seen=seen,
            )
            for key, item in value.items()
        }

    return value


def apply_terminology_text(
    text: str,
    *,
    lang: str,
    mode: str | None = None,
) -> str:
    if (
        lang != "ko"
        or not text
    ):
        return text

    selected = (
        mode
        or get_terminology_mode()
    )

    if selected != "bilingual":
        return text

    glossary = _glossary_for_text(
        text
    )

    return _apply_glossary_recursive(
        text,
        glossary=glossary,
        seen=set(),
    )


def apply_terminology(
    value: Any,
    *,
    lang: str,
    mode: str | None = None,
):
    """Apply one smart glossary to the whole visible bundle.

    Important: glossary extraction happens once for the entire nested result,
    not once for every sentence.
    """
    if lang != "ko":
        return value

    selected = (
        mode
        or get_terminology_mode()
    )

    if selected != "bilingual":
        return value

    combined_text = _collect_strings(
        value
    )

    if not combined_text:
        return value

    glossary = _glossary_for_text(
        combined_text
    )

    return _apply_glossary_recursive(
        value,
        glossary=glossary,
        seen=set(),
    )
