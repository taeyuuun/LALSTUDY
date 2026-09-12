"""LALSTUDY branded public landing page.

This page intentionally uses the user's original logo and tiger artwork.
The generated mockup is a design reference only; the app remains real,
interactive Streamlit UI.
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


def _copy(content, lang):
    return content.get(
        "ko" if lang == "ko" else "en",
        {},
    )


def _L(lang, ko, en):
    return ko if lang == "ko" else en


def _int(value, fallback, lo, hi):
    try:
        value = int(value)
    except Exception:
        value = fallback
    return max(lo, min(hi, value))


def _feature_card(
    *,
    tiger,
    title,
    body,
    link=None,
    link_label=None,
    note=None,
):
    with st.container(border=True):
        image_col, text_col = st.columns(
            [0.28, 0.72],
            vertical_alignment="center",
        )

        with image_col:
            st.image(
                tiger,
                width=88,
            )

        with text_col:
            st.markdown(
                f"### {title}"
            )
            st.caption(
                body
            )

        if link:
            st.page_link(
                link,
                label=link_label or title,
                use_container_width=True,
            )

        if note:
            st.caption(
                note
            )


def _flow_step(
    icon,
    title,
    body,
):
    st.markdown(
        f"""
<div class="lal-flow-step-v2">
  <div class="lal-flow-icon">{icon}</div>
  <div class="lal-flow-title-v2">{title}</div>
  <div class="lal-flow-body-v2">{body}</div>
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
    design = content.get(
        "design",
        {},
    )
    copy = _copy(
        content,
        lang,
    )

    page_width = _int(
        design.get(
            "page_max_width_px",
            1180,
        ),
        1180,
        900,
        1500,
    )

    # New v2 home keys deliberately do not collide with old published config.
    brand_title = copy.get(
        "home_brand_title",
        "LALSTUDY",
    )
    kicker = copy.get(
        "home_kicker",
        _L(
            lang,
            "논문을 읽고, 연구를 이해하는 하나의 흐름",
            "One flow from reading papers to understanding research",
        ),
    )
    description = copy.get(
        "home_description",
        _L(
            lang,
            "LALSTUDY는 생명과학 논문을 분석하고 학습하는 도구입니다. "
            "PDF 한 편에서 연구의 핵심 논리와 Figure를 파악하고, "
            "이해가 필요한 개념과 실제 실험기법까지 이어서 학습할 수 있습니다.",
            "LALSTUDY is a learning tool for analyzing life-science papers. "
            "Start from one PDF, understand the study logic and Figures, "
            "then continue into the concepts and experimental methods you need.",
        ),
    )

    st.markdown(
        f"""
<style>
.block-container {{
    max-width:{page_width}px;
    padding-top:1.55rem;
    padding-bottom:4rem;
}}

.lal-kicker {{
    display:inline-block;
    color:#16843f;
    font-size:0.88rem;
    font-weight:750;
    margin-bottom:0.35rem;
}}

.lal-brand-title {{
    font-size:clamp(2.5rem, 5vw, 4.5rem);
    line-height:1.0;
    letter-spacing:-0.045em;
    font-weight:900;
    margin:0.15rem 0 0.8rem 0;
}}

.lal-product-copy {{
    font-size:1.05rem;
    line-height:1.72;
    max-width:760px;
    opacity:0.80;
}}

.lal-mini-label {{
    font-size:0.78rem;
    font-weight:800;
    letter-spacing:0.08em;
    color:#188648;
    margin-bottom:0.25rem;
}}

.lal-section-heading {{
    font-size:1.65rem;
    font-weight:850;
    letter-spacing:-0.025em;
    margin-top:0.2rem;
    margin-bottom:0.25rem;
}}

.lal-section-sub {{
    opacity:0.68;
    line-height:1.6;
    margin-bottom:0.8rem;
}}

.lal-flow-step-v2 {{
    text-align:center;
    padding:0.35rem 0.2rem;
}}

.lal-flow-icon {{
    width:3.1rem;
    height:3.1rem;
    margin:0 auto 0.45rem auto;
    border-radius:999px;
    background:rgba(28, 169, 76, 0.10);
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:1.35rem;
}}

.lal-flow-title-v2 {{
    font-weight:800;
    font-size:0.95rem;
}}

.lal-flow-body-v2 {{
    margin-top:0.18rem;
    font-size:0.82rem;
    line-height:1.45;
    opacity:0.68;
}}

.lal-benefit {{
    min-height:132px;
    padding:0.95rem 1rem;
    border-radius:15px;
    border:1px solid rgba(49,51,63,.10);
    background:rgba(255,255,255,.76);
}}

.lal-benefit-title {{
    font-weight:800;
    margin-bottom:0.35rem;
}}

.lal-benefit-body {{
    opacity:0.72;
    font-size:0.92rem;
    line-height:1.55;
}}

.lal-quote {{
    margin-top:1rem;
    padding:0.95rem 1.1rem;
    border-radius:15px;
    background:rgba(28,169,76,0.07);
    border:1px solid rgba(28,169,76,0.10);
    font-size:0.95rem;
    line-height:1.6;
}}
</style>
""",
        unsafe_allow_html=True,
    )

    # ============================================================
    # HERO
    # ============================================================
    with st.container(border=True):
        left, right = st.columns(
            [1.35, 0.65],
            gap="large",
            vertical_alignment="center",
        )

        with left:
            st.markdown(
                '<div class="lal-mini-label">OPEN BETA</div>',
                unsafe_allow_html=True,
            )

            # The real user-made logo, not the generated mockup logo.
            st.image(
                LOGO,
                width=390,
            )

            st.markdown(
                f'<div class="lal-kicker">{kicker}</div>',
                unsafe_allow_html=True,
            )

            st.markdown(
                f'<div class="lal-brand-title">{brand_title}</div>',
                unsafe_allow_html=True,
            )

            st.markdown(
                f'<div class="lal-product-copy">{description}</div>',
                unsafe_allow_html=True,
            )

            st.write("")

            cta1, cta2 = st.columns(
                2
            )

            with cta1:
                if interactive:
                    st.page_link(
                        "pages/1_Learn_a_Paper.py",
                        label=copy.get(
                            "home_primary_cta",
                            _L(
                                lang,
                                "📄 논문 분석 시작하기",
                                "📄 Analyze a paper",
                            ),
                        ),
                        use_container_width=True,
                    )
                else:
                    st.button(
                        copy.get(
                            "home_primary_cta",
                            "📄 논문 분석 시작하기",
                        ),
                        disabled=True,
                        use_container_width=True,
                        key="home_preview_primary",
                    )

            with cta2:
                if interactive:
                    st.page_link(
                        "pages/2_Method_Wiki.py",
                        label=copy.get(
                            "home_secondary_cta",
                            _L(
                                lang,
                                "🧬 실험기법 찾아보기",
                                "🧬 Explore methods",
                            ),
                        ),
                        use_container_width=True,
                    )
                else:
                    st.button(
                        copy.get(
                            "home_secondary_cta",
                            "🧬 실험기법 찾아보기",
                        ),
                        disabled=True,
                        use_container_width=True,
                        key="home_preview_secondary",
                    )

            st.caption(
                _L(
                    lang,
                    "PDF에서 시작해 핵심 내용 → Figure → 개념 → 실험기법으로 이어집니다.",
                    "Start from a PDF and move through the core story → Figures → concepts → methods.",
                )
            )

        with right:
            # Exact original wink mascot. The eyebrow is preserved.
            st.image(
                TIGER_WINK,
                use_container_width=True,
            )
            st.caption(
                _L(
                    lang,
                    "어려운 논문도 하나씩 연결하면 읽을 수 있어요.",
                    "Complex papers become manageable when you connect them step by step.",
                )
            )

    st.write("")

    # ============================================================
    # QUICK START
    # ============================================================
    st.markdown(
        '<div class="lal-section-heading">'
        + _L(
            lang,
            "어디서 시작할까요?",
            "Where do you want to start?",
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="lal-section-sub">'
        + _L(
            lang,
            "논문을 읽고 싶은지, 막힌 개념을 찾고 싶은지, 실험기법을 배우고 싶은지에 따라 바로 이동하세요.",
            "Jump directly to paper reading, concept lookup, or experimental-method learning.",
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    f1, f2, f3 = st.columns(
        3,
        gap="medium",
    )

    with f1:
        _feature_card(
            # Serious tiger = original artwork with eyebrows intact.
            tiger=TIGER_SERIOUS,
            title=copy.get(
                "home_feature_learn_title",
                "Learn a Paper",
            ),
            body=copy.get(
                "home_feature_learn_text",
                _L(
                    lang,
                    "PDF 한 편의 핵심 논리, Figure, 실험전략을 단계적으로 읽습니다.",
                    "Read one PDF through its core logic, Figures, and experimental strategy.",
                ),
            ),
            link=(
                "pages/1_Learn_a_Paper.py"
                if interactive
                else None
            ),
            link_label=_L(
                lang,
                "Learn a Paper 열기 →",
                "Open Learn a Paper →",
            ),
        )

    with f2:
        _feature_card(
            tiger=TIGER_SMILE,
            title=copy.get(
                "home_feature_archive_title",
                "Knowledge Archive",
            ),
            body=copy.get(
                "home_feature_archive_text",
                _L(
                    lang,
                    "논문을 읽다가 막힌 용어·구절을 찾아보고 저장해 다시 꺼내봅니다.",
                    "Look up unfamiliar terms, save them, and reuse them while reading future papers.",
                ),
            ),
            note=_L(
                lang,
                "왼쪽 사이드바의 🧠 Knowledge Archive에서 바로 사용",
                "Use 🧠 Knowledge Archive directly from the left sidebar",
            ),
        )

    with f3:
        _feature_card(
            tiger=TIGER_BASIC,
            title=copy.get(
                "home_feature_method_title",
                "Method Wiki",
            ),
            body=copy.get(
                "home_feature_method_text",
                _L(
                    lang,
                    "실험기법의 원리와 해석법을 배우고, 실제 논문 Figure·panel 사용 사례까지 연결합니다.",
                    "Learn method principles and interpretation, then connect them to real paper Figures and panels.",
                ),
            ),
            link=(
                "pages/2_Method_Wiki.py"
                if interactive
                else None
            ),
            link_label=_L(
                lang,
                "Method Wiki 열기 →",
                "Open Method Wiki →",
            ),
        )

    st.write("")

    # ============================================================
    # LEARNING FLOW
    # ============================================================
    with st.container(border=True):
        st.markdown(
            '<div class="lal-section-heading">'
            + _L(
                lang,
                "논문 학습 흐름",
                "Paper learning flow",
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="lal-section-sub">'
            + _L(
                lang,
                "한 편의 논문을 읽다가 생기는 다음 질문을 끊지 않고 이어갑니다.",
                "Keep moving through the next question that naturally appears while reading a paper.",
            )
            + "</div>",
            unsafe_allow_html=True,
        )

        cols = st.columns(
            5
        )
        steps = [
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
                _L(lang, "원문과 함께 이해", "Read with the source"),
            ),
            (
                "🧠",
                _L(lang, "개념 이해", "Concepts"),
                _L(lang, "막히는 배경지식", "Resolve knowledge gaps"),
            ),
            (
                "🧬",
                _L(lang, "실험기법", "Methods"),
                _L(lang, "원리부터 실제 사용까지", "From principle to real use"),
            ),
        ]

        for col, step in zip(
            cols,
            steps,
        ):
            with col:
                _flow_step(
                    *step
                )

    st.write("")

    # ============================================================
    # WHY
    # ============================================================
    st.markdown(
        '<div class="lal-section-heading">'
        + _L(
            lang,
            "왜 LALSTUDY인가?",
            "Why LALSTUDY?",
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    b1, b2, b3 = st.columns(
        3,
        gap="medium",
    )

    benefits = [
        (
            b1,
            "⚡",
            _L(lang, "빠른 논문 진입", "Faster entry"),
            _L(
                lang,
                "긴 논문에서도 먼저 봐야 할 연구 질문과 핵심 흐름을 잡을 수 있습니다.",
                "Find the research question and core story before getting lost in a long paper.",
            ),
        ),
        (
            b2,
            "📊",
            _L(lang, "Figure 중심 이해", "Figure-first understanding"),
            _L(
                lang,
                "원문 Figure와 legend를 중심으로 실제 데이터가 무엇을 말하는지 따라갑니다.",
                "Follow what the data actually show through original Figures and legends.",
            ),
        ),
        (
            b3,
            "🔗",
            _L(lang, "개념과 실험 연결", "Connect concepts and methods"),
            _L(
                lang,
                "모르는 배경개념에서 멈추지 않고 실제 실험기법과 논문 사용 사례까지 이어갑니다.",
                "Move from unfamiliar concepts into the experimental methods and real examples behind them.",
            ),
        ),
    ]

    for col, icon, title, body in benefits:
        with col:
            st.markdown(
                f"""
<div class="lal-benefit">
  <div style="font-size:1.35rem; margin-bottom:0.45rem;">{icon}</div>
  <div class="lal-benefit-title">{title}</div>
  <div class="lal-benefit-body">{body}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    quote_col, tiger_col = st.columns(
        [0.82, 0.18],
        vertical_alignment="center",
    )

    with quote_col:
        st.markdown(
            '<div class="lal-quote">'
            + _L(
                lang,
                "<b>좋은 논문을 더 빨리 읽는 것보다, 좋은 질문을 놓치지 않고 끝까지 이해하는 것.</b><br>"
                "LALSTUDY는 그 학습 흐름을 이어주는 도구를 목표로 합니다.",
                "<b>The goal is not just to read faster, but to keep the right questions connected until the paper makes sense.</b><br>"
                "LALSTUDY is built to support that learning flow.",
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    with tiger_col:
        st.image(
            TIGER_SURPRISED,
            use_container_width=True,
        )

    if design.get(
        "show_open_beta_note",
        True,
    ):
        st.caption(
            _L(
                lang,
                "Open Beta · 일부 자동 분석과 Method/Figure 연결은 원문 확인이 필요할 수 있습니다.",
                "Open Beta · Some automated analysis and Method/Figure links may require source verification.",
            )
        )
