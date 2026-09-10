import io
import json
import os
import re
import html
import hashlib
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import streamlit as st
from pypdf import PdfReader

from i18n import language_selector, L
from ai_engine import (
    analyze_core,
    analyze_prerequisites,
    analyze_experiments,
    analyze_figures,
    analyze_critical_learning,
    StageCallError,
    sdk_available,
    TEXT_MODELS,
    FIGURE_MODELS,
)

from figure_in_study import (
    extract_study_figures,
    find_matching_figure,
    pymupdf_available,
)

from mineru_figure_extractor import (
    extract_figures_with_mineru,
    mineru_available,
)

APP_VERSION = "v0.2.5.4-beta"
METHOD_PROFILE_FILE = Path("method_profiles.json")

st.set_page_config(
    page_title="LALSTUDY · Learn a Paper",
    page_icon="📄",
    layout="wide",
)


# ============================================================
# LOCAL DATA / PDF
# ============================================================

def clean_text(text):
    text = html.unescape(text or "")
    text = text.replace("\x00", " ")
    text = re.sub(r"-\s*\n\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


@st.cache_data
def load_profiles():
    if not METHOD_PROFILE_FILE.exists():
        return []

    return json.loads(
        METHOD_PROFILE_FILE.read_text(
            encoding="utf-8"
        )
    )


profiles = load_profiles()

profiles_by_name = {
    p["name"]: p
    for p in profiles
}

method_alias_index = {}
method_terms = []

for profile in profiles:
    canonical = profile.get("name", "")
    aliases = profile.get("aliases", [])

    for term in [canonical] + aliases:
        if not term:
            continue

        method_terms.append(
            (term, canonical)
        )

        method_alias_index[
            term.lower().strip()
        ] = canonical


def detect_methods(text):
    out = Counter()

    for term, canonical in method_terms:
        pattern = (
            r"(?<![A-Za-z0-9])"
            + re.escape(term)
            + r"(?![A-Za-z0-9])"
        )

        count = len(
            re.findall(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
        )

        if count:
            out[canonical] += count

    return out


def canonical_method_match(name):
    if not name:
        return None

    query = name.lower().strip()

    if query in method_alias_index:
        return method_alias_index[
            query
        ]

    candidates = []

    for alias, canonical in (
        method_alias_index.items()
    ):
        if (
            query in alias
            or alias in query
        ):
            candidates.append(
                (
                    len(alias),
                    canonical,
                )
            )

    if candidates:
        candidates.sort(
            reverse=True
        )
        return candidates[0][1]

    best = None
    best_score = 0.0

    for alias, canonical in (
        method_alias_index.items()
    ):
        score = SequenceMatcher(
            None,
            query,
            alias,
        ).ratio()

        if score > best_score:
            best_score = score
            best = canonical

    return (
        best
        if best_score >= 0.82
        else None
    )


@st.cache_data(show_spinner=False)
def extract_pdf_text(file_bytes):
    reader = PdfReader(
        io.BytesIO(file_bytes)
    )

    pages = []

    for i, page in enumerate(
        reader.pages
    ):
        try:
            text = (
                page.extract_text()
                or ""
            )
        except Exception:
            text = ""

        pages.append(
            {
                "page": i + 1,
                "text": text,
            }
        )

    return (
        pages,
        "\n".join(
            x["text"]
            for x in pages
        ),
    )


@st.cache_data(show_spinner=False)
def get_study_figures(file_bytes, paper_hash):
    return extract_study_figures(
        pdf_bytes=file_bytes,
        paper_hash=paper_hash,
    )


def get_server_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            value = str(
                st.secrets[
                    "GEMINI_API_KEY"
                ]
            ).strip()

            if value:
                return value
    except Exception:
        pass

    return os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()


def get_mineru_token():
    try:
        if "MINERU_TOKEN" in st.secrets:
            value = str(
                st.secrets[
                    "MINERU_TOKEN"
                ]
            ).strip()

            if value:
                return value
    except Exception:
        pass

    return os.getenv(
        "MINERU_TOKEN",
        "",
    ).strip()


# ============================================================
# STATE
# ============================================================

def active_hash():
    return st.session_state.get(
        "lalstudy_active_paper_hash",
        "",
    )


def stage_key(stage, depth):
    return (
        f"lal_v023:{active_hash()}:"
        f"{depth}:{stage}"
    )


def get_stage(stage, depth):
    return st.session_state.get(
        stage_key(stage, depth)
    )


def set_stage(
    stage,
    depth,
    result,
    model,
):
    st.session_state[
        stage_key(stage, depth)
    ] = {
        "data": result.model_dump(),
        "model": model,
    }


def clear_current_paper():
    current_hash = active_hash()

    for key in list(
        st.session_state.keys()
    ):
        if (
            str(key).startswith(
                "lalstudy_active_paper_"
            )
            or str(key).startswith(
                f"lal_v023:{current_hash}:"
            )
        ):
            del st.session_state[key]


# ============================================================
# UI HELPERS
# ============================================================

def selected_language_data(
    stage_record
):
    if not stage_record:
        return None

    data = stage_record.get(
        "data",
        {}
    )

    if (
        isinstance(data, dict)
        and lang in data
    ):
        return data[lang]

    return data


def difficulty_label(value):
    mapping = {
        "basic": L(
            lang,
            "기초",
            "Basic",
        ),
        "intermediate": L(
            lang,
            "중급",
            "Intermediate",
        ),
        "advanced": L(
            lang,
            "심화",
            "Advanced",
        ),
    }

    return mapping.get(
        value,
        value,
    )


def model_badge(record):
    if record:
        st.caption(
            f"AI: {record.get('model','')}"
        )


def show_stage_error(
    title,
    exc,
):
    st.error(
        L(
            lang,
            f"{title} 생성에 실패했습니다. 이미 생성된 다른 결과는 그대로 유지됩니다.",
            f"{title} generation failed. Previously generated sections are preserved.",
        )
    )

    if isinstance(
        exc,
        StageCallError,
    ):
        with st.expander(
            L(
                lang,
                "기술 정보",
                "Technical details",
            )
        ):
            for line in (
                exc.trace[-6:]
            ):
                st.code(line)
    else:
        st.caption(str(exc))


def method_jump_button(
    method_name,
    key,
    target="method",
):
    canonical = canonical_method_match(
        method_name
    )

    if not canonical:
        return

    label = (
        f"🧬 {canonical} "
        + L(
            lang,
            "사례 보기",
            "examples",
        )
    )

    if st.button(
        label,
        key=key,
        use_container_width=True,
    ):
        st.session_state[
            "lal_method_jump"
        ] = canonical

        if target == "figure":
            st.switch_page(
                "pages/3_Figure_Explorer.py"
            )
        else:
            st.switch_page(
                "pages/2_Method_Explorer.py"
            )


def logic_arrow():
    st.markdown(
        "<div style='text-align:center;font-size:1.35rem;opacity:.5'>↓</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# SIDEBAR
# ============================================================

lang = language_selector()

st.sidebar.title("LALSTUDY")
st.sidebar.caption(APP_VERSION)

depth_options = {
    L(
        lang,
        "기초부터 자세히",
        "Foundation",
    ): "foundation",
    L(
        lang,
        "생명과학 학부 수준",
        "Life-science undergraduate",
    ): "undergraduate",
    L(
        lang,
        "심화 / 대학원 수준",
        "Advanced / graduate",
    ): "advanced",
}

depth_label = st.sidebar.selectbox(
    L(
        lang,
        "설명 깊이",
        "Explanation depth",
    ),
    list(depth_options.keys()),
    index=1,
)

depth = depth_options[
    depth_label
]

if lang == "ko":
    st.sidebar.caption(
        "🧬 Korean prose + English scientific terminology"
    )

server_key = get_server_key()

if server_key:
    st.sidebar.success(
        "✨ AI service ready"
    )
else:
    st.sidebar.error(
        L(
            lang,
            "관리자 API key 미설정",
            "Server API key missing",
        )
    )

st.sidebar.caption(
    "Text: "
    + " → ".join(TEXT_MODELS)
)
st.sidebar.caption(
    "Figure: "
    + " → ".join(FIGURE_MODELS)
)


# ============================================================
# ACTIVE PAPER
# ============================================================

st.title(
    "📄 Learn a Paper · Staged Deep Study"
)

st.caption(
    L(
        lang,
        "먼저 논문의 핵심 논리만 빠르게 분석하고, 필요한 학습 모듈만 추가로 생성합니다.",
        "Start with a lightweight core analysis, then generate only the deeper modules you need.",
    )
)

uploaded = st.file_uploader(
    L(
        lang,
        "논문 PDF 업로드 / 교체",
        "Upload / replace paper PDF",
    ),
    type=["pdf"],
    key="lalstudy_pdf_uploader",
)

if uploaded is not None:
    new_bytes = uploaded.getvalue()

    new_hash = hashlib.sha256(
        new_bytes
    ).hexdigest()

    old_hash = active_hash()

    st.session_state[
        "lalstudy_active_paper_bytes"
    ] = new_bytes

    st.session_state[
        "lalstudy_active_paper_name"
    ] = uploaded.name

    st.session_state[
        "lalstudy_active_paper_hash"
    ] = new_hash

    # We deliberately do not delete the previous paper's stage cache here.
    # If the user uploads that same paper again in the same session, its
    # generated modules can be reused by hash.

pdf_bytes = st.session_state.get(
    "lalstudy_active_paper_bytes"
)

paper_name = st.session_state.get(
    "lalstudy_active_paper_name",
    "",
)

if not pdf_bytes:
    st.info(
        L(
            lang,
            "PDF를 올리면 먼저 Core Analysis를 생성합니다.",
            "Upload a PDF to begin with Core Analysis.",
        )
    )

    st.code(
        """PDF
↓
Core: Overview + Logic Map
↓
Prerequisites / Experiments / Figures / Critical Reading
(필요한 모듈만 생성)""",
        language=None,
    )

    st.stop()


with st.container(
    border=True
):
    c1, c2 = st.columns(
        [5, 1]
    )

    with c1:
        st.markdown(
            f"**{L(lang,'📌 현재 논문','📌 Active paper')}**  \n"
            f"{paper_name}"
        )

    with c2:
        if st.button(
            L(
                lang,
                "논문 닫기",
                "Clear paper",
            ),
            use_container_width=True,
        ):
            clear_current_paper()
            st.rerun()


with st.spinner(
    L(
        lang,
        "PDF text layer 확인 중...",
        "Reading PDF text layer...",
    )
):
    pages, raw_text = (
        extract_pdf_text(
            pdf_bytes
        )
    )

paper_text = clean_text(
    raw_text
)

rule_methods = detect_methods(
    paper_text
)

m1, m2, m3 = st.columns(3)

m1.metric(
    L(lang, "페이지", "Pages"),
    len(pages),
)

m2.metric(
    L(
        lang,
        "감지 method",
        "Detected methods",
    ),
    len(rule_methods),
)

m3.metric(
    L(
        lang,
        "PDF 크기",
        "PDF size",
    ),
    f"{len(pdf_bytes)/(1024*1024):.1f} MB",
)


mineru_token = get_mineru_token()

mineru_state_key = (
    "lal_mineru_figures:v5:"
    + active_hash()
)

mineru_record = st.session_state.get(
    mineru_state_key
)

if mineru_record:
    extracted_study_figures = (
        mineru_record.get(
            "figures",
            [],
        )
    )
    figure_extraction_engine = (
        mineru_record.get(
            "engine",
            "mineru_precision_vlm",
        )
    )
else:
    # We no longer run the heuristic extractor automatically.
    # It remains available as a fallback after a MinerU failure or when
    # the user explicitly chooses fallback extraction.
    extracted_study_figures = []
    figure_extraction_engine = "not_prepared"

st.caption(
    L(
        lang,
        f"Figure extraction: {figure_extraction_engine} · {len(extracted_study_figures)} figures",
        f"Figure extraction: {figure_extraction_engine} · {len(extracted_study_figures)} figures",
    )
)

if len(paper_text) < 500:
    st.warning(
        L(
            lang,
            "PDF text layer가 매우 적습니다. Figure 단계는 PDF 자체를 읽지만, 다른 단계의 품질은 낮아질 수 있습니다.",
            "The PDF has little extractable text. Figure analysis reads the PDF directly, but text-based stages may be weaker.",
        )
    )


# ============================================================
# CORE
# ============================================================

core_record = get_stage(
    "core",
    depth,
)

st.divider()

if not core_record:
    st.subheader(
        L(
            lang,
            "1️⃣ Core Analysis",
            "1️⃣ Core Analysis",
        )
    )

    st.write(
        L(
            lang,
            "처음에는 **한눈에 보기 + 논리 지도**만 생성합니다. 이전처럼 모든 분석을 한 요청에 몰아넣지 않습니다.",
            "The first request generates only the **overview + logic map** instead of forcing every analysis into one giant request.",
        )
    )

    can_run = bool(
        server_key
        and sdk_available()
        and len(paper_text) >= 200
    )

    if not server_key:
        st.error(
            L(
                lang,
                "서버 Gemini API key가 설정되지 않았습니다.",
                "Server Gemini API key is not configured.",
            )
        )

    if st.button(
        L(
            lang,
            "✨ Core Analysis 시작",
            "✨ Start Core Analysis",
        ),
        type="primary",
        use_container_width=True,
        disabled=not can_run,
    ):
        with st.spinner(
            L(
                lang,
                "논문의 핵심 질문과 논리 흐름을 분석 중...",
                "Analyzing the paper's core question and logic...",
            )
        ):
            try:
                result, model = analyze_core(
                    paper_text=paper_text,
                    api_key=server_key,
                    depth=depth,
                    detected_methods=[
                        name
                        for name, _
                        in rule_methods.most_common(25)
                    ],
                )

                set_stage(
                    "core",
                    depth,
                    result,
                    model,
                )

                st.rerun()

            except Exception as exc:
                show_stage_error(
                    "Core Analysis",
                    exc,
                )

    st.stop()


core_data = selected_language_data(
    core_record
)

overview = core_data.get(
    "overview",
    {},
)

st.success(
    L(
        lang,
        "Core Analysis 완료. 이제 필요한 심화 모듈만 선택해서 생성할 수 있습니다.",
        "Core Analysis complete. Generate only the deeper modules you need.",
    )
)
model_badge(core_record)


# ============================================================
# MODULE STATUS
# ============================================================

prereq_record = get_stage(
    "prerequisites",
    depth,
)
experiments_record = get_stage(
    "experiments",
    depth,
)
figures_record = get_stage(
    "figures",
    depth,
)
critical_record = get_stage(
    "critical_learning",
    depth,
)

st.subheader(
    L(
        lang,
        "Deep Study Modules",
        "Deep Study Modules",
    )
)

module_cols = st.columns(4)

module_info = [
    (
        module_cols[0],
        "🧠",
        L(lang, "선수지식", "Prerequisites"),
        prereq_record,
    ),
    (
        module_cols[1],
        "🔬",
        L(lang, "실험 전략", "Experiments"),
        experiments_record,
    ),
    (
        module_cols[2],
        "🖼",
        "Figures",
        figures_record,
    ),
    (
        module_cols[3],
        "🧐",
        L(
            lang,
            "비판적 읽기",
            "Critical Reading",
        ),
        critical_record,
    ),
]

for col, icon, label, record in (
    module_info
):
    with col:
        with st.container(
            border=True
        ):
            st.markdown(
                f"### {icon} {label}"
            )

            if record:
                st.success(
                    L(
                        lang,
                        "생성 완료",
                        "Ready",
                    )
                )
                model_badge(record)
            else:
                st.caption(
                    L(
                        lang,
                        "아직 생성 안 함",
                        "Not generated yet",
                    )
                )


# ============================================================
# TABS
# ============================================================

tabs = st.tabs(
    [
        L(
            lang,
            "🎯 한눈에 보기",
            "🎯 Overview",
        ),
        L(
            lang,
            "🧭 논리 지도",
            "🧭 Logic Map",
        ),
        L(
            lang,
            "🧠 선수지식",
            "🧠 Prerequisites",
        ),
        L(
            lang,
            "🔬 실험 전략",
            "🔬 Experiments",
        ),
        "🖼 Figures",
        L(
            lang,
            "🧐 비판적 읽기 + 다음 학습",
            "🧐 Critical Reading + Learn Next",
        ),
    ]
)


# ============================================================
# OVERVIEW
# ============================================================

with tabs[0]:
    st.header(
        overview.get(
            "title",
            paper_name,
        )
    )

    st.info(
        overview.get(
            "one_sentence_takeaway",
            "",
        )
    )

    left, right = st.columns(2)

    with left:
        st.markdown(
            f"### {L(lang,'❓ 연구 질문','❓ Research question')}"
        )
        st.write(
            overview.get(
                "research_question",
                "",
            )
        )

        st.markdown(
            "### 🕳 Knowledge gap"
        )
        st.write(
            overview.get(
                "knowledge_gap",
                "",
            )
        )

        st.markdown(
            "### 🧪 Hypothesis"
        )
        st.write(
            overview.get(
                "hypothesis",
                "",
            )
        )

    with right:
        st.markdown(
            f"### {L(lang,'🌍 왜 중요한가','🌍 Why it matters')}"
        )
        st.write(
            overview.get(
                "why_it_matters",
                "",
            )
        )

        st.markdown(
            f"### {L(lang,'✨ 새로움','✨ Novelty')}"
        )
        st.write(
            overview.get(
                "novelty",
                "",
            )
        )

        st.markdown(
            f"### {L(lang,'🏁 결론','🏁 Conclusion')}"
        )
        st.write(
            overview.get(
                "conclusion",
                "",
            )
        )

    st.caption(
        f"{L(lang,'분야','Field')}: "
        + overview.get(
            "field",
            "-",
        )
    )


# ============================================================
# LOGIC MAP
# ============================================================

with tabs[1]:
    st.header(
        L(
            lang,
            "🧭 논문의 논리 지도",
            "🧭 Paper Logic Map",
        )
    )

    st.caption(
        L(
            lang,
            "결과를 나열하는 대신 왜 다음 실험으로 넘어가는지 따라갑니다.",
            "Follow why the paper moves from one experiment to the next.",
        )
    )

    logic_map = core_data.get(
        "logic_map",
        [],
    )

    for i, step in enumerate(
        logic_map
    ):
        with st.container(
            border=True
        ):
            st.markdown(
                f"### {step.get('order',i+1)}. "
                f"{step.get('question','')}"
            )

            c1, c2 = st.columns(2)

            with c1:
                st.markdown(
                    f"**{L(lang,'실험 / 분석','Experiment / analysis')}**"
                )
                st.write(
                    step.get(
                        "experiment_or_analysis",
                        "",
                    )
                )

                st.markdown(
                    f"**{L(lang,'직접 관찰','Direct observation')}**"
                )
                st.write(
                    step.get(
                        "observation",
                        "",
                    )
                )

            with c2:
                st.markdown(
                    f"**{L(lang,'해석 / 추론','Inference')}**"
                )
                st.write(
                    step.get(
                        "inference",
                        "",
                    )
                )

                st.caption(
                    f"{L(lang,'근거','Evidence')}: "
                    + step.get(
                        "evidence_location",
                        "",
                    )
                )

        if i < len(logic_map) - 1:
            logic_arrow()


# ============================================================
# PREREQUISITES
# ============================================================

with tabs[2]:
    st.header(
        L(
            lang,
            "🧠 이 논문을 이해하기 위한 선수지식",
            "🧠 Prerequisites",
        )
    )

    if not prereq_record:
        st.write(
            L(
                lang,
                "이 모듈은 아직 API를 호출하지 않았습니다.",
                "This module has not called the API yet.",
            )
        )

        if st.button(
            L(
                lang,
                "🧠 선수지식 생성",
                "🧠 Generate prerequisites",
            ),
            type="primary",
            key="generate_prerequisites",
        ):
            with st.spinner(
                L(
                    lang,
                    "이 논문에서 실제로 필요한 선수지식을 선별 중...",
                    "Selecting the prerequisites that actually unlock this paper...",
                )
            ):
                try:
                    result, model = (
                        analyze_prerequisites(
                            paper_text=paper_text,
                            core_bundle=core_record["data"],
                            api_key=server_key,
                            depth=depth,
                        )
                    )

                    set_stage(
                        "prerequisites",
                        depth,
                        result,
                        model,
                    )

                    st.rerun()

                except Exception as exc:
                    show_stage_error(
                        L(
                            lang,
                            "선수지식",
                            "Prerequisites",
                        ),
                        exc,
                    )

    else:
        data = selected_language_data(
            prereq_record
        )

        model_badge(
            prereq_record
        )

        for concept in data.get(
            "prerequisites",
            [],
        ):
            with st.expander(
                f"{concept.get('name','')} · "
                f"{difficulty_label(concept.get('difficulty',''))}"
            ):
                st.markdown(
                    f"**{L(lang,'왜 알아야 하나?','Why do I need this?')}**"
                )
                st.write(
                    concept.get(
                        "why_needed",
                        "",
                    )
                )

                st.markdown(
                    f"**{L(lang,'배경지식','Background')}**"
                )
                st.write(
                    concept.get(
                        "explanation",
                        "",
                    )
                )

                st.markdown(
                    f"**{L(lang,'이 논문에서는','In this paper')}**"
                )
                st.write(
                    concept.get(
                        "paper_context",
                        "",
                    )
                )

                if concept.get(
                    "prerequisites"
                ):
                    st.markdown(
                        f"**{L(lang,'먼저 알면 좋은 것','Learn first')}**"
                    )
                    st.write(
                        " → ".join(
                            concept[
                                "prerequisites"
                            ]
                        )
                    )


# ============================================================
# EXPERIMENTS
# ============================================================

with tabs[3]:
    st.header(
        "🔬 Experimental Strategy"
    )

    if not experiments_record:
        st.write(
            L(
                lang,
                "핵심 실험의 What/Why/Readout을 필요할 때만 생성합니다.",
                "Generate What/Why/Readout cards only when you need them.",
            )
        )

        if st.button(
            L(
                lang,
                "🔬 실험 전략 생성",
                "🔬 Generate experiment analysis",
            ),
            type="primary",
            key="generate_experiments",
        ):
            with st.spinner(
                L(
                    lang,
                    "핵심 실험과 각 실험의 역할을 분석 중...",
                    "Analyzing the major experiments and why they were used...",
                )
            ):
                try:
                    result, model = (
                        analyze_experiments(
                            paper_text=paper_text,
                            core_bundle=core_record["data"],
                            api_key=server_key,
                            detected_methods=[
                                name
                                for name, _
                                in rule_methods.most_common(30)
                            ],
                        )
                    )

                    set_stage(
                        "experiments",
                        depth,
                        result,
                        model,
                    )

                    st.rerun()

                except Exception as exc:
                    show_stage_error(
                        L(
                            lang,
                            "실험 전략",
                            "Experiments",
                        ),
                        exc,
                    )

    else:
        data = selected_language_data(
            experiments_record
        )

        model_badge(
            experiments_record
        )

        for idx, exp in enumerate(
            data.get(
                "experiments",
                [],
            )
        ):
            method = exp.get(
                "method",
                "Method",
            )

            with st.container(
                border=True
            ):
                st.subheader(
                    method
                )

                c1, c2 = st.columns(2)

                with c1:
                    st.markdown(
                        f"**{L(lang,'질문','Scientific question')}**"
                    )
                    st.write(
                        exp.get(
                            "scientific_question",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'샘플 / 모델','Sample / model')}**"
                    )
                    st.write(
                        exp.get(
                            "sample_or_model",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'조작 / 비교','Manipulation / comparison')}**"
                    )
                    st.write(
                        exp.get(
                            "manipulated_variable",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'Readout','Readout')}**"
                    )
                    st.write(
                        exp.get(
                            "readout",
                            "",
                        )
                    )

                with c2:
                    st.markdown(
                        f"**{L(lang,'왜 이 method인가?','Why this method?')}**"
                    )
                    st.write(
                        exp.get(
                            "why_this_method",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'무엇을 지지하나','What it supports')}**"
                    )
                    st.write(
                        exp.get(
                            "result_meaning",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'한계','Limitation')}**"
                    )
                    st.write(
                        exp.get(
                            "limitation",
                            "",
                        )
                    )

                    st.caption(
                        f"{L(lang,'근거','Evidence')}: "
                        + exp.get(
                            "evidence_location",
                            "",
                        )
                    )

                canonical = canonical_method_match(
                    method
                )

                if canonical:
                    b1, b2 = st.columns(2)

                    with b1:
                        method_jump_button(
                            canonical,
                            key=f"method_{idx}",
                            target="method",
                        )

                    with b2:
                        method_jump_button(
                            canonical,
                            key=f"figure_{idx}",
                            target="figure",
                        )


