"""Scientific terminology presentation for LALSTUDY.

Design principle
----------------
Language and scientific-term notation are separate preferences.

- UI language: Korean / English
- Scientific terms in Korean UI:
    1) English only
    2) English + 한국어 병행

Stored AI/cache/database content is NOT duplicated by terminology mode.
This module is a presentation layer, so switching the option does not create
a second paper cache or a second Method Wiki record.

The bilingual mode annotates the first useful occurrence of known scientific
terms as `English (한국어)`. Existing English-first content remains canonical.
"""

from __future__ import annotations

import re
from typing import Any

import streamlit as st


TERM_MODE_OPTIONS = {
    "English only": "en_only",
    "English + 한국어 병행": "bilingual",
}

DEFAULT_TERM_MODE_LABEL = "English + 한국어 병행"


# Curated high-frequency life-science vocabulary.
# Keep canonical technical names in English; Korean is a learning aid.
# Longer/more specific phrases are handled before shorter ones.
TERM_PAIRS = [
    # Experimental methods
    ("single-cell RNA sequencing", "단일세포 RNA 시퀀싱", ["단일세포 RNA 시퀀싱", "단일세포 RNA 염기서열분석"]),
    ("single-cell RNA-seq", "단일세포 RNA 시퀀싱", ["단일세포 RNA-seq"]),
    ("scRNA-seq", "단일세포 RNA 시퀀싱", ["단일세포 RNA-seq"]),
    ("bulk RNA sequencing", "벌크 RNA 시퀀싱", ["벌크 RNA 시퀀싱"]),
    ("RNA sequencing", "RNA 시퀀싱", ["RNA 시퀀싱", "RNA 염기서열분석"]),
    ("RNA-seq", "RNA 시퀀싱", ["RNA-seq"]),
    ("Flow cytometry", "유세포분석", ["유세포분석", "유세포 분석"]),
    ("fluorescence-activated cell sorting", "형광활성세포분류", ["형광활성세포분류", "형광 활성 세포 분류"]),
    ("FACS", "형광활성세포분류", ["형광활성세포분류"]),
    ("mass cytometry", "질량세포분석", ["질량세포분석", "질량 세포분석"]),
    ("Western blotting", "웨스턴 블로팅", ["웨스턴 블로팅", "웨스턴블롯", "웨스턴 블롯"]),
    ("Western blot", "웨스턴 블롯", ["웨스턴 블롯", "웨스턴블롯"]),
    ("immunofluorescence", "면역형광", ["면역형광", "면역 형광"]),
    ("immunohistochemistry", "면역조직화학", ["면역조직화학", "면역 조직 화학"]),
    ("confocal microscopy", "공초점 현미경", ["공초점 현미경", "공초점현미경"]),
    ("electron microscopy", "전자현미경", ["전자현미경", "전자 현미경"]),
    ("qPCR", "정량 PCR", ["정량 PCR", "정량적 PCR", "실시간 PCR"]),
    ("RT-qPCR", "역전사 정량 PCR", ["역전사 정량 PCR", "역전사 qPCR"]),
    ("RT-PCR", "역전사 PCR", ["역전사 PCR"]),
    ("PCR", "중합효소연쇄반응", ["중합효소연쇄반응", "중합효소 연쇄 반응"]),
    ("ELISA", "효소면역측정법", ["효소면역측정법", "효소 면역 측정법"]),
    ("co-immunoprecipitation", "공동면역침강", ["공동면역침강", "공동 면역 침강"]),
    ("Co-IP", "공동면역침강", ["공동면역침강"]),
    ("immunoprecipitation", "면역침강", ["면역침강", "면역 침강"]),
    ("ATAC-seq", "염색질 접근성 시퀀싱", ["염색질 접근성 시퀀싱"]),
    ("ChIP-seq", "염색질 면역침강 시퀀싱", ["염색질 면역침강 시퀀싱"]),
    ("CRISPR-Cas9", "CRISPR-Cas9 유전자편집", ["CRISPR-Cas9 유전자편집", "CRISPR-Cas9 유전자 편집"]),
    ("CRISPR", "CRISPR 유전자편집", ["CRISPR 유전자편집", "CRISPR 유전자 편집"]),
    ("luciferase assay", "루시퍼레이스 분석", ["루시퍼레이스 분석", "루시퍼레이스 어세이"]),
    ("reporter assay", "리포터 분석", ["리포터 분석", "리포터 어세이"]),
    ("cell viability assay", "세포 생존율 분석", ["세포 생존율 분석"]),
    ("cytotoxicity assay", "세포독성 분석", ["세포독성 분석"]),
    ("colony formation assay", "집락형성 분석", ["집락형성 분석", "콜로니 형성 분석"]),
    ("migration assay", "세포 이동 분석", ["세포 이동 분석"]),
    ("invasion assay", "세포 침윤 분석", ["세포 침윤 분석"]),
    ("organoid", "오가노이드", ["오가노이드"]),
    ("xenograft", "이종이식 모델", ["이종이식 모델", "이종이식"]),
    ("cell line", "세포주", ["세포주"]),
    ("primary cells", "일차세포", ["일차세포", "일차 세포"]),

    # Immunology
    ("regulatory T cell", "조절 T세포", ["조절 T세포", "조절 T 세포"]),
    ("regulatory T cells", "조절 T세포", ["조절 T세포", "조절 T 세포"]),
    ("Treg", "조절 T세포", ["조절 T세포"]),
    ("CD4+ T cell", "CD4+ T세포", ["CD4+ T세포", "CD4+ T 세포"]),
    ("CD8+ T cell", "CD8+ T세포", ["CD8+ T세포", "CD8+ T 세포"]),
    ("T cell", "T세포", ["T세포", "T 세포"]),
    ("T cells", "T세포", ["T세포", "T 세포"]),
    ("B cell", "B세포", ["B세포", "B 세포"]),
    ("B cells", "B세포", ["B세포", "B 세포"]),
    ("NK cell", "자연살해세포", ["자연살해세포", "자연 살해 세포"]),
    ("natural killer cell", "자연살해세포", ["자연살해세포", "자연 살해 세포"]),
    ("macrophage", "대식세포", ["대식세포", "대식 세포"]),
    ("dendritic cell", "수지상세포", ["수지상세포", "수지상 세포"]),
    ("neutrophil", "호중구", ["호중구"]),
    ("cytokine", "사이토카인", ["사이토카인"]),
    ("chemokine", "케모카인", ["케모카인"]),
    ("antigen", "항원", ["항원"]),
    ("antibody", "항체", ["항체"]),
    ("immune checkpoint", "면역관문", ["면역관문", "면역 관문"]),
    ("immune response", "면역반응", ["면역반응", "면역 반응"]),
    ("innate immunity", "선천면역", ["선천면역", "선천 면역"]),
    ("adaptive immunity", "적응면역", ["적응면역", "적응 면역"]),

    # Cell / molecular biology
    ("apoptotic stress", "세포자멸사 스트레스", ["세포자멸사 스트레스"]),
    ("apoptosis", "세포자멸사", ["세포자멸사", "세포 자멸사"]),
    ("necrosis", "괴사", ["괴사"]),
    ("autophagy", "자가포식", ["자가포식", "자가 포식"]),
    ("senescence", "세포노화", ["세포노화", "세포 노화"]),
    ("proliferation", "증식", ["증식"]),
    ("differentiation", "분화", ["분화"]),
    ("activation", "활성화", ["활성화"]),
    ("cell cycle", "세포주기", ["세포주기", "세포 주기"]),
    ("cell death", "세포사멸", ["세포사멸", "세포 사멸"]),
    ("DNA damage response", "DNA 손상 반응", ["DNA 손상 반응"]),
    ("oxidative stress", "산화 스트레스", ["산화 스트레스"]),
    ("endoplasmic reticulum stress", "소포체 스트레스", ["소포체 스트레스"]),
    ("ER stress", "소포체 스트레스", ["소포체 스트레스"]),
    ("unfolded protein response", "미접힘단백질반응", ["미접힘단백질반응", "미접힘 단백질 반응"]),
    ("mitochondrial membrane potential", "미토콘드리아 막전위", ["미토콘드리아 막전위", "미토콘드리아 막 전위"]),
    ("signal transduction", "신호전달", ["신호전달", "신호 전달"]),
    ("signaling pathway", "신호전달경로", ["신호전달경로", "신호 전달 경로"]),
    ("receptor", "수용체", ["수용체"]),
    ("ligand", "리간드", ["리간드"]),
    ("transcription factor", "전사인자", ["전사인자", "전사 인자"]),
    ("transcription", "전사", ["전사"]),
    ("translation", "번역", ["번역"]),
    ("phosphorylation", "인산화", ["인산화"]),
    ("dephosphorylation", "탈인산화", ["탈인산화"]),
    ("ubiquitination", "유비퀴틴화", ["유비퀴틴화"]),
    ("methylation", "메틸화", ["메틸화"]),
    ("acetylation", "아세틸화", ["아세틸화"]),
    ("gene expression", "유전자 발현", ["유전자 발현"]),
    ("protein expression", "단백질 발현", ["단백질 발현"]),
    ("overexpression", "과발현", ["과발현"]),
    ("knockdown", "발현억제", ["발현억제", "발현 억제"]),
    ("knockout", "유전자결손", ["유전자결손", "유전자 결손"]),
    ("loss-of-function", "기능상실", ["기능상실", "기능 상실"]),
    ("gain-of-function", "기능획득", ["기능획득", "기능 획득"]),
    ("wild-type", "야생형", ["야생형"]),
    ("mutation", "돌연변이", ["돌연변이"]),
    ("promoter", "프로모터", ["프로모터"]),
    ("enhancer", "인핸서", ["인핸서"]),
    ("epigenetic", "후성유전학적", ["후성유전학적", "후성 유전학적"]),

    # Omics / analysis
    ("differential gene expression", "차등 유전자 발현", ["차등 유전자 발현"]),
    ("differential expression", "차등발현", ["차등발현", "차등 발현"]),
    ("gene set enrichment analysis", "유전자집합 풍부도 분석", ["유전자집합 풍부도 분석", "유전자 집합 풍부도 분석"]),
    ("GSEA", "유전자집합 풍부도 분석", ["유전자집합 풍부도 분석"]),
    ("pathway enrichment", "경로 풍부도 분석", ["경로 풍부도 분석"]),
    ("transcriptome", "전사체", ["전사체"]),
    ("proteome", "단백질체", ["단백질체"]),
    ("epigenome", "후성유전체", ["후성유전체"]),
    ("single-cell", "단일세포", ["단일세포", "단일 세포"]),
    ("principal component analysis", "주성분분석", ["주성분분석", "주성분 분석"]),
    ("PCA", "주성분분석", ["주성분분석"]),
    ("UMAP", "UMAP 차원축소", ["UMAP 차원축소", "UMAP 차원 축소"]),
    ("clustering", "군집화", ["군집화"]),
    ("dimensionality reduction", "차원축소", ["차원축소", "차원 축소"]),
]


