"""LALSTUDY polished branded homepage.

This implementation recreates the generated mockup as real Streamlit UI.
The mockup image itself is NOT used as a background.

Original user-made brand assets are used directly:
- LALSTUDY logo
- tiger expressions
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st


ASSET_DIR = Path(__file__).parent / "assets" / "brand"

LOGO = ASSET_DIR / "lalstudy_logo.png"
TIGER_SMILE = ASSET_DIR / "tiger_smile.jpg"
TIGER_BASIC = ASSET_DIR / "tiger_basic.jpg"
TIGER_WINK = ASSET_DIR / "tiger_wink.jpg"
TIGER_SURPRISED = ASSET_DIR / "tiger_surprised.jpg"
TIGER_SERIOUS = ASSET_DIR / "tiger_serious.jpg"


def _L(lang: str, ko: str, en: str) -> str:
    return ko if lang == "ko" else en


def _copy(content, lang):
    return content.get(
        "ko" if lang == "ko" else "en",
        {},
    )


def _feature(
    *,
    image,
    title,
    body,
    page=None,
    button=None,
):
    with st.container(border=True):
        c1, c2 = st.columns(
            [0.26, 0.74],
            vertical_alignment="center",
        )

        with c1:
            st.image(
                image,
                width=78,
            )

        with c2:
            st.markdown(
                f'<div class="lal-card-title">{title}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="lal-card-copy">{body}</div>',
                unsafe_allow_html=True,
            )

        if page:
            st.page_link(
                page,
                label=button or title,
                use_container_width=True,
            )


def _benefit(icon, title, body):
    st.markdown(
        f"""