# ============================================================
# FIGURES
# ============================================================

with tabs[4]:
    st.header(
        "🖼 Figure-by-Figure"
    )

    st.caption(
        L(
            lang,
            "v0.2.5.4는 MinerU를 caption detector로 사용하고, multi-panel body bbox가 불완전하면 원본 PDF의 caption 위 전체 visual region을 자동 crop하는 hybrid mode를 사용합니다.",
            "v0.2.5.4 uses MinerU as a semantic caption detector and automatically switches to a caption-anchored original-PDF crop when a multi-panel body bbox looks incomplete.",
        )
    )

    # --------------------------------------------------------
    # EXTRACTION ENGINE STATUS
    # --------------------------------------------------------

    status_cols = st.columns(3)

    with status_cols[0]:
        st.metric(
            "MinerU SDK",
            "Ready"
            if mineru_available()
            else "Missing",
        )

    with status_cols[1]:
        st.metric(
            "MinerU token",
            "Connected"
            if mineru_token
            else "Missing",
        )

    with status_cols[2]:
        st.metric(
            L(
                lang,
                "추출된 Figure",
                "Extracted figures",
            ),
            len(
                extracted_study_figures
            ),
        )

    if extracted_study_figures:
        st.success(
            L(
                lang,
                f"Figure engine: {figure_extraction_engine}",
                f"Figure engine: {figure_extraction_engine}",
            )
        )

        if (
            mineru_available()
            and mineru_token
            and st.button(
                L(
                    lang,
                    "🔄 MinerU Figure 강제 재추출",
                    "🔄 Force re-extract MinerU Figures",
                ),
                use_container_width=True,
                key="force_reextract_mineru_v3",
            )
        ):
            with st.spinner(
                L(
                    lang,
                    "기존 Figure cache를 버리고 middle.json 기반으로 다시 추출 중...",
                    "Discarding old Figure cache and re-extracting from MinerU middle.json...",
                )
            ):
                try:
                    figures = extract_figures_with_mineru(
                        pdf_bytes=pdf_bytes,
                        paper_hash=active_hash(),
                        token=mineru_token,
                        language="en",
                        force=True,
                    )

                    st.session_state[
                        mineru_state_key
                    ] = {
                        "engine": "mineru_hybrid_v5",
                        "figures": figures,
                    }

                    st.rerun()

                except Exception as exc:
                    st.error(
                        f"Forced MinerU extraction failed: {exc}"
                    )

        with st.expander(
            L(
                lang,
                "🔎 추출 결과 확인",
                "🔎 Inspect extraction",
            ),
            expanded=False,
        ):
            for item in (
                extracted_study_figures
            ):
                st.markdown(
                    f"### {item.get('figure_label','Figure')}"
                )

                st.caption(
                    f"page {item.get('page_number','?')} · "
                    f"{item.get('engine', figure_extraction_engine)} · "
                    f"{item.get('asset_mode','')}"
                )

                st.image(
                    item.get(
                        "image_path"
                    ),
                    use_container_width=True,
                )

                st.caption(
                    item.get(
                        "caption",
                        "",
                    )
                )

    else:
        st.info(
            L(
                lang,
                "아직 Figure extraction을 실행하지 않았습니다.",
                "Figure extraction has not been run yet.",
            )
        )

        if mineru_available() and mineru_token:
            if st.button(
                L(
                    lang,
                    "✨ MinerU Precision으로 Figure 추출",
                    "✨ Extract Figures with MinerU Precision",
                ),
                type="primary",
                use_container_width=True,
                key="run_mineru_figures",
            ):
                with st.spinner(
                    L(
                        lang,
                        "MinerU VLM이 PDF layout을 분석하고 Figure 영역을 추출 중입니다. 첫 실행은 시간이 걸릴 수 있습니다...",
                        "MinerU VLM is analyzing the PDF layout and extracting Figure regions. The first run may take a while...",
                    )
                ):
                    try:
                        figures = (
                            extract_figures_with_mineru(
                                pdf_bytes=pdf_bytes,
                                paper_hash=active_hash(),
                                token=mineru_token,
                                language="en",
                                force=False,
                            )
                        )

                        if not figures:
                            raise RuntimeError(
                                "MinerU completed parsing but no main Figure captions/images were matched."
                            )

                        st.session_state[
                            mineru_state_key
                        ] = {
                            "engine": "mineru_hybrid_v5",
                            "figures": figures,
                        }

                        st.rerun()

                    except Exception as exc:
                        st.error(
                            L(
                                lang,
                                f"MinerU extraction 실패: {exc}",
                                f"MinerU extraction failed: {exc}",
                            )
                        )

        elif not mineru_token:
            st.warning(
                L(
                    lang,
                    "MinerU Precision을 쓰려면 서버에 `MINERU_TOKEN`을 한 번 설정해야 합니다. 그 전에는 아래 fallback을 사용할 수 있습니다.",
                    "MinerU Precision needs a server-side `MINERU_TOKEN`. Until then, you can use the fallback below.",
                )
            )

        if st.button(
            L(
                lang,
                "↩ PyMuPDF fallback으로 추출",
                "↩ Extract with PyMuPDF fallback",
            ),
            use_container_width=True,
            key="run_fallback_figures",
        ):
            with st.spinner(
                L(
                    lang,
                    "Fallback Figure extraction 중...",
                    "Running fallback Figure extraction...",
                )
            ):
                try:
                    figures = get_study_figures(
                        pdf_bytes,
                        active_hash(),
                    )

                    st.session_state[
                        mineru_state_key
                    ] = {
                        "engine": "pymupdf_fallback_v2",
                        "figures": figures,
                    }

                    st.rerun()

                except Exception as exc:
                    st.error(
                        f"Fallback extraction failed: {exc}"
                    )

    # --------------------------------------------------------
    # AI FIGURE INTERPRETATION
    # --------------------------------------------------------

    st.divider()
    st.subheader(
        L(
            lang,
            "AI Figure Interpretation",
            "AI Figure Interpretation",
        )
    )

    if not extracted_study_figures:
        st.caption(
            L(
                lang,
                "먼저 위에서 Figure 이미지를 준비하는 것을 권장합니다.",
                "Prepare the Figure images above first.",
            )
        )

    if not figures_record:
        if st.button(
            L(
                lang,
                "🧠 Figure 해석 생성",
                "🧠 Generate Figure interpretation",
            ),
            type="primary",
            use_container_width=True,
            key="generate_figures",
        ):
            with st.spinner(
                L(
                    lang,
                    "Gemini가 논문의 Figure 논리를 분석 중...",
                    "Gemini is analyzing the Figure logic...",
                )
            ):
                try:
                    result, model = (
                        analyze_figures(
                            pdf_bytes=pdf_bytes,
                            core_bundle=core_record["data"],
                            api_key=server_key,
                        )
                    )

                    set_stage(
                        "figures",
                        depth,
                        result,
                        model,
                    )

                    st.rerun()

                except Exception as exc:
                    show_stage_error(
                        "Figures",
                        exc,
                    )

    else:
        data = selected_language_data(
            figures_record
        )

        model_badge(
            figures_record
        )

        for f_idx, figure in enumerate(
            data.get(
                "figures",
                [],
            )
        ):
            matching_item = find_matching_figure(
                extracted_study_figures,
                figure.get(
                    "figure_label",
                    "",
                ),
            )

            with st.expander(
                f"{figure.get('figure_label','Figure')} — "
                f"{figure.get('role_in_story','')}",
                expanded=False,
            ):
                if matching_item:
                    st.image(
                        matching_item.get(
                            "image_path"
                        ),
                        caption=(
                            f"{matching_item.get('figure_label','Figure')} · "
                            f"page {matching_item.get('page_number','?')}"
                        ),
                        use_container_width=True,
                    )

                    with st.expander(
                        L(
                            lang,
                            "원문 caption",
                            "Source caption",
                        ),
                        expanded=False,
                    ):
                        st.write(
                            matching_item.get(
                                "caption",
                                "",
                            )
                        )

                elif extracted_study_figures:
                    st.warning(
                        L(
                            lang,
                            "AI Figure label과 추출 이미지의 자동 매칭에 실패했습니다.",
                            "Could not automatically match the AI Figure label to an extracted image.",
                        )
                    )

                st.markdown(
                    f"### {L(lang,'❓ 핵심 질문','❓ Main question')}"
                )

                st.write(
                    figure.get(
                        "main_question",
                        "",
                    )
                )

                panels = figure.get(
                    "panels",
                    [],
                )

                if panels:
                    labels = [
                        panel.get(
                            "panel_label",
                            f"Panel {i+1}",
                        )
                        for i, panel in enumerate(
                            panels
                        )
                    ]

                    panel_tabs = st.tabs(
                        labels
                    )

                    for i, panel in enumerate(
                        panels
                    ):
                        with panel_tabs[i]:
                            c1, c2 = st.columns(
                                2
                            )

                            with c1:
                                st.markdown(
                                    "**WHAT**"
                                )
                                st.write(
                                    panel.get(
                                        "what",
                                        "",
                                    )
                                )

                                st.markdown(
                                    "**HOW**"
                                )
                                st.write(
                                    panel.get(
                                        "how",
                                        "",
                                    )
                                )

                            with c2:
                                st.markdown(
                                    "**RESULT**"
                                )
                                st.write(
                                    panel.get(
                                        "result",
                                        "",
                                    )
                                )

                                st.markdown(
                                    "**INTERPRETATION**"
                                )
                                st.write(
                                    panel.get(
                                        "interpretation",
                                        "",
                                    )
                                )

                            if panel.get(
                                "methods"
                            ):
                                st.caption(
                                    "Methods: "
                                    + ", ".join(
                                        panel[
                                            "methods"
                                        ]
                                    )
                                )

                st.divider()

                c1, c2 = st.columns(
                    2
                )

                with c1:
                    st.markdown(
                        f"**{L(lang,'전체 takeaway','Overall takeaway')}**"
                    )
                    st.write(
                        figure.get(
                            "overall_takeaway",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'지지하는 것','What it supports')}**"
                    )
                    st.write(
                        figure.get(
                            "what_it_proves",
                            "",
                        )
                    )

                with c2:
                    st.markdown(
                        f"**{L(lang,'증명하지 못하는 것','What it does NOT establish')}**"
                    )
                    st.write(
                        figure.get(
                            "what_it_does_not_prove",
                            "",
                        )
                    )