def _pair_records():
    records = []
    for english, korean, aliases in TERM_PAIRS:
        records.append(
            {
                "english": english,
                "korean": korean,
                "aliases": list(dict.fromkeys([korean] + list(aliases))),
            }
        )
    return records


_RECORDS = _pair_records()


def terminology_selector(lang: str) -> str:
    """Render the global terminology selector under Language."""
    if "lalstudy_terminology_label" not in st.session_state:
        st.session_state["lalstudy_terminology_label"] = DEFAULT_TERM_MODE_LABEL

    # Scientific-term notation is only relevant to Korean prose.
    if lang != "ko":
        return get_terminology_mode()

    label = st.sidebar.selectbox(
        "🔬 Scientific terms",
        list(TERM_MODE_OPTIONS.keys()),
        key="lalstudy_terminology_label",
    )
    return TERM_MODE_OPTIONS.get(label, "bilingual")


def get_terminology_mode() -> str:
    label = st.session_state.get(
        "lalstudy_terminology_label",
        DEFAULT_TERM_MODE_LABEL,
    )
    return TERM_MODE_OPTIONS.get(label, "bilingual")


def _inside_parentheses(text: str, index: int) -> bool:
    left_open = text.rfind("(", 0, index)
    left_close = text.rfind(")", 0, index)
    return left_open > left_close