<div class="lal-benefit">
  <div class="lal-benefit-icon">{icon}</div>
  <div>
    <div class="lal-benefit-title">{title}</div>
    <div class="lal-benefit-copy">{body}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_home(
    content,
    *,
    lang,
    interactive=True,
):
    copy = _copy(
        content,
        lang,
    )

    title = copy.get(
        "home_brand_title",
        "LALSTUDY",
    )
    kicker = copy.get(
        "home_kicker",
        _L(
            lang,
            "논문을 읽는 즐거움, 연구가 더 가까워지는 시간",
            "Make papers easier to enter and research easier to understand",
        ),
    )
    description = copy.get(
        "home_description",
        _L(
            lang,
            "LALSTUDY는 생명과학 논문을 분석하고 학습하는 통합 도구입니다. "
            "논문의 핵심 논리와 Figure를 파악하고, 이해가 필요한 배경 개념과 "
            "실제 실험기법까지 하나의 학습 흐름으로 이어갈 수 있습니다.",
            "LALSTUDY is an integrated learning tool for life-science papers. "
            "Understand the core logic and Figures, then continue into the background concepts "
            "and experimental methods you need.",
        ),
    )

    st.markdown(
        """
<style>
.block-container {
    max-width: 1240px;
    padding-top: 1.15rem;
    padding-bottom: 3.5rem;
}

/* ---------- HERO ---------- */
.lal-hero-shell {
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(35, 73, 47, 0.08);
    border-radius: 22px;
    padding: 1.35rem 1.5rem 1.25rem 1.5rem;
    background:
        radial-gradient(circle at 88% 18%, rgba(77,184,91,.14) 0 9rem, transparent 9.1rem),
        radial-gradient(circle at 76% 105%, rgba(125,199,105,.13) 0 11rem, transparent 11.1rem),
        linear-gradient(125deg, #fffaf0 0%, #fffdf8 50%, #f3faee 100%);
    box-shadow: 0 10px 30px rgba(50,80,55,.045);
}

.lal-open-beta {
    display:inline-flex;
    align-items:center;
    gap:.35rem;
    padding:.28rem .6rem;
    border-radius:999px;
    background:#edf7ea;
    color:#148244;
    font-size:.72rem;
    font-weight:850;
    letter-spacing:.08em;
    margin-bottom:.55rem;
}

.lal-kicker {
    color:#187d42;
    font-size:.92rem;
    font-weight:800;
    margin-bottom:.35rem;
}

.lal-title {
    margin:.35rem 0 .55rem 0;
    font-size:clamp(2.8rem, 6vw, 5.3rem);
    line-height:.96;
    font-weight:950;
    letter-spacing:-.055em;
}

.lal-desc {
    max-width:720px;
    font-size:1.03rem;
    line-height:1.7;
    opacity:.80;
}

.lal-upload-card {
    margin-top:1rem;
    padding:.95rem 1rem;
    border-radius:16px;
    border:1px dashed rgba(255,255,255,.70);
    background:linear-gradient(135deg,#33b44e,#2fa845);
    color:white;
    box-shadow:0 8px 20px rgba(42,155,64,.15);
}

.lal-upload-title {
    font-size:1.05rem;
    font-weight:850;
    margin-bottom:.15rem;
}

.lal-upload-copy {
    font-size:.87rem;
    opacity:.88;
}

.lal-tiger-note {
    margin-top:.45rem;
    padding:.65rem .8rem;
    background:#eef8e9;
    border-radius:18px 18px 18px 5px;
    color:#176b37;
    font-size:.9rem;
    font-weight:750;
    line-height:1.45;
    text-align:center;
}

.lal-small-pills {
    margin-top:.65rem;
    display:flex;
    flex-wrap:wrap;
    gap:.35rem;
}

.lal-pill {
    padding:.22rem .5rem;
    border-radius:999px;
    background:rgba(19,128,62,.07);
    font-size:.74rem;
    opacity:.74;
}

/* ---------- SECTIONS ---------- */
.lal-section-title {
    font-size:1.55rem;
    font-weight:900;
    letter-spacing:-.025em;
    margin:0 0 .25rem 0;
}

.lal-section-copy {
    font-size:.92rem;
    opacity:.68;
    line-height:1.55;
    margin-bottom:.9rem;
}

.lal-card-title {
    font-size:1.03rem;
    font-weight:850;
    margin-bottom:.18rem;
}

.lal-card-copy {
    font-size:.88rem;
    line-height:1.5;
    opacity:.72;
}

/* Streamlit containers that hold the 3 product cards */
div[data-testid="stHorizontalBlock"] > div:nth-child(1) div[data-testid="stVerticalBlockBorderWrapper"] {
    background:linear-gradient(135deg,#f1fbef,#fbfefb);
}
div[data-testid="stHorizontalBlock"] > div:nth-child(2) div[data-testid="stVerticalBlockBorderWrapper"] {
    background:linear-gradient(135deg,#fffaf0,#fffdf8);
}
div[data-testid="stHorizontalBlock"] > div:nth-child(3) div[data-testid="stVerticalBlockBorderWrapper"] {
    background:linear-gradient(135deg,#fff5ef,#fffaf7);
}

/* ---------- FLOW ---------- */
.lal-flow-wrap {
    border:1px solid rgba(41,69,50,.09);
    border-radius:18px;
    padding:1.05rem 1.15rem;
    background:linear-gradient(180deg,#fbfdff,#f8fbfc);
}

.lal-flow-row {
    display:grid;
    grid-template-columns:repeat(5, 1fr);
    gap:.55rem;
    margin-top:.8rem;
}

.lal-flow-item {
    text-align:center;
    position:relative;
    padding:.4rem;
}

.lal-flow-item:not(:last-child)::after {
    content:"→";
    position:absolute;
    right:-.45rem;
    top:1.25rem;
    color:rgba(31,41,55,.28);
    font-size:1.35rem;
}

.lal-flow-icon {
    width:3rem;
    height:3rem;
    margin:0 auto .45rem auto;
    border-radius:999px;
    display:flex;
    align-items:center;
    justify-content:center;
    background:#e9f7ea;
    font-size:1.25rem;
}

.lal-flow-title {
    font-weight:850;
    font-size:.92rem;
}

.lal-flow-copy {
    font-size:.76rem;
    margin-top:.15rem;
    opacity:.64;
    line-height:1.35;
}

/* ---------- BENEFITS ---------- */
.lal-benefit {
    display:flex;
    gap:.8rem;
    align-items:flex-start;
    min-height:118px;
    padding:.9rem .95rem;
    border-radius:16px;
    border:1px solid rgba(41,69,50,.09);
    background:#fff;
}

.lal-benefit-icon {
    min-width:2.65rem;
    height:2.65rem;
    border-radius:999px;
    display:flex;
    align-items:center;
    justify-content:center;
    background:#eef8eb;
    font-size:1.2rem;
}

.lal-benefit-title {
    font-weight:850;
    margin-bottom:.25rem;
}

.lal-benefit-copy {
    font-size:.86rem;
    line-height:1.48;
    opacity:.69;
}

/* ---------- QUOTE ---------- */
.lal-quote {
    padding:.85rem 1rem;
    border-radius:15px;
    background:linear-gradient(90deg,#eef9ed,#f7fcf6);
    border:1px solid rgba(40,133,69,.08);
    line-height:1.55;
}

/* page-link polish */
div[data-testid="stPageLink"] a {
    border-radius:12px !important;
    font-weight:750 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # ============================================================
    # HERO
    # ============================================================
    st.markdown(
        '<div class="lal-hero-shell">',
        unsafe_allow_html=True,
    )

    hero_left, hero_right = st.columns(
        [1.45, .55],
        gap="large",
        vertical_alignment="center",
    )

    with hero_left:
        st.markdown(
            '<div class="lal-open-beta">● OPEN BETA</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="lal-kicker">{kicker}</div>',
            unsafe_allow_html=True,
        )

        # Original user-made logo.
        st.image(
            LOGO,
            width=390,
        )

        st.markdown(
            f'<div class="lal-title">{title}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="lal-desc">{description}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
<div class="lal-upload-card">
  <div class="lal-upload-title">📄 {_L(lang, "논문 PDF로 시작하기", "Start with a paper PDF")}</div>
  <div class="lal-upload-copy">
    {_L(lang, "PDF를 업로드하면 핵심 내용과 Figure부터 차근차근 읽을 수 있습니다.",
        "Upload a PDF and work through the core story and Figures step by step.")}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)

        with c1:
            if interactive:
                st.page_link(
                    "pages/1_Learn_a_Paper.py",
                    label=copy.get(
                        "home_primary_cta",
                        _L(
                            lang,
                            "Learn a Paper 시작하기 →",
                            "Start Learn a Paper →",
                        ),
                    ),
                    use_container_width=True,
                )
            else:
                st.button(
                    "Learn a Paper",
                    disabled=True,
                    use_container_width=True,
                    key="home_mock_preview_1",
                )

        with c2:
            if interactive:
                st.page_link(
                    "pages/2_Method_Wiki.py",
                    label=copy.get(
                        "home_secondary_cta",
                        _L(
                            lang,
                            "Method Wiki 둘러보기 →",
                            "Explore Method Wiki →",
                        ),
                    ),
                    use_container_width=True,
                )
            else:
                st.button(
                    "Method Wiki",
                    disabled=True,
                    use_container_width=True,
                    key="home_mock_preview_2",
                )

        st.markdown(
            """
<div class="lal-small-pills">
  <span class="lal-pill">PDF</span>
  <span class="lal-pill">Figure-first</span>
  <span class="lal-pill">Concept Archive</span>
  <span class="lal-pill">Method → Paper → Panel</span>
</div>
""",
            unsafe_allow_html=True,
        )

    with hero_right:
        st.markdown(
            '<div class="lal-tiger-note">'
            + _L(
                lang,
                "어려운 논문도<br>함께라면 읽을 수 있어요!",
                "Complex papers become easier<br>when we connect the pieces.",
            )
            + "</div>",
            unsafe_allow_html=True,
        )

        st.image(
            TIGER_WINK,
            use_container_width=True,
        )

        st.caption(
            _L(
                lang,
                "오늘은 어디서부터 시작할까요?",
                "Where should we start today?",
            )
        )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )

    st.write("")

    # ============================================================
    # PRODUCT CARDS
    # ============================================================
    st.markdown(
        '<div class="lal-section-title">'
        + _L(
            lang,
            "어디서 시작할까요?",
            "Choose your starting point",
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="lal-section-copy">'
        + _L(
            lang,
            "논문 읽기, 개념 이해, 실험기법 학습을 각각 따로 하지 않고 서로 이어서 사용할 수 있습니다.",
            "Move between paper reading, concept learning, and experimental methods without breaking your study flow.",
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    card1, card2, card3 = st.columns(
        3,
        gap="medium",
    )

    with card1:
        _feature(
            image=TIGER_SERIOUS,  # eyebrows preserved
            title="Learn a Paper",
            body=copy.get(
                "home_feature_learn_text",
                _L(
                    lang,
                    "연구의 핵심 논리와 Figure, 실험전략까지 논문 한 편을 단계적으로 읽습니다.",
                    "Read one paper step by step through its core logic, Figures, and experimental strategy.",
                ),
            ),
            page=(
                "pages/1_Learn_a_Paper.py"
                if interactive
                else None
            ),
            button=_L(
                lang,
                "논문 읽기 →",
                "Read a paper →",
            ),
        )

    with card2:
        _feature(
            image=TIGER_SMILE,
            title="Knowledge Archive",
            body=copy.get(
                "home_feature_archive_text",
                _L(
                    lang,
                    "막히는 용어·구절을 찾아보고 저장해, 다른 논문을 읽을 때 다시 꺼내봅니다.",
                    "Look up unfamiliar terms, save them, and reuse them while reading future papers.",
                ),
            ),
        )
        st.caption(
            _L(
                lang,
                "왼쪽 사이드바의 🧠 Knowledge Archive",
                "Use 🧠 Knowledge Archive in the left sidebar",
            )
        )

    with card3:
        _feature(
            image=TIGER_BASIC,
            title="Method Wiki",
            body=copy.get(
                "home_feature_method_text",
                _L(
                    lang,
                    "실험기법의 원리와 해석을 배우고 실제 논문의 Figure·panel 사용 사례까지 연결합니다.",
                    "Learn how methods work and connect them to real paper Figures and panels.",
                ),
            ),
            page=(
                "pages/2_Method_Wiki.py"
                if interactive
                else None
            ),
            button=_L(
                lang,
                "실험기법 보기 →",
                "Explore methods →",
            ),
        )

    st.write("")

    # ============================================================
    # LEARNING FLOW
    # ============================================================
    st.markdown(
        '<div class="lal-flow-wrap">',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="lal-section-title">'
        + _L(
            lang,
            "논문 학습 흐름",
            "Paper learning flow",
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="lal-section-copy">'
        + _L(
            lang,
            "한 편의 논문이 깊은 이해로 이어지는 과정을 하나의 흐름으로 연결합니다.",
            "Connect one paper to the deeper questions that appear while you read.",
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    flow = [
        (
            "📄",
            _L(lang, "PDF 업로드", "Upload PDF"),
            _L(lang, "논문으로 시작", "Start from the paper"),
        ),
        (
            "🎯",
            _L(lang, "핵심 내용", "Core story"),
            _L(lang, "질문·결과·결론", "Question, results, conclusion"),
        ),
        (
            "🖼️",
            "Figure",
            _L(lang, "원문 Figure 이해", "Understand original Figures"),
        ),
        (
            "💡",
            _L(lang, "개념 이해", "Concepts"),
            _L(lang, "배경지식 연결", "Connect background knowledge"),
        ),
        (
            "🧪",
            _L(lang, "실험기법", "Methods"),
            _L(lang, "실제 사용까지", "Trace real usage"),
        ),
    ]

    flow_html = '<div class="lal-flow-row">'
    for icon, flow_title, flow_copy in flow:
        flow_html += f"""
<div class="lal-flow-item">
  <div class="lal-flow-icon">{icon}</div>
  <div class="lal-flow-title">{flow_title}</div>
  <div class="lal-flow-copy">{flow_copy}</div>
</div>
"""
    flow_html += "</div>"

    st.markdown(
        flow_html,
        unsafe_allow_html=True,
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )

    st.write("")

    # ============================================================
    # WHY
    # ============================================================
    why_left, why_right = st.columns(
        [0.28, 0.72],
        gap="large",
        vertical_alignment="center",
    )

    with why_left:
        st.markdown(
            '<div class="lal-section-title">'
            + _L(
                lang,
                "왜 LALSTUDY인가?",
                "Why LALSTUDY?",
            )
            + "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="lal-section-copy">'
            + _L(
                lang,
                "생명과학 논문을 처음부터 끝까지 혼자 버티지 않아도 되도록, "
                "읽다가 생기는 다음 질문을 바로 이어주는 학습 경험을 목표로 합니다.",
                "A learning experience that helps you follow the next question instead of struggling through a paper alone.",
            )
            + "</div>",
            unsafe_allow_html=True,
        )

        st.image(
            TIGER_SURPRISED,
            width=118,
        )

    with why_right:
        b1, b2, b3 = st.columns(
            3,
            gap="small",
        )

        with b1:
            _benefit(
                "⚡",
                _L(
                    lang,
                    "빠른 논문 진입",
                    "Faster entry",
                ),
                _L(
                    lang,
                    "긴 논문에서도 먼저 봐야 할 질문과 핵심 흐름부터 잡습니다.",
                    "Find the question and core story before getting lost in a long paper.",
                ),
            )

        with b2:
            _benefit(
                "📊",
                _L(
                    lang,
                    "Figure 중심 이해",
                    "Figure-first",
                ),
                _L(
                    lang,
                    "원문 Figure와 legend를 중심으로 실제 데이터가 무엇을 보여주는지 따라갑니다.",
                    "Follow what the data show through the original Figures and legends.",
                ),
            )

        with b3:
            _benefit(
                "🔗",
                _L(
                    lang,
                    "개념 · 실험 연결",
                    "Concept → method",
                ),
                _L(
                    lang,
                    "배경 개념에서 멈추지 않고 실제 실험기법과 논문 사용 사례까지 이어갑니다.",
                    "Move from background concepts into methods and real paper usage.",
                ),
            )

    st.write("")

    quote_left, quote_right = st.columns(
        [.12, .88],
        vertical_alignment="center",
    )

    with quote_left:
        st.image(
            TIGER_SMILE,
            width=86,
        )

    with quote_right:
        st.markdown(
            '<div class="lal-quote">'
            + _L(
                lang,
                "<b>좋은 논문은 좋은 질문에서 시작하고, 깊은 이해는 연결된 질문에서 시작합니다.</b><br>"
                "LALSTUDY는 논문 한 편이 다음 배움으로 이어지도록 돕습니다.",
                "<b>Good papers begin with good questions, and deep understanding comes from keeping those questions connected.</b><br>"
                "LALSTUDY helps one paper lead naturally into the next piece of learning.",
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    st.caption(
        _L(
            lang,
            "Open Beta · 일부 자동 분석과 Method/Figure 연결은 원문 확인이 필요할 수 있습니다.",
            "Open Beta · Some automated analysis and Method/Figure links may require source verification.",
        )
    )
