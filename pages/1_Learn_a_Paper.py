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
from knowledge_widget import render_knowledge_archive_widget
from ai_provider import render_openai_usage_panel
from ai_router import (
    analyze_core,
    analyze_prerequisites,
    analyze_experiments,
    analyze_figures,
    analyze_single_figure,
    analyze_critical_learning,
    StageCallError,
    get_text_models,
    get_figure_models,
)
from ai_provider import (
    get_openai_api_key,
    openai_ready,
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

from source_pdf_figure_extractor import (
    extract_figures_from_source_pdf,
    available as source_pdf_extractor_available,
)

APP_VERSION = "v0.4.0-beta"
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


@st.cache_data(show_spinner=False)
def get_source_pdf_figures_v2(
    file_bytes,
    paper_hash,
):
    return extract_figures_from_source_pdf(
        pdf_bytes=file_bytes,
        paper_hash=paper_hash,
        force=False,
    )


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



def single_figure_stage_name(source_item):
    key = (
        source_item.get("figure_key")
        or source_item.get("figure_label")
        or "figure"
    )
    key = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(key))
    return f"single_figure:{key}"


def get_single_figure_stage(source_item, depth):
    return get_stage(
        single_figure_stage_name(source_item),
        depth,
    )


def set_single_figure_stage(
    source_item,
    depth,
    result,
    model,
    provider,
    usage=None,
):
    st.session_state[
        stage_key(
            single_figure_stage_name(source_item),
            depth,
        )
    ] = {
        "data": result.model_dump(),
        "model": model,
        "provider": provider,
        "usage": usage,
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
        provider = record.get("provider", "")
        model = record.get("model", "")
        label = " · ".join(
            value
            for value in [provider, model]
            if value
        )
        st.caption(
            f"AI: {label or model}"
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


# ============================================================
# ACTIVE PAPER
# ============================================================

st.title(
    "📄 Learn a Paper"
)

render_openai_usage_panel(lang=lang)

render_knowledge_archive_widget(
    lang=lang,
    depth=depth,
)

openai_api_key = get_openai_api_key()
openai_ok = openai_ready()

st.sidebar.caption("Active AI: OpenAI")
st.sidebar.caption(
    "Text: " + " → ".join(get_text_models())
)
st.sidebar.caption(
    "Figure: " + " → ".join(get_figure_models())
)


st.caption(
    L(
        lang,
        "논문을 한 번 분석하면 핵심 내용과 Figure + 원문 legend를 먼저 정리합니다. 더 깊은 분석은 Plus에서 필요할 때만 추가합니다.",
        "Analyze once to prepare the core story plus Figures and their source legends. Deeper analyses are optional Plus modules.",
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
            "PDF를 올리면 `논문 분석하기` 버튼이 나타납니다.",
            "Upload a PDF and the `Analyze paper` button will appear.",
        )
    )

    st.code(
        """PDF
↓
[논문 분석하기]
↓
Core Analysis
+ Figure crop
+ 원문 Figure legend
↓
Main: 핵심 내용 / Figures
↓
Plus: 선수지식 / 실험 전략 / 비판적 읽기""",
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

# ============================================================
# MAIN ANALYSIS STATE
# ============================================================

source_figure_state_key = (
    "lal_source_pdf_figures:v2:"
    + active_hash()
)

mineru_state_key = (
    "lal_mineru_figures:fallback_v1:"
    + active_hash()
)

source_record = st.session_state.get(
    source_figure_state_key
)

mineru_record = st.session_state.get(
    mineru_state_key
)

if (
    source_record
    and source_record.get(
        "figures"
    )
):
    extracted_study_figures = (
        source_record[
            "figures"
        ]
    )
    figure_extraction_engine = (
        source_record.get(
            "engine",
            "source_pdf_caption_v2",
        )
    )

elif (
    mineru_record
    and mineru_record.get(
        "figures"
    )
):
    extracted_study_figures = (
        mineru_record[
            "figures"
        ]
    )
    figure_extraction_engine = (
        mineru_record.get(
            "engine",
            "mineru_fallback",
        )
    )

else:
    extracted_study_figures = []
    figure_extraction_engine = (
        "not_prepared"
    )

core_record = get_stage(
    "core",
    depth,
)
figures_record = get_stage(
    "figures",
    depth,
)
prereq_record = get_stage(
    "prerequisites",
    depth,
)
experiments_record = get_stage(
    "experiments",
    depth,
)
critical_record = get_stage(
    "critical_learning",
    depth,
)

if len(paper_text) < 500:
    st.warning(
        L(
            lang,
            "PDF text layer가 매우 적습니다. Core Analysis 품질이 낮아질 수 있고 Figure 추출은 fallback이 필요할 수 있습니다.",
            "The PDF has little extractable text. Core Analysis may be weaker and Figure extraction may require fallback.",
        )
    )


def prepare_main_figures(
    *,
    force=False,
):
    """
    Prepare Figure images + source legends without an AI call.
    Source-PDF extraction is primary. MinerU is an automatic fallback only.
    """
    figures = []

    if source_pdf_extractor_available():
        try:
            figures = (
                extract_figures_from_source_pdf(
                    pdf_bytes=pdf_bytes,
                    paper_hash=active_hash(),
                    force=force,
                )
            )
        except Exception:
            figures = []

    if figures:
        st.session_state[
            source_figure_state_key
        ] = {
            "engine": (
                "source_pdf_caption_v2"
            ),
            "figures": figures,
        }
        return (
            figures,
            "source_pdf_caption_v2",
        )

    if (
        mineru_available()
        and mineru_token
    ):
        figures = (
            extract_figures_with_mineru(
                pdf_bytes=pdf_bytes,
                paper_hash=active_hash(),
                token=mineru_token,
                language="en",
                force=force,
            )
        )

        st.session_state[
            mineru_state_key
        ] = {
            "engine": (
                "mineru_fallback"
            ),
            "figures": figures,
        }

        return (
            figures,
            "mineru_fallback",
        )

    return (
        [],
        "not_prepared",
    )


def figure_number(
    label,
):
    match = re.search(
        r"(?i)(\d+)",
        label or "",
    )

    return (
        int(match.group(1))
        if match
        else None
    )


def ai_figure_for_source(
    source_item,
    ai_figures,
):
    target = figure_number(
        source_item.get(
            "figure_label",
            "",
        )
    )

    if target is None:
        return None

    for item in ai_figures:
        if figure_number(
            item.get(
                "figure_label",
                "",
            )
        ) == target:
            return item

    return None


def render_ai_figure_analysis(
    figure,
):
    st.markdown(
        f"#### {L(lang,'AI Figure 해석','AI Figure interpretation')}"
    )

    role = figure.get(
        "role_in_story",
        "",
    )

    if role:
        st.caption(
            role
        )

    main_question = figure.get(
        "main_question",
        "",
    )

    if main_question:
        st.markdown(
            f"**{L(lang,'핵심 질문','Main question')}**"
        )
        st.write(
            main_question
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
                left, right = (
                    st.columns(2)
                )

                with left:
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

                with right:
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

                methods = panel.get(
                    "methods",
                    [],
                )

                if methods:
                    st.caption(
                        "Methods: "
                        + ", ".join(
                            methods
                        )
                    )

    takeaway = figure.get(
        "overall_takeaway",
        "",
    )

    proves = figure.get(
        "what_it_proves",
        "",
    )

    not_proves = figure.get(
        "what_it_does_not_prove",
        "",
    )

    if (
        takeaway
        or proves
        or not_proves
    ):
        left, right = (
            st.columns(2)
        )

        with left:
            if takeaway:
                st.markdown(
                    f"**{L(lang,'전체 takeaway','Overall takeaway')}**"
                )
                st.write(
                    takeaway
                )

            if proves:
                st.markdown(
                    f"**{L(lang,'무엇을 지지하나','What it supports')}**"
                )
                st.write(
                    proves
                )

        with right:
            if not_proves:
                st.markdown(
                    f"**{L(lang,'증명하지 못하는 것','What it does NOT establish')}**"
                )
                st.write(
                    not_proves
                )


# ============================================================
# ONE PRIMARY ENTRY POINT
# ============================================================

main_ready = bool(
    core_record
    and extracted_study_figures
)

if not main_ready:
    st.divider()

    with st.container(
        border=True
    ):
        st.subheader(
            L(
                lang,
                "📄 논문 분석",
                "📄 Paper Analysis",
            )
        )

        st.write(
            L(
                lang,
                "한 번의 클릭으로 Core Analysis와 Figure 이미지 + 원문 legend를 준비합니다.",
                "One click prepares the Core Analysis plus Figure images and their original source legends.",
            )
        )

        st.caption(
            L(
                lang,
                "기본 분석에서는 OpenAI가 Core에 사용됩니다. Figure crop/legend 추출은 PDF에서 직접 처리합니다.",
                "The currently selected AI provider is used for Core. Figure crop/legend extraction is handled directly from the PDF.",
            )
        )

        analyze_paper_clicked = (
            st.button(
                L(
                    lang,
                    "📄 논문 분석하기",
                    "📄 Analyze paper",
                ),
                type="primary",
                use_container_width=True,
                disabled=(
                    not openai_ok
                ),
                key=(
                    "lal_main_analyze_paper"
                ),
            )
        )

        if analyze_paper_clicked:
            progress = st.progress(
                0
            )
            status = st.empty()

            main_errors = []

            # 1) Figure images + source legend
            if not extracted_study_figures:
                status.info(
                    L(
                        lang,
                        "1/2 · PDF에서 Figure와 원문 legend를 추출 중...",
                        "1/2 · Extracting Figures and source legends from the PDF...",
                    )
                )

                try:
                    (
                        extracted_study_figures,
                        figure_extraction_engine,
                    ) = prepare_main_figures(
                        force=False
                    )

                    if not extracted_study_figures:
                        main_errors.append(
                            "No Figure captions/images were detected."
                        )

                except Exception as exc:
                    main_errors.append(
                        "Figure extraction: "
                        + str(exc)
                    )

            progress.progress(
                0.45
            )

            # 2) Core AI
            if not core_record:
                status.info(
                    L(
                        lang,
                        "2/2 · 논문의 핵심 논리와 결론을 분석 중...",
                        "2/2 · Analyzing the paper's core logic and conclusions...",
                    )
                )

                try:
                    result, model = (
                        analyze_core(
                            paper_text=paper_text,
                            api_key=openai_api_key,
                                                        depth=depth,
                            detected_methods=[
                                name
                                for name, _
                                in rule_methods.most_common(
                                    25
                                )
                            ],
                        )
                    )

                    set_stage(
                        "core",
                        depth,
                        result,
                        model,
                    )

                except Exception as exc:
                    main_errors.append(
                        (
                            "Core Analysis: "
                            + str(exc)
                        )
                    )

            progress.progress(
                1.0
            )

            if main_errors:
                status.warning(
                    L(
                        lang,
                        "일부 단계가 완료되지 않았습니다. 완료된 결과는 유지됩니다.",
                        "Some steps did not complete. Successful results were preserved.",
                    )
                )

                with st.expander(
                    L(
                        lang,
                        "오류 확인",
                        "View errors",
                    )
                ):
                    for error in main_errors:
                        st.code(
                            error
                        )
            else:
                status.success(
                    L(
                        lang,
                        "논문 기본 분석 완료",
                        "Paper analysis complete",
                    )
                )

            st.rerun()


# Refresh after possible analysis.
core_record = get_stage(
    "core",
    depth,
)
figures_record = get_stage(
    "figures",
    depth,
)
prereq_record = get_stage(
    "prerequisites",
    depth,
)
experiments_record = get_stage(
    "experiments",
    depth,
)
critical_record = get_stage(
    "critical_learning",
    depth,
)

source_record = st.session_state.get(
    source_figure_state_key
)

mineru_record = st.session_state.get(
    mineru_state_key
)

if (
    source_record
    and source_record.get(
        "figures"
    )
):
    extracted_study_figures = (
        source_record[
            "figures"
        ]
    )
    figure_extraction_engine = (
        source_record.get(
            "engine",
            "source_pdf_caption_v2",
        )
    )

elif (
    mineru_record
    and mineru_record.get(
        "figures"
    )
):
    extracted_study_figures = (
        mineru_record[
            "figures"
        ]
    )
    figure_extraction_engine = (
        mineru_record.get(
            "engine",
            "mineru_fallback",
        )
    )

else:
    extracted_study_figures = []
    figure_extraction_engine = (
        "not_prepared"
    )

core_data = (
    selected_language_data(
        core_record
    )
    or {}
)

overview = core_data.get(
    "overview",
    {},
)


# ============================================================
# MAIN CONTENT
# ============================================================

if core_record or extracted_study_figures:
    st.divider()

    st.subheader(
        L(
            lang,
            "Main Analysis",
            "Main Analysis",
        )
    )

    main_status = st.columns(
        2
    )

    with main_status[0]:
        st.success(
            (
                "🎯 Core · "
                + (
                    L(
                        lang,
                        "완료",
                        "Ready",
                    )
                    if core_record
                    else L(
                        lang,
                        "미완료",
                        "Not ready",
                    )
                )
            )
        )

    with main_status[1]:
        st.success(
            (
                "🖼 Figures · "
                + str(
                    len(
                        extracted_study_figures
                    )
                )
                + " "
                + L(
                    lang,
                    "개",
                    "found",
                )
            )
        )

    main_tabs = st.tabs(
        [
            L(
                lang,
                "🎯 핵심 내용",
                "🎯 Core",
            ),
            "🖼 Figures",
        ]
    )

    # --------------------------------------------------------
    # CORE
    # --------------------------------------------------------
    with main_tabs[0]:
        if not core_record:
            st.warning(
                L(
                    lang,
                    "Core Analysis가 아직 완료되지 않았습니다. 위의 `논문 분석하기`를 다시 실행하세요.",
                    "Core Analysis is not ready yet. Run `Analyze paper` again above.",
                )
            )

        else:
            model_badge(
                core_record
            )

            st.header(
                overview.get(
                    "title",
                    paper_name,
                )
            )

            takeaway = overview.get(
                "one_sentence_takeaway",
                "",
            )

            if takeaway:
                st.info(
                    takeaway
                )

            left, right = (
                st.columns(2)
            )

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

            st.divider()

            st.subheader(
                L(
                    lang,
                    "🧭 논리 흐름",
                    "🧭 Logic Map",
                )
            )

            st.caption(
                L(
                    lang,
                    "각 결과를 나열하기보다 왜 다음 실험으로 넘어가는지 따라갑니다.",
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

                    c1, c2 = (
                        st.columns(2)
                    )

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

                        evidence = step.get(
                            "evidence_location",
                            "",
                        )

                        if evidence:
                            st.caption(
                                f"{L(lang,'근거','Evidence')}: {evidence}"
                            )

                if i < (
                    len(
                        logic_map
                    )
                    - 1
                ):
                    logic_arrow()

    # --------------------------------------------------------
    # FIGURES
    # --------------------------------------------------------
    with main_tabs[1]:
        st.header(
            "🖼 Figures"
        )

        st.caption(
            L(
                lang,
                "논문 PDF에서 Figure 이미지와 바로 아래 원문 Figure legend를 한 묶음으로 가져옵니다. 이미지는 화면 폭에 맞춰 확대하지 않고 crop의 원래 크기로 표시합니다.",
                "Each Figure is paired with its original source legend from the PDF. Images are displayed at their native crop size instead of being stretched to page width.",
            )
        )

        if not extracted_study_figures:
            st.warning(
                L(
                    lang,
                    "Figure가 준비되지 않았습니다.",
                    "Figures are not prepared yet.",
                )
            )

        st.caption(
            L(
                lang,
                "각 Figure는 서로 독립적으로 분석됩니다. 한 Figure가 실패해도 다른 Figure의 결과는 유지됩니다.",
                "Each Figure is analyzed independently. A failure in one Figure does not affect the others.",
            )
        )

        figure_openai_ready = openai_ok

        analyzed_count = sum(
            1
            for source_item in extracted_study_figures
            if get_single_figure_stage(
                source_item,
                depth,
            )
        )

        if extracted_study_figures:
            st.caption(
                f"AI analyzed: {analyzed_count}/{len(extracted_study_figures)} · "
                + "OpenAI"
            )

        for source_item in (
            extracted_study_figures
        ):
            figure_record = (
                get_single_figure_stage(
                    source_item,
                    depth,
                )
            )

            with st.container(
                border=True
            ):
                st.subheader(
                    source_item.get(
                        "figure_label",
                        "Figure",
                    )
                )

                st.image(
                    source_item.get(
                        "image_path"
                    ),
                    caption=(
                        f"{source_item.get('figure_label','Figure')} · "
                        f"page {source_item.get('page_number','?')}"
                    ),
                    use_container_width=False,
                )

                st.markdown(
                    f"#### {L(lang,'원문 Figure legend','Original Figure legend')}"
                )

                st.write(
                    source_item.get(
                        "caption",
                        "",
                    )
                )

                button_label = (
                    L(
                        lang,
                        "✨ 이 Figure 분석하기",
                        "✨ Analyze this Figure",
                    )
                    if not figure_record
                    else L(
                        lang,
                        "🔄 이 Figure 다시 분석하기",
                        "🔄 Re-analyze this Figure",
                    )
                )

                if st.button(
                    button_label,
                    key=(
                        "lal_single_figure_ai_"
                        + str(
                            source_item.get(
                                "figure_key",
                                source_item.get(
                                    "figure_label",
                                    "figure",
                                ),
                            )
                        )
                    ),
                    type=(
                        "primary"
                        if not figure_record
                        else "secondary"
                    ),
                    disabled=(
                        not figure_openai_ready
                    ),
                ):
                    with st.spinner(
                        L(
                            lang,
                            f"{source_item.get('figure_label','Figure')}만 분석 중...",
                            f"Analyzing only {source_item.get('figure_label','Figure')}...",
                        )
                    ):
                        try:
                            image_path = Path(
                                source_item.get(
                                    "image_path",
                                    "",
                                )
                            )

                            if not image_path.exists():
                                raise FileNotFoundError(
                                    f"Figure crop not found: {image_path}"
                                )

                            suffix = image_path.suffix.lower()
                            mime_type = {
                                ".jpg": "image/jpeg",
                                ".jpeg": "image/jpeg",
                                ".webp": "image/webp",
                            }.get(
                                suffix,
                                "image/png",
                            )

                            (
                                result,
                                model,
                                provider,
                                usage,
                            ) = analyze_single_figure(
                                figure_label=(
                                    source_item.get(
                                        "figure_label",
                                        "Figure",
                                    )
                                ),
                                image_bytes=(
                                    image_path.read_bytes()
                                ),
                                image_mime_type=mime_type,
                                legend=(
                                    source_item.get(
                                        "caption",
                                        "",
                                    )
                                ),
                                core_bundle=(
                                    core_record[
                                        "data"
                                    ]
                                    if core_record
                                    else {}
                                ),
                                api_key=(
                                    openai_api_key
                                ),
                                                            )

                            set_single_figure_stage(
                                source_item,
                                depth,
                                result,
                                model,
                                provider,
                                usage,
                            )

                            st.rerun()

                        except Exception as exc:
                            show_stage_error(
                                source_item.get(
                                    "figure_label",
                                    "Figure",
                                ),
                                exc,
                            )

                if figure_record:
                    st.divider()
                    model_badge(
                        figure_record
                    )

                    usage = figure_record.get(
                        "usage"
                    ) or {}

                    if usage.get(
                        "total_tokens"
                    ):
                        st.caption(
                            "Tokens: "
                            f"{usage.get('input_tokens','?')} in + "
                            f"{usage.get('output_tokens','?')} out = "
                            f"{usage.get('total_tokens','?')} total"
                        )

                    figure_ai_data = (
                        selected_language_data(
                            figure_record
                        )
                        or {}
                    )

                    render_ai_figure_analysis(
                        figure_ai_data
                    )

        with st.expander(
            L(
                lang,
                "🔧 Figure 추출 진단",
                "🔧 Figure extraction diagnostics",
            ),
            expanded=False,
        ):
            st.caption(
                f"engine: {figure_extraction_engine}"
            )

            if st.button(
                L(
                    lang,
                    "Figure 강제 재추출",
                    "Force re-extract Figures",
                ),
                key=(
                    "lal_force_reextract_figures"
                ),
            ):
                try:
                    (
                        figures,
                        engine,
                    ) = prepare_main_figures(
                        force=True
                    )

                    st.success(
                        f"{len(figures)} Figures · {engine}"
                    )

                    st.rerun()

                except Exception as exc:
                    st.error(
                        str(exc)
                    )


# ============================================================
# PLUS ANALYSIS
# ============================================================

if core_record:
    st.divider()

    st.subheader(
        "✨ Plus Analysis"
    )

    st.caption(
        L(
            lang,
            "기본 논문 이해에는 필요하지 않은 추가 분석입니다. 원하는 항목만 열어 별도로 AI를 호출합니다.",
            "Optional deeper analyses. Open only the module you want; each one makes its own AI request only when generated.",
        )
    )

    # --------------------------------------------------------
    # PREREQUISITES PLUS
    # --------------------------------------------------------
    with st.expander(
        (
            "🧠 "
            + L(
                lang,
                "선수지식",
                "Prerequisites",
            )
            + (
                " · ✓"
                if prereq_record
                else " · Plus"
            )
        ),
        expanded=False,
    ):
        if not prereq_record:
            st.write(
                L(
                    lang,
                    "이 논문을 읽는 데 필요한 배경 개념을 AI가 선별합니다.",
                    "AI selects the background concepts most useful for understanding this paper.",
                )
            )

            if st.button(
                L(
                    lang,
                    "🧠 선수지식 추가 분석",
                    "🧠 Add prerequisite analysis",
                ),
                key=(
                    "plus_generate_prerequisites"
                ),
                disabled=(
                    not openai_ok
                ),
            ):
                with st.spinner(
                    L(
                        lang,
                        "선수지식을 분석 중...",
                        "Analyzing prerequisites...",
                    )
                ):
                    try:
                        result, model = (
                            analyze_prerequisites(
                                paper_text=paper_text,
                                core_bundle=(
                                    core_record[
                                        "data"
                                    ]
                                ),
                                api_key=openai_api_key,
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
            data = (
                selected_language_data(
                    prereq_record
                )
                or {}
            )

            model_badge(
                prereq_record
            )

            for concept in data.get(
                "prerequisites",
                [],
            ):
                with st.expander(
                    (
                        f"{concept.get('name','')} · "
                        f"{difficulty_label(concept.get('difficulty',''))}"
                    )
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

                    prerequisites = (
                        concept.get(
                            "prerequisites",
                            [],
                        )
                    )

                    if prerequisites:
                        st.caption(
                            (
                                L(
                                    lang,
                                    "먼저 알면 좋은 것: ",
                                    "Learn first: ",
                                )
                                + " → ".join(
                                    prerequisites
                                )
                            )
                        )

    # --------------------------------------------------------
    # EXPERIMENTAL STRATEGY PLUS
    # --------------------------------------------------------
    with st.expander(
        (
            "🔬 "
            + L(
                lang,
                "실험 전략",
                "Experimental Strategy",
            )
            + (
                " · ✓"
                if experiments_record
                else " · Plus"
            )
        ),
        expanded=False,
    ):
        if not experiments_record:
            st.write(
                L(
                    lang,
                    "핵심 실험의 What / Why / Readout / limitation을 추가로 분석합니다.",
                    "Add a deeper What / Why / Readout / limitation analysis of the major experiments.",
                )
            )

            if st.button(
                L(
                    lang,
                    "🔬 실험 전략 추가 분석",
                    "🔬 Add experiment analysis",
                ),
                key=(
                    "plus_generate_experiments"
                ),
                disabled=(
                    not openai_ok
                ),
            ):
                with st.spinner(
                    L(
                        lang,
                        "핵심 실험을 분석 중...",
                        "Analyzing major experiments...",
                    )
                ):
                    try:
                        result, model = (
                            analyze_experiments(
                                paper_text=paper_text,
                                core_bundle=(
                                    core_record[
                                        "data"
                                    ]
                                ),
                                api_key=openai_api_key,
                                                                detected_methods=[
                                    name
                                    for name, _
                                    in rule_methods.most_common(
                                        30
                                    )
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
            data = (
                selected_language_data(
                    experiments_record
                )
                or {}
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

                    left, right = (
                        st.columns(2)
                    )

                    with left:
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
                            "**Readout**"
                        )
                        st.write(
                            exp.get(
                                "readout",
                                "",
                            )
                        )

                    with right:
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

                        evidence = exp.get(
                            "evidence_location",
                            "",
                        )

                        if evidence:
                            st.caption(
                                f"{L(lang,'근거','Evidence')}: {evidence}"
                            )

                    canonical = (
                        canonical_method_match(
                            method
                        )
                    )

                    if canonical:
                        b1, b2 = (
                            st.columns(2)
                        )

                        with b1:
                            method_jump_button(
                                canonical,
                                key=(
                                    f"plus_method_{idx}"
                                ),
                                target=(
                                    "method"
                                ),
                            )

                        with b2:
                            method_jump_button(
                                canonical,
                                key=(
                                    f"plus_figure_{idx}"
                                ),
                                target=(
                                    "figure"
                                ),
                            )

    # --------------------------------------------------------
    # CRITICAL READING PLUS
    # --------------------------------------------------------
    with st.expander(
        (
            "🧐 "
            + L(
                lang,
                "비판적 읽기",
                "Critical Reading",
            )
            + (
                " · ✓"
                if critical_record
                else " · Plus"
            )
        ),
        expanded=False,
    ):
        if not critical_record:
            st.write(
                L(
                    lang,
                    "가장 강한 근거, 약한 연결고리, 대안 해석과 추가 실험을 검토합니다.",
                    "Review the strongest evidence, weakest link, alternative explanations, and useful follow-up experiments.",
                )
            )

            if st.button(
                L(
                    lang,
                    "🧐 비판적 읽기 추가 분석",
                    "🧐 Add critical analysis",
                ),
                key=(
                    "plus_generate_critical"
                ),
                disabled=(
                    not openai_ok
                ),
            ):
                with st.spinner(
                    L(
                        lang,
                        "논문의 논리적 강점과 한계를 분석 중...",
                        "Analyzing strengths and inferential limits...",
                    )
                ):
                    try:
                        result, model = (
                            analyze_critical_learning(
                                paper_text=paper_text,
                                core_bundle=(
                                    core_record[
                                        "data"
                                    ]
                                ),
                                experiments_bundle=(
                                    experiments_record[
                                        "data"
                                    ]
                                    if experiments_record
                                    else None
                                ),
                                api_key=openai_api_key,
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
            data = (
                selected_language_data(
                    critical_record
                )
                or {}
            )

            model_badge(
                critical_record
            )

            crit = data.get(
                "critical_reading",
                {},
            )

            left, right = (
                st.columns(2)
            )

            with left:
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

            with right:
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

            reviewer_questions = (
                crit.get(
                    "reviewer_questions",
                    [],
                )
            )

            if reviewer_questions:
                st.markdown(
                    f"### {L(lang,'👀 Reviewer라면 물을 질문','👀 Reviewer questions')}"
                )

                for item in reviewer_questions:
                    st.markdown(
                        f"- {item}"
                    )

            learning_path = data.get(
                "learning_path",
                [],
            )

            if learning_path:
                st.divider()

                st.markdown(
                    f"### {L(lang,'📚 다음 학습','📚 Learn next')}"
                )

                for item in sorted(
                    learning_path,
                    key=lambda x: x.get(
                        "order",
                        999,
                    ),
                ):
                    with st.container(
                        border=True
                    ):
                        st.markdown(
                            (
                                f"**{item.get('order','')}. "
                                f"{item.get('topic','')}**"
                            )
                        )

                        st.write(
                            item.get(
                                "why_now",
                                "",
                            )
                        )

                        action = item.get(
                            "action",
                            "",
                        )

                        if action:
                            st.caption(
                                f"{L(lang,'추천 행동','Suggested action')}: {action}"
                            )


# ============================================================
# EXPORT
# ============================================================

st.divider()

all_records = {
    "core": core_record,
    "prerequisites": prereq_record,
    "experiments": experiments_record,
    "figures_legacy": figures_record,
    "critical_learning": critical_record,
}

single_figure_records = {
    str(
        item.get(
            "figure_key",
            item.get("figure_label", "Figure"),
        )
    ): get_single_figure_stage(item, depth)
    for item in extracted_study_figures
    if get_single_figure_stage(item, depth)
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
    "figure_analyses": {
        key: {
            "data": record.get("data"),
            "model": record.get("model"),
            "provider": record.get("provider"),
            "usage": record.get("usage"),
        }
        for key, record in single_figure_records.items()
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
        + "_lalstudy_v033.json"
    ),
    mime="application/json",
    use_container_width=True,
)

st.caption(
    L(
        lang,
        "Main Analysis는 Core + Figure/legend를 먼저 준비하고, Plus Analysis는 필요한 경우에만 독립적으로 추가됩니다.",
        "Main Analysis prepares Core + Figures/legends first; Plus modules are added independently only when requested.",
    )
)