def _has_korean_parenthetical_immediately_after(text: str, end: int) -> bool:
    tail = text[end : end + 60]
    return bool(
        re.match(
            r"\s*\([^)]*[가-힣][^)]*\)",
            tail,
        )
    )


def _english_pattern():
    terms = sorted(
        {r["english"] for r in _RECORDS},
        key=len,
        reverse=True,
    )
    return re.compile(
        r"(?<![A-Za-z0-9])("
        + "|".join(re.escape(t) for t in terms)
        + r")(?![A-Za-z0-9])",
        flags=re.IGNORECASE,
    )


_ENGLISH_PATTERN = _english_pattern()

_ENGLISH_LOOKUP = {
    r["english"].casefold(): r
    for r in _RECORDS
}


def _korean_pattern():
    aliases = []
    lookup = {}
    for record in _RECORDS:
        for alias in record["aliases"]:
            alias = (alias or "").strip()
            if not alias:
                continue
            aliases.append(alias)
            lookup[alias] = record

    aliases = sorted(
        set(aliases),
        key=len,
        reverse=True,
    )
    if not aliases:
        return None, {}

    pattern = re.compile(
        "("
        + "|".join(re.escape(a) for a in aliases)
        + ")"
    )
    return pattern, lookup


_KOREAN_PATTERN, _KOREAN_LOOKUP = _korean_pattern()


