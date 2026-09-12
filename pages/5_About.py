import streamlit as st

from i18n import language_selector, L
from sidebar_ui import render_public_sidebar


APP_VERSION = "v0.6.2-open-beta"


st.set_page_config(
    page_title="LALSTUDY · About",
    page_icon="ℹ️",
    layout="wide",
)

lang = language_selector()

render_public_sidebar(
    lang=lang
)


st.markdown(
    """
    <style>
    .block-container {
        max-width: 1040px;
        padding-top: 2.4rem;
        padding-bottom: 4rem;
    }

    .about-badge {
        display:inline-block;
        padding:.32rem .68rem;
        border-radius:999px;
        border:1px solid rgba(49,51,63,.14);
        font-size:.76rem;
        font-weight:800;
        letter-spacing:.07em;
        margin-bottom:.8rem;
    }

    .about-lead {
        font-size:1.08rem;
        line-height:1.75;
        max-width:820px;
        opacity:.78;
        margin-bottom:1.2rem;
    }

    .about-card {
        border:1px solid rgba(49,51,63,.12);
        border-radius:16px;
        padding:1rem 1.05rem;
        min-height:145px;
        background:rgba(255,255,255,.75);
    }

    .about-card-title {
        font-weight:800;
        margin-bottom:.45rem;
    }

    .about-card-copy {
        opacity:.72;
        line-height:1.6;
        font-size:.93rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    '<div class="about-badge">OPEN BETA</div>',
    unsafe_allow_html=True,
)

st.title(
    L(
        lang,
        "LALSTUDY 소개",
        "About LALSTUDY",
    )
)

st.markdown(
    (
        '<div class="about-lead">'
        + L(
            lang,
            "LALSTUDY는 과학 논문을 단순히 요약하는 대신, "
            "연구의 핵심 논리·Figure·배경개념·실험기법을 서로 연결해 "
            "다음 질문으로 자연스럽게 이어지도록 만든 학습 플랫폼입니다.",
            "LALSTUDY is a scientific-learning platform built to connect "
            "a paper's core logic, Figures, prerequisite concepts, and experimental methods—"
            "so reading naturally leads to the next useful question.",
        )
        + "</div>"
    ),
    unsafe_allow_html=True,
)


st.header(
    L(
        lang,
        "Open Beta에서 제공하는 것",
        "What is available in Open Beta",
    )
)

items = [
    (
        "📄",
        L(lang, "Learn a Paper", "Learn a Paper"),
        L(
            lang,
            "PDF를 업로드해 Core Analysis, 원문 Figure/legend, 선수지식, 실험전략, 비판적 읽기를 단계적으로 확인합니다.",
            "Upload a PDF and move through Core Analysis, original Figures/legends, prerequisites, experimental strategy, and critical reading.",
        ),
    ),
    (
        "🖼️",
        L(lang, "Figure 이해", "Figure understanding"),
        L(
            lang,
            "각 Figure를 독립적으로 해석해 무엇을 측정했고 무엇을 보여주는지, 무엇까지는 말할 수 없는지 확인합니다.",
            "Analyze Figures independently to see what was measured, what the result supports, and what it does not establish.",
        ),
    ),
    (
        "🧬",
        L(lang, "Method Wiki", "Method Wiki"),
        L(
            lang,
            "실험기법을 검색하거나 category로 탐색하고 실제 논문·Figure·panel에서 어떻게 쓰였는지 연결해서 봅니다.",
            "Search or browse experimental methods and connect them to how they are used in real papers, Figures, and panels.",
        ),
    ),
    (
        "🧠",
        L(lang, "Knowledge Archive", "Knowledge Archive"),
        L(
            lang,
            "한 번 찾아본 개념 설명을 재사용 가능한 지식으로 저장해 다른 논문을 읽을 때 다시 활용합니다.",
            "Save concept explanations as reusable knowledge and bring them back when reading other papers.",
        ),
    ),
]

cols = st.columns(2)

for i, (
    icon,
    title,
    copy,
) in enumerate(
    items
):
    with cols[
        i % 2
    ]:
        st.markdown(
            f"""
            <div class="about-card">
              <div class="about-card-title">{icon} {title}</div>
              <div class="about-card-copy">{copy}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")


st.header(
    L(
        lang,
        "Corpus 범위",
        "Corpus scope",
    )
)

st.markdown(
    L(
        lang,
        """
현재 corpus 기반 기능은 면역학 관련 키워드 검색으로 수집한 약 **1,000편의 Nature Communications open-access 논문**을 사용합니다.

따라서 Method Wiki의 논문 수나 사용 빈도는 **이 corpus 안에서의 관찰값**이며,
전체 면역학 문헌의 실제 빈도를 의미하지 않습니다.
""",
        """
Corpus-based features currently use approximately **1,000 Nature Communications open-access papers retrieved with immunology-related search terms**.

Method counts and usage frequencies therefore describe this corpus only; they are not prevalence estimates for the full immunology literature.
""",
    )
)


st.header(
    L(
        lang,
        "데이터와 AI",
        "Data and AI",
    )
)

st.markdown(
    L(
        lang,
        """
- AI 분석은 OpenAI 기반으로 동작합니다.
- 동일 논문의 재분석 비용과 대기 시간을 줄이기 위해 구조화된 분석 결과를 재사용할 수 있습니다.
- 공유 분석 cache에는 업로드한 **PDF 원문 자체나 Figure image bytes를 저장하지 않도록 설계**했습니다.
- Figure crop은 업로드된 PDF에서 필요할 때 생성합니다.
- Method Wiki의 설명은 재사용 가능한 method-level 지식으로 저장됩니다.
""",
        """
- AI analysis is powered by OpenAI.
- Structured analysis results can be reused to reduce repeated waiting time and duplicate model calls for the same paper.
- The shared analysis cache is designed **not to store uploaded PDF bytes or Figure image bytes**.
- Figure crops are generated from the uploaded PDF when needed.
- Method Wiki descriptions are stored as reusable method-level knowledge.
""",
    )
)


st.header(
    L(
        lang,
        "Open Beta에서 알아둘 점",
        "Open Beta notes",
    )
)

st.markdown(
    L(
        lang,
        """
- 자동 method detection과 Figure/panel 연결에는 일부 false positive 또는 누락이 있을 수 있습니다.
- 논문 PDF의 text layer와 문서 구조에 따라 추출 품질이 달라질 수 있습니다.
- Figure별 AI 해석은 학습 보조이며 원문 결과와 legend를 함께 확인하는 것이 좋습니다.
- corpus와 Method Wiki는 계속 확장·교정될 수 있습니다.
""",
        """
- Automated method detection and Figure/panel linking can occasionally contain false positives or omissions.
- Extraction quality can vary with the PDF text layer and document structure.
- Per-Figure AI interpretation is a learning aid; read it together with the original result and legend.
- The corpus and Method Wiki may continue to expand and be corrected during Open Beta.
""",
    )
)


st.header(
    L(
        lang,
        "주요 변화",
        "Major milestones",
    )
)

st.markdown(
    L(
        lang,
        """
**Open Beta · v0.6**  
사용자용 화면을 정리하고 핵심 기능을 `Learn a Paper`와 `Method Wiki`에 집중했습니다.

**v0.5 · Method Wiki**  
실험기법 검색, category 탐색, Method → Paper → Figure → Panel 연결을 도입했습니다.

**v0.4 · Persistent learning**  
공유 paper-analysis cache, Knowledge Archive, OpenAI-only AI 분석 구조를 도입했습니다.

**v0.2–0.3 · Deep paper learning**  
Figure 추출과 Figure별 AI 분석, 선수지식·실험전략·비판적 읽기 흐름을 구축했습니다.
""",
        """
**Open Beta · v0.6**  
Simplified the public product around two core experiences: `Learn a Paper` and `Method Wiki`.

**v0.5 · Method Wiki**  
Added method search, category browsing, and Method → Paper → Figure → Panel connections.

**v0.4 · Persistent learning**  
Added reusable paper-analysis caching, Knowledge Archive, and an OpenAI-only AI architecture.

**v0.2–0.3 · Deep paper learning**  
Built Figure extraction, per-Figure AI analysis, prerequisites, experimental strategy, and critical-reading flows.
""",
    )
)


st.divider()

st.page_link(
    "app.py",
    label=L(
        lang,
        "← 홈으로",
        "← Back home",
    ),
    icon="🏠",
)
