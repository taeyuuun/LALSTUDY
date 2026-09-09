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
from translator import translate_text
from ai_engine import (
    analyze_pdf,
    make_cache_key,
    sdk_available,
    DEFAULT_MODEL,
)

APP_VERSION = "v0.2.1-beta"
METHOD_PROFILE_FILE = Path("method_profiles.json")

st.set_page_config(
    page_title="LALSTUDY · Learn a Paper",
    page_icon="📄",
    layout="wide",
)


# ============================================================
# DATA / RULE-BASED FALLBACK
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
        METHOD_PROFILE_FILE.read_text(encoding="utf-8")
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
        return method_alias_index[query]

    # Containment match.
    containment = []

    for alias, canonical in method_alias_index.items():
        if query in alias or alias in query:
            containment.append(
                (len(alias), canonical)
            )

    if containment:
        containment.sort(reverse=True)
        return containment[0][1]

    # Conservative fuzzy fallback.
    best = None
    best_score = 0.0

    for alias, canonical in method_alias_index.items():
        score = SequenceMatcher(
            None,
            query,
            alias,
        ).ratio()

        if score > best_score:
            best_score = score
            best = canonical

    if best_score >= 0.82:
        return best

    return None


@st.cache_data(show_spinner=False)
def extract_pdf_text(file_bytes):
    reader = PdfReader(
        io.BytesIO(file_bytes)
    )

    pages = []

    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        pages.append(
            {
                "page": i + 1,
                "text": text,
            }
        )

    full = "\n".join(
        x["text"] for x in pages
    )

    return pages, full


def get_secret_key():
    # 1) Streamlit Cloud / local secrets
    try:
        if "GEMINI_API_KEY" in st.secrets:
            value = str(
                st.secrets["GEMINI_API_KEY"]
            ).strip()

            if value:
                return value, "secret"
    except Exception:
        pass

    # 2) Environment
    value = os.getenv(
        "GEMINI_API_KEY",
        ""
    ).strip()

    if value:
        return value, "environment"

    # 3) Current Streamlit session.
    # Use ONE stable key for both the widget and the analysis engine.
    value = str(
        st.session_state.get(
            "lalstudy_gemini_key",
            ""
        )
    ).strip()

    if value:
        return value, "session"

    return "", None


# ============================================================
# UI HELPERS
# ============================================================

def difficulty_label(value, lang):
    labels = {
        "basic": L(lang, "기초", "Basic"),
        "intermediate": L(lang, "중급", "Intermediate"),
        "advanced": L(lang, "심화", "Advanced"),
    }

    return labels.get(value, value)


