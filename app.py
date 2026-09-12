import streamlit as st
from i18n import language_selector, L
from knowledge_widget import render_knowledge_archive_widget
from openai_sidebar import render_openai_usage_panel

APP_VERSION = "v0.5.2.1-beta"

st.set_page_config(page_title="LALSTUDY", page_icon="🧬", layout="wide")
lang = language_selector()

render_openai_usage_panel(lang=lang)

render_knowledge_archive_widget(lang=lang)

st.title("🧬 LALSTUDY")
st.caption(f"Scientific paper learning & experimental method explorer · {APP_VERSION}")

if lang == "ko":
    st.markdown("""
### 논문을 '요약'에서 끝내지 않고, **이해하고 더 공부할 수 있게 연결**합니다.

LALSTUDY는 두 가지 학습 흐름을 연결합니다.

#### 📄 Learn a Paper
논문 PDF → **Core Analysis + Figures/legends → 필요할 때 Plus Analysis**

#### 🔬 Explore Experiments
실험기법 → **Method → Paper → Figure → Panel**
    """)
else:
    st.markdown("""
### Go beyond summarization: **understand a paper and keep learning without losing context.**

LALSTUDY connects two learning workflows.

#### 📄 Learn a Paper
Paper PDF → **Core Analysis + Figures/legends → optional Plus Analysis when needed**

#### 🔬 Explore Experiments
Experimental method → **Method → Paper → Figure → Panel**
    """)

st.divider()
c1,c2=st.columns(2)
with c1:
    with st.container(border=True):
        st.subheader("📄 Learn a Paper")
        st.write(L(lang,
            "PDF에서 핵심 문장, 연구 gap, 배경지식, 실험기법, Figure 흐름과 추가 학습 경로를 구조화합니다.",
            "Turn a PDF into a structured map of its core logic, research gap, prerequisite knowledge, experimental methods, figures, and next learning steps."))
        st.page_link("pages/1_Learn_a_Paper.py", label=L(lang,"Learn a Paper 열기 →","Open Learn a Paper →"), icon="📄")
with c2:
    with st.container(border=True):
        st.subheader("🧬 Method Explorer")
        st.write(L(lang,
            "LALSTUDY corpus에서 특정 실험기법이 어떤 논문과 Figure에서 사용되었는지 탐색합니다.",
            "Explore which papers and figures in the LALSTUDY corpus use a selected experimental method."))
        st.page_link("pages/2_Method_Explorer.py", label=L(lang,"Method Explorer 열기 →","Open Method Explorer →"), icon="🧬")

c3,c4=st.columns(2)
with c3:
    with st.container(border=True):
        st.subheader("🖼 Figure Explorer")
        st.write(L(lang,
            "실험기법과 연관된 실제 Figure를 보고 caption을 panel 단위로 나누어 학습합니다.",
            "Study real figures linked to experimental methods and inspect captions at the panel level."))
        st.page_link("pages/3_Figure_Explorer.py", label=L(lang,"Figure Explorer 열기 →","Open Figure Explorer →"), icon="🖼️")
with c4:
    with st.container(border=True):
        st.subheader("✂️ Panel Crop Beta")
        st.write(L(lang,
            "복합 Figure를 A/B/C/D panel 후보 영역으로 자동 분할하는 실험적 기능입니다.",
            "Experimental automatic segmentation of composite figures into candidate A/B/C/D panel regions."))
        st.page_link("pages/4_Panel_Crop_Beta.py", label=L(lang,"Panel Crop Beta 열기 →","Open Panel Crop Beta →"), icon="✂️")

st.divider()
st.subheader(L(lang,"현재 파이프라인","Current pipeline"))
st.code("""PDF / OA literature
        ↓
Scientific text extraction
        ↓
Method ontology + prerequisite concepts
        ↓
Paper ↔ Method ↔ Figure
        ↓
Figure / Panel interpretation
        ↓
Additional learning""", language=None)

st.info(L(lang,
    "v0.4.0-beta는 OpenAI-only AI 분석, Figure별 독립 분석, Knowledge Archive, 공식 OpenAI usage sync를 지원합니다.",
    "v0.4.0-beta uses an OpenAI-only AI engine with per-Figure analysis, Knowledge Archive, and official OpenAI usage sync."))

st.page_link("pages/5_About.py", label=L(lang,"About / 버전 기록","About / Version History"), icon="ℹ️")
