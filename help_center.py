"""Product-facing contextual help for LALSTUDY.

One source of truth is used by:
- Knowledge Archive contextual help
- Learn a Paper contextual help
- Method Wiki contextual help
- the full Help page

Keep this file user-facing. Avoid developer/debug language here.
"""

from __future__ import annotations

import streamlit as st


def _L(lang: str, ko: str, en: str) -> str:
    return ko if lang == "ko" else en


HELP_TOPICS = {
    "learn": {
        "icon": "📄",
        "title_ko": "Learn a Paper",
        "title_en": "Learn a Paper",
        "one_ko": "논문 한 편을 핵심 논리 → Figure → 실험전략까지 단계적으로 읽는 공간입니다.",
        "one_en": "Read one paper step by step from its core logic to Figures and experimental strategy.",
    },
    "archive": {
        "icon": "🧠",
        "title_ko": "Knowledge Archive",
        "title_en": "Knowledge Archive",
        "one_ko": "논문을 읽다가 막힌 개념을 바로 찾아보고, 다음 논문에서도 다시 쓰는 개인 지식창고입니다.",
        "one_en": "Look up unfamiliar concepts while reading and reuse them across future papers.",
    },
    "method": {
        "icon": "🧬",
        "title_ko": "Method Wiki",
        "title_en": "Method Wiki",
        "one_ko": "실험기법의 원리와 해석법을 배우고, 실제 논문의 Figure·panel에서 어떻게 쓰였는지 연결해서 봅니다.",
        "one_en": "Learn how a method works and see how it is actually used in paper Figures and panels.",
    },
}