# ============================================================
# CRITICAL + LEARN NEXT
# ============================================================

with tabs[5]:
    st.header(
        L(
            lang,
            "🧐 비판적 읽기 + 📚 다음 학습",
            "🧐 Critical Reading + 📚 Learn Next",
        )
    )

    if not critical_record:
        st.write(
            L(
                lang,
                "핵심 논리를 이해한 뒤 필요할 때만 마지막 비판적 분석을 생성합니다.",
                "Generate the final critical-reading layer only after the core analysis.",
            )
        )

        if st.button(
            L(
                lang,
                "🧐 Critical Reading 생성",
                "🧐 Generate Critical Reading",
            ),
            type="primary",
            key="generate_critical",
        ):
            with st.spinner(
                L(
                    lang,
                    "논문의 가장 강한 근거와 약한 연결고리를 점검 중...",
                    "Evaluating the strongest evidence and weakest inferential links...",
                )
            ):
                try:
                    result, model = (
                        analyze_critical_learning(
                            paper_text=paper_text,
                            core_bundle=core_record["data"],
                            experiments_bundle=(
                                experiments_record["data"]
                                if experiments_record
                                else None
                            ),
                            api_key=server_key,
                            depth=depth,
                        )
                    )

                    set_stage(
                        "critical_learning",
                        depth,
                        result,
                        model,
                    )

                    st.rerun()

                except Exception as exc:
                    show_stage_error(
                        L(
                            lang,
                            "비판적 읽기",
                            "Critical Reading",
                        ),
                        exc,
                    )

    else:
        data = selected_language_data(
            critical_record
        )

        model_badge(
            critical_record
        )

        crit = data.get(
            "critical_reading",
            {},
        )

        c1, c2 = st.columns(2)

        with c1:
            st.markdown(
                f"### {L(lang,'💪 가장 강한 근거','💪 Strongest evidence')}"
            )
            st.write(
                crit.get(
                    "strongest_evidence",
                    "",
                )
            )

            st.markdown(
                f"### {L(lang,'⚠️ 가장 약한 연결고리','⚠️ Weakest link')}"
            )
            st.write(
                crit.get(
                    "weakest_link",
                    "",
                )
            )

            st.markdown(
                f"### {L(lang,'🧪 하나 더 한다면','🧪 One experiment to add')}"
            )
            st.write(
                crit.get(
                    "missing_control_or_experiment",
                    "",
                )
            )

        with c2:
            st.markdown(
                f"### {L(lang,'🔀 대안 해석','🔀 Alternative explanations')}"
            )

            for item in crit.get(
                "alternative_explanations",
                [],
            ):
                st.markdown(
                    f"- {item}"
                )

            st.markdown(
                f"### {L(lang,'📝 저자가 밝힌 한계','📝 Author-stated limitations')}"
            )

            for item in crit.get(
                "author_stated_limitations",
                [],
            ):
                st.markdown(
                    f"- {item}"
                )

        st.markdown(
            f"### {L(lang,'👀 Reviewer라면 물을 질문','👀 Reviewer questions')}"
        )

        for item in crit.get(
            "reviewer_questions",
            [],
        ):
            st.markdown(
                f"- {item}"
            )

        st.divider()

        st.header(
            L(
                lang,
                "📚 이 논문을 다시 읽기 전에",
                "📚 Before reading again",
            )
        )

        for item in sorted(
            data.get(
                "learning_path",
                [],
            ),
            key=lambda x: x.get(
                "order",
                999,
            ),
        ):
            with st.container(
                border=True
            ):
                st.markdown(
                    f"### {item.get('order','')}. "
                    f"{item.get('topic','')}"
                )

                st.write(
                    item.get(
                        "why_now",
                        "",
                    )
                )

                st.caption(
                    f"{L(lang,'추천 행동','Suggested action')}: "
                    + item.get(
                        "action",
                        "",
                    )
                )


