import streamlit as st

APP_VERSION = "v0.1.0-beta"

st.set_page_config(
    page_title="LALSTUDY",
    page_icon="🧬",
    layout="wide",
)

st.title("🧬 LALSTUDY")
st.caption(f"Scientific paper learning & experimental method explorer · {APP_VERSION}")

st.markdown("""
### 논문을 '요약'에서 끝내지 않고, **이해하고 더 공부할 수 있게 연결**합니다.

LALSTUDY의 현재 베타는 두 축으로 구성됩니다.

#### 📄 Learn a Paper
논문 PDF를 업로드하면 다음 순서로 학습 구조를 만듭니다.

**핵심 논리 → 연구 필요성 → 선수지식 → 실험 전략 → Figure → 다음 학습**

#### 🔬 Explore Experiments
실험기법을 선택하면 실제 논문과 Figure 사례를 탐색할 수 있습니다.

**Method → Paper → Figure → Panel**
""")

st.divider()

c1, c2 = st.columns(2)

with c1:
    with st.container(border=True):
        st.subheader("📄 Learn a Paper")
        st.write(
            "PDF에서 핵심 문장, 연구 gap, 배경지식, 실험기법, "
            "Figure 흐름과 추가 학습 경로를 구조화합니다."
        )
        st.page_link(
            "pages/1_Learn_a_Paper.py",
            label="Learn a Paper 열기 →",
            icon="📄",
        )

with c2:
    with st.container(border=True):
        st.subheader("🧬 Method Explorer")
        st.write(
            "LALSTUDY의 논문 corpus에서 특정 experimental method가 "
            "어떤 논문과 Figure에서 사용되었는지 탐색합니다."
        )
        st.page_link(
            "pages/2_Method_Explorer.py",
            label="Method Explorer 열기 →",
            icon="🧬",
        )

c3, c4 = st.columns(2)

with c3:
    with st.container(border=True):
        st.subheader("🖼 Figure Explorer")
        st.write(
            "실험기법과 연관된 실제 Figure를 보고 caption을 panel 단위로 "
            "분리해 학습할 수 있습니다."
        )
        st.page_link(
            "pages/3_Figure_Explorer.py",
            label="Figure Explorer 열기 →",
            icon="🖼️",
        )

with c4:
    with st.container(border=True):
        st.subheader("✂️ Panel Crop Beta")
        st.write(
            "복합 Figure를 A/B/C/D panel 후보 영역으로 자동 분할하는 "
            "실험적 기능입니다."
        )
        st.page_link(
            "pages/4_Panel_Crop_Beta.py",
            label="Panel Crop Beta 열기 →",
            icon="✂️",
        )

st.divider()

st.subheader("Current pipeline")

st.code(
"""PDF / OA literature
        ↓
Scientific text extraction
        ↓
Method ontology + prerequisite concepts
        ↓
Paper ↔ Method ↔ Figure
        ↓
Figure / Panel interpretation
        ↓
Additional learning""",
    language=None,
)

st.info(
    "v0.1.0-beta는 자동 추출과 규칙 기반 분석을 중심으로 한 MVP입니다. "
    "향후 생성형 AI 설명, concept dependency graph, 개인별 학습 기록을 추가할 예정입니다."
)

st.page_link(
    "pages/5_About.py",
    label="About / Version History",
    icon="ℹ️",
)
