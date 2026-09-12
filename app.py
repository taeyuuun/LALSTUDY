import streamlit as st

from i18n import language_selector, L
from knowledge_widget import render_knowledge_archive_widget


APP_VERSION = "v0.6.0-open-beta"


st.set_page_config(
    page_title="LALSTUDY",
    page_icon="🧬",
    layout="wide",
)

lang = language_selector()

# Keep the reusable learning archive globally accessible,
# but remove developer-facing usage/debug panels from the landing page.
render_knowledge_archive_widget(
    lang=lang
)


st.markdown(
    """
    <style>
    .block-container {
        max-width: 1180px;
        padding-top: 2.2rem;
        padding-bottom: 4rem;
    }

    .lal-badge {
        display: inline-block;
        padding: .34rem .72rem;
        border-radius: 999px;
        border: 1px solid rgba(49, 51, 63, .14);
        background: rgba(247, 249, 252, .88);
        font-size: .76rem;
        font-weight: 800;
        letter-spacing: .08em;
        margin-bottom: 1rem;
    }

    .lal-hero-title {
        font-size: clamp(2.4rem, 5.2vw, 4.6rem);
        line-height: 1.05;
        letter-spacing: -.045em;
        font-weight: 850;
        margin: 0 0 1rem 0;
        max-width: 930px;
    }

    .lal-hero-copy {
        font-size: 1.12rem;
        line-height: 1.75;
        opacity: .78;
        max-width: 780px;
        margin-bottom: 1.5rem;
    }

    .lal-section-title {
        font-size: 1.65rem;
        font-weight: 820;
        letter-spacing: -.02em;
        margin-top: .2rem;
        margin-bottom: .35rem;
    }

    .lal-section-copy {
        opacity: .68;
        line-height: 1.65;
        margin-bottom: 1.2rem;
    }

    .lal-feature {
        border: 1px solid rgba(49, 51, 63, .12);
        border-radius: 18px;
        padding: 1.15rem 1.2rem;
        background: rgba(255,255,255,.76);
        min-height: 158px;
    }

    .lal-feature-icon {
        font-size: 1.3rem;
        margin-bottom: .65rem;
    }

    .lal-feature-title {
        font-size: 1.05rem;
        font-weight: 800;
        margin-bottom: .35rem;
    }

    .lal-feature-copy {
        line-height: 1.6;
        opacity: .72;
        font-size: .93rem;
    }

    .lal-flow {
        border: 1px solid rgba(49, 51, 63, .12);
        border-radius: 20px;
        padding: 1.25rem 1.3rem;
        background: rgba(248, 249, 251, .70);
        min-height: 225px;
    }

    .lal-flow-title {
        font-size: 1.15rem;
        font-weight: 820;
        margin-bottom: .75rem;
    }

    .lal-flow-step {
        margin: .45rem 0;
        line-height: 1.55;
    }

    .lal-flow-arrow {
        opacity: .35;
        margin-left: .2rem;
    }

    .lal-openbeta {
        border-left: 4px solid #5b8def;
        border-radius: 10px;
        padding: .9rem 1rem;
        background: rgba(91, 141, 239, .07);
        line-height: 1.65;
    }

    div[data-testid="stPageLink"] a {
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    '<div class="lal-badge">OPEN BETA</div>',
    unsafe_allow_html=True,
)

st.markdown(
    (
        '<div class="lal-hero-title">'
        + L(
            lang,
            "논문을 읽고,<br>Figure를 이해하고,<br>실험기법까지 연결하세요.",
            "Read the paper.<br>Understand the Figure.<br>Connect the experiment.",
        )
        + "</div>"
    ),
    unsafe_allow_html=True,
)

st.markdown(
    (
        '<div class="lal-hero-copy">'
        + L(
            lang,
            "LALSTUDY는 논문 요약에서 끝나지 않습니다. "
            "연구의 핵심 논리, Figure, 배경개념과 실제 실험기법을 하나의 학습 흐름으로 연결합니다.",
            "LALSTUDY goes beyond paper summarization. "
            "It connects a study's core logic, Figures, prerequisite concepts, and real experimental methods into one learning flow.",
        )
        + "</div>"
    ),
    unsafe_allow_html=True,
)


start1, start2, spacer = st.columns(
    [1.15, 1.15, 2.7]
)

with start1:
    st.page_link(
        "pages/1_Learn_a_Paper.py",
        label=L(
            lang,
            "📄 논문으로 시작하기",
            "📄 Start with a paper",
        ),
        use_container_width=True,
    )

with start2:
    st.page_link(
        "pages/2_Method_Wiki.py",
        label=L(
            lang,
            "🧬 실험기법 찾아보기",
            "🧬 Explore methods",
        ),
        use_container_width=True,
    )


st.write("")
st.write("")

st.markdown(
    (
        '<div class="lal-section-title">'
        + L(
            lang,
            "무엇을 할 수 있나요?",
            "What can you do?",
        )
        + "</div>"
    ),
    unsafe_allow_html=True,
)

st.markdown(
    (
        '<div class="lal-section-copy">'
        + L(
            lang,
            "논문을 읽는 흐름과 실험기법을 탐색하는 흐름이 서로 연결됩니다.",
            "The paper-learning workflow and the experimental-method workflow connect to each other.",
        )
        + "</div>"
    ),
    unsafe_allow_html=True,
)


features = [
    (
        "🎯",
        L(lang, "연구의 핵심 논리", "Core study logic"),
        L(
            lang,
            "무엇을 물었고, 왜 이 연구가 필요했으며, 어떤 결론까지 말할 수 있는지 구조화합니다.",
            "Structure the question, research gap, experimental logic, and the conclusions the evidence can support.",
        ),
    ),
    (
        "🖼️",
        L(lang, "Figure 중심 학습", "Figure-first learning"),
        L(
            lang,
            "원문 Figure와 legend를 함께 보고, 필요한 Figure만 개별적으로 AI 해석할 수 있습니다.",
            "Read the original Figure with its legend and analyze only the Figures you want to study more deeply.",
        ),
    ),
    (
        "🧬",
        L(lang, "Method Wiki", "Method Wiki"),
        L(
            lang,
            "실험기법을 목적·대상·원리·검출·표지·결과로 탐색하고 실제 논문과 panel 사용 사례까지 연결합니다.",
            "Browse methods by purpose, material, principle, detection, labeling, and output, then connect them to real papers and panels.",
        ),
    ),
    (
        "🧠",
        L(lang, "Knowledge Archive", "Knowledge Archive"),
        L(
            lang,
            "모르는 개념을 한 번 정리해 두고 이후 논문에서도 다시 사용할 수 있는 학습 자산으로 쌓습니다.",
            "Save unfamiliar concepts once and reuse them as persistent learning assets across future papers.",
        ),
    ),
]

cols = st.columns(4)

for col, (
    icon,
    title,
    copy,
) in zip(
    cols,
    features,
):
    with col:
        st.markdown(
            f"""
            <div class="lal-feature">
              <div class="lal-feature-icon">{icon}</div>
              <div class="lal-feature-title">{title}</div>
              <div class="lal-feature-copy">{copy}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


st.write("")
st.write("")

st.markdown(
    (
        '<div class="lal-section-title">'
        + L(
            lang,
            "두 가지 시작점",
            "Two ways to start",
        )
        + "</div>"
    ),
    unsafe_allow_html=True,
)

flow1, flow2 = st.columns(
    2,
    gap="large",
)

with flow1:
    st.markdown(
        f"""
        <div class="lal-flow">
          <div class="lal-flow-title">📄 {L(lang, "논문에서 시작", "Start from a paper")}</div>
          <div class="lal-flow-step">PDF upload</div>
          <div class="lal-flow-arrow">↓</div>
          <div class="lal-flow-step"><b>{L(lang, "Core Analysis", "Core Analysis")}</b></div>
          <div class="lal-flow-arrow">↓</div>
          <div class="lal-flow-step">{L(lang, "Figure + 원문 legend", "Figure + original legend")}</div>
          <div class="lal-flow-arrow">↓</div>
          <div class="lal-flow-step">{L(lang, "선수지식 · 실험전략 · 비판적 읽기", "Prerequisites · strategy · critical reading")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with flow2:
    st.markdown(
        f"""
        <div class="lal-flow">
          <div class="lal-flow-title">🧬 {L(lang, "실험기법에서 시작", "Start from a method")}</div>
          <div class="lal-flow-step">{L(lang, "실험명 검색 또는 category 탐색", "Search a method or browse categories")}</div>
          <div class="lal-flow-arrow">↓</div>
          <div class="lal-flow-step"><b>{L(lang, "Method Wiki", "Method Wiki")}</b></div>
          <div class="lal-flow-arrow">↓</div>
          <div class="lal-flow-step">{L(lang, "실제 논문 → Figure → Panel", "Real paper → Figure → Panel")}</div>
          <div class="lal-flow-arrow">↓</div>
          <div class="lal-flow-step">{L(lang, "어디서 어떻게 쓰였는지 확인", "See where and how the method was used")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.write("")
st.write("")

st.markdown(
    (
        '<div class="lal-openbeta">'
        + L(
            lang,
            "<b>Open Beta</b> · 현재 corpus 기반 탐색은 면역학 관련 키워드로 수집한 약 1,000편의 "
            "Nature Communications open-access 논문을 사용합니다. 자동 method/panel 연결은 일부 부정확할 수 있습니다.",
            "<b>Open Beta</b> · Corpus-based exploration currently uses approximately 1,000 "
            "Nature Communications open-access papers retrieved with immunology-related search terms. "
            "Automated method/panel links may occasionally be imperfect.",
        )
        + "</div>"
    ),
    unsafe_allow_html=True,
)

st.write("")

st.page_link(
    "pages/5_About.py",
    label=L(
        lang,
        "LALSTUDY에 대해 더 알아보기 →",
        "Learn more about LALSTUDY →",
    ),
    icon="ℹ️",
)