# ============================================================
# EXPORT
# ============================================================

st.divider()

all_records = {
    "core": core_record,
    "prerequisites": prereq_record,
    "experiments": experiments_record,
    "figures": figures_record,
    "critical_learning": critical_record,
}

export_data = {
    "lalstudy_version": APP_VERSION,
    "paper_name": paper_name,
    "paper_hash": active_hash(),
    "depth": depth,
    "modules": {
        key: (
            value.get("data")
            if value
            else None
        )
        for key, value in (
            all_records.items()
        )
    },
    "models": {
        key: (
            value.get("model")
            if value
            else None
        )
        for key, value in (
            all_records.items()
        )
    },
}

st.download_button(
    L(
        lang,
        "⬇️ 현재 Learning Map JSON 저장",
        "⬇️ Download current Learning Map JSON",
    ),
    data=json.dumps(
        export_data,
        ensure_ascii=False,
        indent=2,
    ),
    file_name=(
        Path(paper_name).stem
        + "_lalstudy_v023.json"
    ),
    mime="application/json",
    use_container_width=True,
)

st.caption(
    L(
        lang,
        "v0.2.3-beta: 각 AI module은 독립적으로 저장됩니다. 한 module 실패가 다른 결과를 지우지 않습니다.",
        "v0.2.3-beta: each AI module is stored independently; one module failing does not erase the others.",
    )
)