def bilingualize_text(text: str) -> str:
    """Annotate the first meaningful occurrence of known terms."""
    if not text:
        return text

    seen = set()

    def replace_english(match):
        original = match.group(0)
        record = _ENGLISH_LOOKUP.get(
            original.casefold()
        )
        if not record:
            return original

        canonical = record["english"].casefold()

        if canonical in seen:
            return original

        seen.add(canonical)

        if _has_korean_parenthetical_immediately_after(
            match.string,
            match.end(),
        ):
            return original

        return f"{original} ({record['korean']})"

    out = _ENGLISH_PATTERN.sub(
        replace_english,
        text,
    )

    if _KOREAN_PATTERN is None:
        return out

    def replace_korean(match):
        original = match.group(0)
        record = _KOREAN_LOOKUP.get(original)
        if not record:
            return original

        canonical = record["english"].casefold()

        if canonical in seen:
            return original

        if _inside_parentheses(
            match.string,
            match.start(),
        ):
            return original

        seen.add(canonical)
        return f"{record['english']} ({record['korean']})"

    return _KOREAN_PATTERN.sub(
        replace_korean,
        out,
    )


def apply_terminology_text(
    text: str,
    *,
    lang: str,
    mode: str | None = None,
) -> str:
    if lang != "ko":
        return text

    selected = mode or get_terminology_mode()

    if selected != "bilingual":
        return text

    return bilingualize_text(text)


def apply_terminology(
    value: Any,
    *,
    lang: str,
    mode: str | None = None,
):
    """Recursively apply presentation terminology without mutating stored data."""
    if lang != "ko":
        return value

    selected = mode or get_terminology_mode()

    if selected != "bilingual":
        return value

    if isinstance(value, str):
        return bilingualize_text(value)

    if isinstance(value, list):
        return [
            apply_terminology(
                item,
                lang=lang,
                mode=selected,
            )
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            apply_terminology(
                item,
                lang=lang,
                mode=selected,
            )
            for item in value
        )

    if isinstance(value, dict):
        return {
            key: apply_terminology(
                item,
                lang=lang,
                mode=selected,
            )
            for key, item in value.items()
        }

    return value