def method_jump_button(method_name, key, target="method"):
    canonical = canonical_method_match(
        method_name
    )

    if not canonical:
        return

    label = (
        f"🧬 {canonical} "
        + L(lang, "사례 보기", "examples")
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
        "<div style='text-align:center;font-size:1.4rem;opacity:.55'>↓</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# SIDEBAR
# ============================================================

lang = language_selector()

st.sidebar.title("LALSTUDY")
st.sidebar.caption(APP_VERSION)

depth_options = {
    L(lang, "기초부터 자세히", "Foundation"): "foundation",
    L(lang, "생명과학 학부 수준", "Life-science undergraduate"): "undergraduate",
    L(lang, "심화 / 대학원 수준", "Advanced / graduate"): "advanced",
}

depth_label = st.sidebar.selectbox(
    L(lang, "설명 깊이", "Explanation depth"),
    list(depth_options.keys()),
    index=1,
)

depth = depth_options[
    depth_label
]

st.sidebar.caption(
    L(
        lang,
        "같은 논문이라도 선택한 수준에 따라 선수지식 설명 깊이가 달라집니다.",
        "Prerequisite explanations adapt to the selected learning level.",
    )
)

if lang == "ko":
    st.sidebar.caption(
        "🧬 용어 스타일: Korean prose + English scientific terms"
    )

existing_key, key_source = get_secret_key()

if existing_key:
    st.sidebar.success(
        L(
            lang,
            "✨ AI 연결 준비 완료",
            "✨ AI ready",
        )
    )
else:
    st.sidebar.info(
        L(
            lang,
            "PDF 업로드 후 본문에서 Gemini API key를 입력하세요.",
            "Upload a PDF, then enter your Gemini API key in the main page.",
        )
    )

st.sidebar.caption(
    L(
        lang,
        f"AI model: {DEFAULT_MODEL}",
        f"AI model: {DEFAULT_MODEL}",
    )
)


# ============================================================
# PAGE
# ============================================================

st.title("📄 Learn a Paper · AI Deep Study")

st.caption(
    L(
        lang,
        "요약이 아니라 논문의 논리·배경지식·실험·Figure를 하나의 학습 경로로 재구성합니다.",
        "More than a summary: reconstruct the paper's logic, prerequisites, experiments, and Figures as a learning path.",
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

# ------------------------------------------------------------
# ACTIVE PAPER STATE
# ------------------------------------------------------------
# A FileUploader widget belongs to this page and may disappear when the user
# navigates away. Store the actual bytes under non-widget session keys so the
# active paper survives navigation across the whole multipage app.

if uploaded is not None:
    new_bytes = uploaded.getvalue()
    new_hash = hashlib.sha256(
        new_bytes
    ).hexdigest()

    old_hash = st.session_state.get(
        "lalstudy_active_paper_hash"
    )

    if new_hash != old_hash:
        # A genuinely new paper replaces the current active paper.
        # Clear old AI analysis bundles while preserving API key/preferences.
        for state_key in list(
            st.session_state.keys()
        ):
            if str(state_key).startswith(
                "lal_ai_result:"
            ):
                del st.session_state[
                    state_key
                ]

    st.session_state[
        "lalstudy_active_paper_bytes"
    ] = new_bytes

    st.session_state[
        "lalstudy_active_paper_name"
    ] = uploaded.name

    st.session_state[
        "lalstudy_active_paper_hash"
    ] = new_hash


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
            "PDF를 올리면 AI Deep Study가 논문 전체를 학습용 구조로 재구성합니다.",
            "Upload a PDF and AI Deep Study will reconstruct the paper as a structured learning experience.",
        )
    )

    st.markdown(
        L(
            lang,
            """
### v0.2.1-beta

**AI Deep Study**
- 연구 질문 / knowledge gap / hypothesis
- 논문의 전체 논리 지도
- 선수지식 dependency
- 각 실험의 **왜 이 방법을 썼는가**
- Figure별 **What / How / Why / What it proves**
- 논문의 약한 고리와 추가실험
- 개인 수준에 맞춘 다음 학습 순서

한 번 업로드한 PDF와 분석 결과는 페이지를 이동해도 현재 session에 유지됩니다.
""",
            """
### v0.2.1-beta

**AI Deep Study**
- Research question / knowledge gap / hypothesis
- Whole-paper logic map
- Prerequisite dependencies
- Why each experimental method was chosen
- Figure-by-Figure **What / How / Why / What it proves**
- Critical reading and missing experiments
- Level-adapted learning path

The active PDF and its analysis stay available while you navigate between pages in the current session.
""",
        )
    )

    st.stop()


with st.container(
    border=True
):
    c_paper, c_clear = st.columns(
        [5, 1]
    )

    with c_paper:
        st.markdown(
            f"**{L(lang,'📌 현재 논문','📌 Active paper')}**  \n"
            f"{paper_name}"
        )

    with c_clear:
        if st.button(
            L(
                lang,
                "논문 닫기",
                "Clear paper",
            ),
            use_container_width=True,
            key="lalstudy_clear_active_paper",
        ):
            for state_key in list(
                st.session_state.keys()
            ):
                if (
                    str(state_key).startswith(
                        "lalstudy_active_paper_"
                    )
                    or str(state_key).startswith(
                        "lal_ai_result:"
                    )
                ):
                    del st.session_state[
                        state_key
                    ]

            st.rerun()


with st.spinner(
    L(
        lang,
        "PDF 기본 구조를 읽는 중...",
        "Reading PDF structure...",
    )
):
    pages, raw_text = extract_pdf_text(
        pdf_bytes
    )

full_text = clean_text(
    raw_text
)

rule_methods = detect_methods(
    full_text
)

m1, m2, m3 = st.columns(3)

m1.metric(
    L(lang, "페이지", "Pages"),
    len(pages),
)

m2.metric(
    L(
        lang,
        "ontology 감지 method",
        "Ontology methods",
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


# ============================================================
# AI CONTROL
# ============================================================

st.divider()

st.subheader(
    L(
        lang,
        "✨ AI Deep Study 시작",
        "✨ Start AI Deep Study",
    )
)

st.write(
    L(
        lang,
        "PDF 전체를 직접 읽고 **연구 질문 → 논리 지도 → 선수지식 → 실험 전략 → Figure 해석 → 비판적 읽기** 순서로 학습 자료를 만듭니다.",
        "Reads the full PDF and builds a learning path from **research question → logic map → prerequisites → experimental strategy → Figure interpretation → critical reading**.",
    )
)

st.markdown(
    f"#### {L(lang,'🔑 Gemini API key','🔑 Gemini API key')}"
)

# Keep the widget mounted on every rerun.
# This prevents Streamlit widget-state cleanup from erasing a user-entered key.
if key_source in ("secret", "environment"):
    st.success(
        L(
            lang,
            "서버에 Gemini API key가 연결되어 있습니다.",
            "A server-side Gemini API key is connected.",
        )
    )
else:
    st.text_input(
        L(
            lang,
            "API key를 입력하세요",
            "Enter your API key",
        ),
        type="password",
        key="lalstudy_gemini_key",
        placeholder="AIza...",
        help=L(
            lang,
            "키는 프로젝트 파일에 저장하지 않고 현재 Streamlit 세션에서만 유지합니다.",
            "The key is not written to project files and is kept only in the current Streamlit session.",
        ),
    )

# Re-read AFTER rendering the widget, so the current run uses the latest value.
existing_key, key_source = get_secret_key()

if existing_key and key_source == "session":
    st.success(
        L(
            lang,
            "API key가 현재 세션에 유지되고 있습니다.",
            "API key is retained in the current session.",
        )
    )

with st.expander(
    L(
        lang,
        "PDF / API 사용 안내",
        "PDF / API usage note",
    )
):
    st.write(
        L(
            lang,
            "AI 분석을 실행하면 업로드한 PDF가 Gemini API로 전송됩니다. "
            "공개 논문 사용을 권장합니다. 비공개·미출판 자료는 API 서비스의 "
            "데이터 처리 조건을 먼저 확인하세요.",
            "When AI analysis runs, the uploaded PDF is sent to the Gemini API. "
            "Public papers are recommended. Check the API provider's data terms "
            "before using confidential or unpublished material.",
        )
    )

if key_source == "session":
    if st.button(
        L(lang, "🔒 입력한 API key 지우기", "🔒 Clear entered API key"),
        key="clear_lalstudy_gemini_key",
    ):
        st.session_state["lalstudy_gemini_key"] = ""
        st.rerun()


if not sdk_available():
    st.error(
        L(
            lang,
            "`google-genai`가 설치되지 않았습니다. `python -m pip install -r requirements.txt`를 실행하세요.",
            "`google-genai` is not installed. Run `python -m pip install -r requirements.txt`.",
        )
    )

if len(pdf_bytes) > 50 * 1024 * 1024:
    st.error(
        L(
            lang,
            "현재 beta는 50 MB 이하 PDF만 지원합니다.",
            "The current beta supports PDFs up to 50 MB.",
        )
    )

can_run = bool(
    existing_key
    and sdk_available()
    and len(pdf_bytes) <= 50 * 1024 * 1024
)

analyze_clicked = st.button(
    L(
        lang,
        "✨ AI Deep Study 시작",
        "✨ Start AI Deep Study",
    ),
    type="primary",
    use_container_width=True,
    disabled=not can_run,
)

if not existing_key:
    st.caption(
        L(
            lang,
            "↑ API key를 입력하면 버튼이 활성화됩니다.",
            "↑ Enter an API key to enable the button.",
        )
    )


cache_key = make_cache_key(
    pdf_bytes,
    "bilingual",
    depth,
    DEFAULT_MODEL,
)

result_key = (
    "lal_ai_result:"
    + cache_key
)


if analyze_clicked:
    with st.spinner(
        L(
            lang,
            "논문의 논리와 Figure를 재구성하는 중입니다. 첫 분석은 시간이 조금 걸릴 수 있습니다...",
            "Reconstructing the paper's logic and Figures. The first analysis may take a little while...",
        )
    ):
        try:
            analysis = analyze_pdf(
                pdf_bytes=pdf_bytes,
                api_key=existing_key,
                language=lang,
                depth=depth,
                detected_methods=[
                    name
                    for name, _ in rule_methods.most_common(30)
                ],
                model=DEFAULT_MODEL,
            )

            st.session_state[
                result_key
            ] = analysis.model_dump()

        except Exception as exc:
            st.error(
                L(
                    lang,
                    f"AI 분석에 실패했습니다: {exc}",
                    f"AI analysis failed: {exc}",
                )
            )


analysis_bundle = st.session_state.get(
    result_key
)

analysis_data = None

if analysis_bundle:
    # v0.2.1+: one analysis contains both Korean and English.
    if (
        isinstance(
            analysis_bundle,
            dict
        )
        and "ko" in analysis_bundle
        and "en" in analysis_bundle
    ):
        analysis_data = analysis_bundle[
            lang
        ]

    # Backward-compatible fallback for a stale v0.2.0 session.
    else:
        analysis_data = analysis_bundle


# ============================================================
# AI RESULTS
# ============================================================

if analysis_data:
    st.success(
        L(
            lang,
            "AI Deep Study가 생성되었습니다. 한국어/English 결과가 함께 저장되어 언어를 바꿔도 다시 분석하지 않습니다.",
            "AI Deep Study generated. Korean and English results are stored together, so switching language does not re-analyze the PDF.",
        )
    )

    overview = analysis_data[
        "overview"
    ]

    tabs = st.tabs(
        [
            L(lang, "🎯 한눈에 보기", "🎯 Overview"),
            L(lang, "🧭 논리 지도", "🧭 Logic Map"),
            L(lang, "🧠 선수지식", "🧠 Prerequisites"),
            L(lang, "🔬 실험 전략", "🔬 Experiments"),
            L(lang, "🖼 Figure", "🖼 Figures"),
            L(lang, "🧐 비판적 읽기", "🧐 Critical Reading"),
            L(lang, "📚 다음 학습", "📚 Learn Next"),
        ]
    )

    # --------------------------------------------------------
    # OVERVIEW
    # --------------------------------------------------------
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

        c1, c2 = st.columns(2)

        with c1:
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
                f"### {L(lang,'🕳 Knowledge gap','🕳 Knowledge gap')}"
            )
            st.write(
                overview.get(
                    "knowledge_gap",
                    "",
                )
            )

            st.markdown(
                f"### {L(lang,'🧪 Hypothesis','🧪 Hypothesis')}"
            )
            st.write(
                overview.get(
                    "hypothesis",
                    "",
                )
            )

        with c2:
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

    # --------------------------------------------------------
    # LOGIC MAP
    # --------------------------------------------------------
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
                "논문의 결과를 나열하는 대신 '왜 다음 실험으로 넘어갔는가'를 따라갑니다.",
                "Follows why the authors moved from one experiment to the next instead of merely listing results.",
            )
        )

        logic_map = analysis_data.get(
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
                    f"### {step.get('order', i+1)}. "
                    f"{step.get('question','')}"
                )

                q1, q2 = st.columns(2)

                with q1:
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

                with q2:
                    st.markdown(
                        f"**{L(lang,'해석 / 추론','Inference')}**"
                    )
                    st.write(
                        step.get(
                            "inference",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'근거 위치','Evidence')}**"
                    )
                    st.write(
                        step.get(
                            "evidence_location",
                            "",
                        )
                    )

            if i < len(logic_map) - 1:
                logic_arrow()

    # --------------------------------------------------------
    # PREREQUISITES
    # --------------------------------------------------------
    with tabs[2]:
        st.header(
            L(
                lang,
                "🧠 이 논문을 이해하기 위한 선수지식",
                "🧠 Prerequisites for this paper",
            )
        )

        st.caption(
            L(
                lang,
                "일반 배경지식과 '이 논문에서 왜 필요한가'를 분리해서 보여줍니다.",
                "Separates general background knowledge from why the concept matters specifically in this paper.",
            )
        )

        for concept in analysis_data.get(
            "prerequisites",
            [],
        ):
            title = (
                f"{concept.get('name','')} · "
                f"{difficulty_label(concept.get('difficulty',''),lang)}"
            )

            with st.expander(
                title
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
                    f"**{L(lang,'배경지식','Background knowledge')}**"
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

                prerequisites = concept.get(
                    "prerequisites",
                    [],
                )

                if prerequisites:
                    st.markdown(
                        f"**{L(lang,'먼저 알면 좋은 것','Learn first')}**"
                    )
                    st.write(
                        " → ".join(
                            prerequisites
                        )
                    )

    # --------------------------------------------------------
    # EXPERIMENTS
    # --------------------------------------------------------
    with tabs[3]:
        st.header(
            L(
                lang,
                "🔬 Experimental Strategy",
                "🔬 Experimental Strategy",
            )
        )

        for idx, exp in enumerate(
            analysis_data.get(
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
                        f"**{L(lang,'이 실험이 묻는 질문','Scientific question')}**"
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
                        f"**{L(lang,'조작 변수','Manipulation')}**"
                    )
                    st.write(
                        exp.get(
                            "manipulated_variable",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'측정값','Readout')}**"
                    )
                    st.write(
                        exp.get(
                            "readout",
                            "",
                        )
                    )

                with c2:
                    st.markdown(
                        f"**{L(lang,'왜 이 방법인가?','Why this method?')}**"
                    )
                    st.write(
                        exp.get(
                            "why_this_method",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'결과가 의미하는 것','What the result means')}**"
                    )
                    st.write(
                        exp.get(
                            "result_meaning",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'해석의 한계','Limitation')}**"
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
                            key=f"method_jump_{idx}",
                            target="method",
                        )

                    with b2:
                        method_jump_button(
                            canonical,
                            key=f"figure_jump_{idx}",
                            target="figure",
                        )

                    profile = profiles_by_name.get(
                        canonical,
                        {},
                    )

                    if profile:
                        st.caption(
                            L(
                                lang,
                                f"LALSTUDY corpus: {profile.get('paper_count',0)} papers · "
                                f"{profile.get('figure_count',0)} Figure examples",
                                f"LALSTUDY corpus: {profile.get('paper_count',0)} papers · "
                                f"{profile.get('figure_count',0)} Figure examples",
                            )
                        )

    # --------------------------------------------------------
    # FIGURES
    # --------------------------------------------------------
    with tabs[4]:
        st.header(
            L(
                lang,
                "🖼 Figure-by-Figure",
                "🖼 Figure-by-Figure",
            )
        )

        st.caption(
            L(
                lang,
                "각 Figure를 '무엇을 했나'보다 '왜 했고 무엇까지 말할 수 있나' 중심으로 읽습니다.",
                "Reads each Figure around why it was done and what can legitimately be concluded.",
            )
        )

        for f_idx, figure in enumerate(
            analysis_data.get(
                "figures",
                [],
            )
        ):
            with st.expander(
                f"{figure.get('figure_label','Figure')} — "
                f"{figure.get('role_in_story','')}"
            ):
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
                    panel_tabs = st.tabs(
                        [
                            p.get(
                                "panel_label",
                                f"Panel {i+1}",
                            )
                            for i, p in enumerate(
                                panels
                            )
                        ]
                    )

                    for p_idx, panel in enumerate(
                        panels
                    ):
                        with panel_tabs[p_idx]:
                            a, b = st.columns(2)

                            with a:
                                st.markdown(
                                    f"**{L(lang,'WHAT','WHAT')}**"
                                )
                                st.write(
                                    panel.get(
                                        "what",
                                        "",
                                    )
                                )

                                st.markdown(
                                    f"**{L(lang,'HOW','HOW')}**"
                                )
                                st.write(
                                    panel.get(
                                        "how",
                                        "",
                                    )
                                )

                            with b:
                                st.markdown(
                                    f"**{L(lang,'RESULT','RESULT')}**"
                                )
                                st.write(
                                    panel.get(
                                        "result",
                                        "",
                                    )
                                )

                                st.markdown(
                                    f"**{L(lang,'INTERPRETATION','INTERPRETATION')}**"
                                )
                                st.write(
                                    panel.get(
                                        "interpretation",
                                        "",
                                    )
                                )

                            methods_here = panel.get(
                                "methods",
                                [],
                            )

                            if methods_here:
                                st.caption(
                                    "Methods: "
                                    + ", ".join(
                                        methods_here
                                    )
                                )

                st.divider()

                x1, x2 = st.columns(2)

                with x1:
                    st.markdown(
                        f"**{L(lang,'Figure 전체 takeaway','Overall takeaway')}**"
                    )
                    st.write(
                        figure.get(
                            "overall_takeaway",
                            "",
                        )
                    )

                    st.markdown(
                        f"**{L(lang,'이 Figure가 지지하는 것','What it supports')}**"
                    )
                    st.write(
                        figure.get(
                            "what_it_proves",
                            "",
                        )
                    )

                with x2:
                    st.markdown(
                        f"**{L(lang,'하지만 이것까지 증명하진 않는다','What it does NOT prove')}**"
                    )
                    st.write(
                        figure.get(
                            "what_it_does_not_prove",
                            "",
                        )
                    )

    # --------------------------------------------------------
    # CRITICAL READING
    # --------------------------------------------------------
    with tabs[5]:
        st.header(
            L(
                lang,
                "🧐 비판적으로 읽기",
                "🧐 Critical Reading",
            )
        )

        crit = analysis_data.get(
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
                f"### {L(lang,'🧪 내가 하나 더 한다면','🧪 One experiment I would add')}"
            )
            st.write(
                crit.get(
                    "missing_control_or_experiment",
                    "",
                )
            )

        with c2:
            st.markdown(
                f"### {L(lang,'🔀 가능한 대안 해석','🔀 Alternative explanations')}"
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
            f"### {L(lang,'👀 Reviewer라면 물을 질문','👀 Questions I would ask as a reviewer')}"
        )

        for item in crit.get(
            "reviewer_questions",
            [],
        ):
            st.markdown(
                f"- {item}"
            )

    # --------------------------------------------------------
    # LEARN NEXT
    # --------------------------------------------------------
    with tabs[6]:
        st.header(
            L(
                lang,
                "📚 이 논문을 다시 읽기 전에",
                "📚 Before reading the paper again",
            )
        )

        for item in sorted(
            analysis_data.get(
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

        st.divider()

        st.download_button(
            L(
                lang,
                "⬇️ AI Learning Map JSON 저장",
                "⬇️ Download AI Learning Map JSON",
            ),
            data=json.dumps(
                analysis_data,
                ensure_ascii=False,
                indent=2,
            ),
            file_name=(
                Path(
                    paper_name
                ).stem
                + "_lalstudy_v020.json"
            ),
            mime="application/json",
            use_container_width=True,
        )

        if st.button(
            L(
                lang,
                "🔄 이 논문 AI 분석 결과 지우기",
                "🔄 Clear this AI analysis",
            )
        ):
            st.session_state.pop(
                result_key,
                None,
            )
            st.rerun()


st.divider()

st.caption(
    L(
        lang,
        "LALSTUDY v0.2.0-beta · AI-generated study aids can contain errors. "
        "Study-specific claims should be checked against the original paper.",
        "LALSTUDY v0.2.0-beta · AI-generated study aids can contain errors. "
        "Study-specific claims should be checked against the original paper.",
    )
)
