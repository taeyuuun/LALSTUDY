import streamlit as st

from help_center import (
    HELP_TOPICS,
    render_help_topic,
)
from i18n import language_selector, L
from sidebar_ui import render_public_sidebar


APP_VERSION = "v0.6.4-open-beta"


st.set_page_config(
    page_title="LALSTUDY Help",
    page_icon="❓",
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
    max-width: 1020px;
    padding-top: 2.2rem;
    padding-bottom: 4rem;
}

.help-hero {
    padding: 1.25rem 1.35rem;
    border: 1px solid rgba(49,51,63,.10);
    border-radius: 18px;
    background: rgba(127,127,127,.04);
    margin-bottom: 1.4rem;
}

.help-path {
    padding: 1rem 1.05rem;
    border-radius: 14px;
    border: 1px solid rgba(49,51,63,.10);
    line-height: 1.65;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title(
    L(
        lang,
        "❓ LALSTUDY 사용법",
        "❓ LALSTUDY Help",
    )
)

st.markdown(
    (
        '<div class="help-hero">'
        + L(
            lang,
            "<b>처음이라면 이것만 기억하세요.</b><br>"
            "논문은 <b>Learn a Paper</b>에서 읽고, "
            "막힌 개념은 <b>Knowledge Archive</b>에서 찾고, "
            "실험기법은 <b>Method Wiki</b>에서 깊게 봅니다.",
            "<b>If you are new, remember this.</b><br>"
            "Read papers in <b>Learn a Paper</b>, "
            "look up unfamiliar concepts in <b>Knowledge Archive</b>, "
            "and explore experimental methods in <b>Method Wiki</b>.",
        )
        + "</div>"
    ),
    unsafe_allow_html=True,
)

st.subheader(
    L(
        lang,
        "가장 자연스러운 사용 흐름",
        "Recommended workflow",
    )
)

st.markdown(
    (
        '<div class="help-path">'
        + L(
            lang,
            "📄 <b>PDF 업로드</b>"
            " &nbsp;→&nbsp; 🎯 <b>핵심 내용</b>"
            " &nbsp;→&nbsp; 🖼️ <b>Figure</b>"
            " &nbsp;→&nbsp; 🧠 <b>모르는 개념</b>"
            " &nbsp;→&nbsp; 🧬 <b>실험기법</b>"
            " &nbsp;→&nbsp; 🧐 <b>필요할 때 더 깊게</b>",
            "📄 <b>Upload PDF</b>"
            " &nbsp;→&nbsp; 🎯 <b>Core story</b>"
            " &nbsp;→&nbsp; 🖼️ <b>Figures</b>"
            " &nbsp;→&nbsp; 🧠 <b>Unknown concepts</b>"
            " &nbsp;→&nbsp; 🧬 <b>Methods</b>"
            " &nbsp;→&nbsp; 🧐 <b>Go deeper when needed</b>",
        )
        + "</div>"
    ),
    unsafe_allow_html=True,
)

st.write("")

tabs = st.tabs(
    [
        L(lang, "📄 Learn a Paper", "📄 Learn a Paper"),
        L(lang, "🧠 Knowledge Archive", "🧠 Knowledge Archive"),
        L(lang, "🧬 Method Wiki", "🧬 Method Wiki"),
    ]
)

with tabs[0]:
    render_help_topic(
        "learn",
        lang=lang,
    )

with tabs[1]:
    render_help_topic(
        "archive",
        lang=lang,
    )

with tabs[2]:
    render_help_topic(
        "method",
        lang=lang,
    )

st.subheader(
    L(
        lang,
        "어디서 찾을 수 있나요?",
        "Where can I find each feature?",
    )
)

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(
        L(
            lang,
            "**📄 Learn a Paper**  \n왼쪽 메뉴에서 바로 선택",
            "**📄 Learn a Paper**  \nOpen it from the left menu",
        )
    )

with c2:
    st.markdown(
        L(
            lang,
            "**🧠 Knowledge Archive**  \n주요 페이지의 왼쪽 사이드바",
            "**🧠 Knowledge Archive**  \nIn the left sidebar of the main pages",
        )
    )

with c3:
    st.markdown(
        L(
            lang,
            "**🧬 Method Wiki**  \n왼쪽 메뉴 또는 논문 안의 method 버튼",
            "**🧬 Method Wiki**  \nFrom the left menu or a method button inside a paper",
        )
    )

st.info(
    L(
        lang,
        "각 기능 화면의 **❓ 사용법** 버튼을 누르면 이 페이지를 떠나지 않고 필요한 도움말만 바로 볼 수 있습니다.",
        "Use the **❓ Help** button inside each feature to open contextual help without leaving your current page.",
    )
)