def _step(number: int, title: str, body: str):
    st.markdown(
        f"""
<div style="
    display:flex;
    gap:0.8rem;
    align-items:flex-start;
    margin:0.55rem 0;
">
  <div style="
      min-width:1.75rem;
      height:1.75rem;
      border-radius:999px;
      background:rgba(90,120,255,0.10);
      display:flex;
      align-items:center;
      justify-content:center;
      font-weight:700;
      font-size:0.85rem;
  ">{number}</div>
  <div>
    <div style="font-weight:700; margin-bottom:0.12rem;">{title}</div>
    <div style="opacity:0.78; line-height:1.55;">{body}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _small_note(text: str):
    st.markdown(
        f"""
<div style="
    margin-top:0.8rem;
    padding:0.75rem 0.85rem;
    border-radius:0.75rem;
    background:rgba(127,127,127,0.07);
    line-height:1.55;
    font-size:0.92rem;
">{text}</div>
""",
        unsafe_allow_html=True,
    )


def render_help_topic(topic: str, lang: str = "ko", compact: bool = False):
    info = HELP_TOPICS[topic]

    title = (
        info["title_ko"]
        if lang == "ko"
        else info["title_en"]
    )
    one = (
        info["one_ko"]
        if lang == "ko"
        else info["one_en"]
    )

    st.markdown(
        f"### {info['icon']} {title}"
    )
    st.write(one)

    if topic == "learn":
        st.markdown(
            "#### "
            + _L(
                lang,
                "어디서 사용하나요?",
                "Where do I use it?",
            )
        )
        st.write(
            _L(
                lang,
                "왼쪽 메뉴에서 **Learn a Paper**를 선택한 뒤, 읽고 싶은 논문 PDF를 업로드합니다.",
                "Open **Learn a Paper** from the left menu and upload the paper PDF you want to study.",
            )
        )

        st.markdown(
            "#### "
            + _L(
                lang,
                "처음부터 끝까지",
                "Start to finish",
            )
        )

        _step(
            1,
            _L(lang, "PDF 업로드", "Upload the PDF"),
            _L(
                lang,
                "논문 PDF를 올리고 분석을 시작합니다.",
                "Upload the paper PDF and start the analysis.",
            ),
        )
        _step(
            2,
            _L(lang, "핵심 내용 먼저", "Read the core story first"),
            _L(
                lang,
                "연구 질문, 왜 필요한 연구인지, 핵심 결과와 결론을 먼저 잡습니다.",
                "Start with the question, motivation, key results, and conclusion.",
            ),
        )
        _step(
            3,
            _L(lang, "Figure를 원문과 함께", "Read Figures with the source"),
            _L(
                lang,
                "Figure crop과 원문 legend를 함께 보고, 이해가 필요한 Figure만 개별 분석합니다.",
                "Read each Figure with its original legend and analyze only the Figures you need.",
            ),
        )
        _step(
            4,
            _L(lang, "모르는 개념은 Archive로", "Send unfamiliar concepts to the Archive"),
            _L(
                lang,
                "읽다가 막힌 용어는 Knowledge Archive에서 바로 찾아볼 수 있습니다.",
                "Look up unfamiliar terms in Knowledge Archive without leaving your reading flow.",
            ),
        )
        _step(
            5,
            _L(lang, "실험기법은 Method Wiki로", "Open methods in Method Wiki"),
            _L(
                lang,
                "논문에 등장한 실험기법을 눌러 원리, 해석 포인트, 실제 사용 Figure와 panel까지 이어서 봅니다.",
                "Open experimental methods to learn the principle, interpretation points, and real Figure/panel examples.",
            ),
        )
        _step(
            6,
            _L(lang, "필요할 때 Plus", "Use Plus when needed"),
            _L(
                lang,
                "선수지식, 실험전략, 비판적 읽기는 필요한 부분만 추가로 확인합니다.",
                "Open prerequisites, experimental strategy, and critical reading only when you need them.",
            ),
        )

        _small_note(
            _L(
                lang,
                "추천 순서: **핵심 내용 → Figure → 막히는 개념/실험기법 → Plus**. 처음부터 모든 분석을 볼 필요는 없습니다.",
                "Recommended order: **Core → Figures → unfamiliar concepts/methods → Plus**. You do not need every analysis at once.",
            )
        )

    elif topic == "archive":
        st.markdown(
            "#### "
            + _L(
                lang,
                "어디서 사용하나요?",
                "Where do I use it?",
            )
        )
        st.write(
            _L(
                lang,
                "주요 페이지의 왼쪽 사이드바에 있는 **🧠 Knowledge Archive**에서 사용합니다.",
                "Use **🧠 Knowledge Archive** in the left sidebar of the main pages.",
            )
        )

        st.markdown(
            "#### "
            + _L(
                lang,
                "사용 순서",
                "How it works",
            )
        )

        _step(
            1,
            _L(lang, "이해가 필요한 용어 입력", "Enter a term you want to understand"),
            _L(
                lang,
                "예: `apoptotic stress`. 여러 단어로 된 표현도 그대로 하나의 개념으로 입력하면 됩니다.",
                "Example: `apoptotic stress`. Multi-word phrases can be entered as one concept.",
            ),
        )
        _step(
            2,
            _L(lang, "용어 추가", "Add the term"),
            _L(
                lang,
                "여러 개를 보고 싶다면 하나씩 queue에 추가합니다.",
                "Add terms to the queue one at a time if you want to look up several.",
            ),
        )
        _step(
            3,
            _L(lang, "Archive 검색", "Search the Archive"),
            _L(
                lang,
                "이미 저장된 개념이면 바로 설명을 불러옵니다.",
                "If the concept is already stored, its explanation appears immediately.",
            ),
        )
        _step(
            4,
            _L(lang, "없으면 AI 생성", "Generate only when missing"),
            _L(
                lang,
                "Archive에 없는 용어만 원할 때 AI로 설명을 생성하고 저장할 수 있습니다.",
                "For a missing concept, generate an explanation with AI only when you want to, then save it.",
            ),
        )
        _step(
            5,
            _L(lang, "다음 논문에서도 재사용", "Reuse it later"),
            _L(
                lang,
                "한 번 저장된 개념은 다른 논문을 읽을 때 다시 검색해 사용할 수 있습니다.",
                "Saved concepts can be searched again while reading future papers.",
            ),
        )

        _small_note(
            _L(
                lang,
                "**팁:** 너무 넓은 주제보다 지금 논문에서 막힌 정확한 용어·구절을 넣는 것이 가장 유용합니다.",
                "**Tip:** Search the exact term or phrase blocking your reading rather than a very broad topic.",
            )
        )

    elif topic == "method":
        st.markdown(
            "#### "
            + _L(
                lang,
                "어디서 사용하나요?",
                "Where do I use it?",
            )
        )
        st.write(
            _L(
                lang,
                "왼쪽 메뉴의 **Method Wiki**에서 직접 검색하거나, Learn a Paper의 실험기법 버튼을 통해 바로 이동할 수 있습니다.",
                "Open **Method Wiki** from the left menu, or jump there directly from a method inside Learn a Paper.",
            )
        )

        st.markdown(
            "#### "
            + _L(
                lang,
                "사용 순서",
                "How it works",
            )
        )

        _step(
            1,
            _L(lang, "방법 이름 검색 또는 category 탐색", "Search or browse"),
            _L(
                lang,
                "실험기법 이름을 검색하거나 목적·대상·핵심 원리·검출·표지·결과 기준으로 탐색합니다.",
                "Search by method name or browse by purpose, material, core principle, detection, labeling, and output.",
            ),
        )
        _step(
            2,
            _L(lang, "한눈에 보기", "Get the quick view"),
            _L(
                lang,
                "이 실험이 무엇을 묻는 방법인지와 핵심 원리를 먼저 파악합니다.",
                "First understand what the method asks and its core principle.",
            ),
        )
        _step(
            3,
            _L(lang, "언제 쓰고 어떻게 해석하는지", "Learn when to use and how to interpret it"),
            _L(
                lang,
                "적합한 상황, 핵심 단계, 결과를 읽을 때 주의할 점을 확인합니다.",
                "Review use cases, key steps, and the main interpretation caveats.",
            ),
        )
        _step(
            4,
            _L(lang, "실제 논문 연결", "Connect to real papers"),
            _L(
                lang,
                "이 method가 사용된 corpus 논문을 찾아 실제 연구 맥락에서 봅니다.",
                "Find corpus papers using the method and see it in a real research context.",
            ),
        )
        _step(
            5,
            _L(lang, "Figure → panel까지 확인", "Trace Figure → panel"),
            _L(
                lang,
                "가능한 경우 어떤 Figure의 A–F 중 어느 panel에서 어떻게 사용됐는지 legend 근거와 함께 확인합니다.",
                "When supported by the legend, see which Figure panel (A–F) uses the method and how.",
            ),
        )

        _small_note(
            _L(
                lang,
                "Method Wiki의 논문·사용 빈도는 현재 LALSTUDY corpus 안의 결과입니다. 전체 생명과학 문헌의 빈도를 뜻하지는 않습니다.",
                "Paper examples and usage counts describe the current LALSTUDY corpus, not the full life-science literature.",
            )
        )

    if not compact:
        st.divider()


@st.dialog("LALSTUDY Help")
def _help_dialog(topic: str, lang: str):
    render_help_topic(
        topic,
        lang=lang,
        compact=True,
    )


def help_button(
    topic: str,
    *,
    lang: str = "ko",
    key: str | None = None,
    use_container_width: bool = False,
):
    label = _L(
        lang,
        "❓ 사용법",
        "❓ Help",
    )

    if st.button(
        label,
        key=key or f"lal_help_{topic}",
        use_container_width=use_container_width,
    ):
        _help_dialog(
            topic,
            lang,
        )
