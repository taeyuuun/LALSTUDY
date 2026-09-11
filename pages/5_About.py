import streamlit as st
from i18n import language_selector, L
from knowledge_widget import render_knowledge_archive_widget
from ai_provider import render_openai_usage_panel

APP_VERSION = "v0.4.0-beta"
st.set_page_config(page_title="LALSTUDY · About",page_icon="ℹ️",layout="wide")
lang=language_selector()

render_openai_usage_panel(lang=lang)

render_knowledge_archive_widget(lang=lang)

st.title(L(lang,"ℹ️ LALSTUDY 소개","ℹ️ About LALSTUDY"))
st.caption(L(lang,f"현재 버전: {APP_VERSION}",f"Current version: {APP_VERSION}"))

if lang=="ko":
    st.markdown("""
**LALSTUDY**는 논문을 읽는 과정에서 논리, 배경개념, 실험기법, Figure를 하나의 학습 맥락으로 연결하기 위한 실험적 플랫폼입니다.

현재 corpus 기반 기능은 면역학 관련 키워드 검색으로 수집한 약 1,000개의 **Nature Communications open-access 논문**을 사용합니다. 이는 전체 면역학 문헌이나 *Nature Immunology* corpus가 아닙니다.
    """)
else:
    st.markdown("""
**LALSTUDY** is an experimental platform designed to connect paper logic, background concepts, experimental methods, and figures within one learning context.

The current corpus-based features use approximately 1,000 **Nature Communications open-access papers retrieved with immunology-related search terms**. This is neither a complete immunology corpus nor a *Nature Immunology* corpus.
    """)

st.header(L(lang,"버전 기록","Version History"))
with st.container(border=True):
    st.subheader("v0.4.0-beta")
    st.markdown(L(lang,"""
- AI provider를 OpenAI 하나로 단일화
- Core / Plus / Figure / Knowledge Archive AI 호출을 OpenAI로 통합
- Figure별 독립 분석 및 cache 유지
- OpenAI 공식 Usage / Costs sync 유지
- Gemini runtime 및 provider 선택 UI 제거
""","""
- Unified all AI features under OpenAI only
- Core / Plus / Figure / Knowledge Archive calls use the same OpenAI engine
- Independent per-Figure analysis and caching retained
- Official OpenAI Usage / Costs sync retained
- Gemini runtime and provider-selection UI removed
"""))
with st.container(border=True):
    st.subheader("v0.1.1-beta")
    st.markdown(L(lang,"""
- 한국어 / English 전역 언어 선택
- 주요 UI 한영 전환
- Learn a Paper 배경지식 설명 한영 전환
- 실험기법 목적 설명 한영 전환
- 원 논문 텍스트는 원문 유지
""","""
- Global Korean / English language selector
- Bilingual primary UI
- Bilingual prerequisite explanations in Learn a Paper
- Bilingual experimental-method purpose explanations
- Original paper text remains unchanged
"""))
with st.container(border=True):
    st.subheader("v0.1.0-beta")
    st.markdown("""
- Initial integrated beta
- Learn a Paper
- Method Explorer
- Figure Gallery / panel-aware interpretation
- Panel crop beta
- License-aware Figure display
    """)

st.header(L(lang,"로드맵","Roadmap"))
st.markdown(L(lang,"""
### 현재 개발 방향
- OpenAI 기반 AI 설명 레이어 고도화
- Question → Gap → Hypothesis → Experiment → Result → Conclusion 구조화
- Concept dependency graph
- Learn a Paper ↔ Method/Figure Explorer 직접 연결
- 복합 과학 검색

### 이후
- 개인 지식 프로필
- 학습 기록
- 사용자 correction / QA
- 여러 논문 비교
""","""
### Current development direction
- Improve the OpenAI-powered explanation layer
- Question → Gap → Hypothesis → Experiment → Result → Conclusion reconstruction
- Concept dependency graph
- Direct Learn a Paper ↔ Method/Figure Explorer linking
- Compound scientific search

### Later
- Personal knowledge profile
- Learning history
- User correction / QA
- Multi-paper comparison
"""))

st.header(L(lang,"베타 한계","Beta limitations"))
st.markdown(L(lang,"""
- 자동 method detection에는 false positive가 있을 수 있습니다.
- Figure ↔ Method 연결은 Paper ↔ Method보다 덜 완전합니다.
- Panel parsing/cropping은 heuristic입니다.
- Learn a Paper는 아직 extractive / rule-based 중심입니다.
- PDF text layer가 필요합니다.
- 권리 분류는 보수적 자동 보조 도구이며 법률 자문이 아닙니다.
""","""
- Automated method detection can produce false positives.
- Figure ↔ Method coverage is less complete than Paper ↔ Method coverage.
- Panel parsing and cropping are heuristic.
- Learn a Paper is still primarily extractive / rule-based.
- PDF parsing requires an accessible text layer.
- Rights classification is a conservative automated aid, not legal advice.
"""))

st.divider()
st.page_link("app.py",label=L(lang,"← 홈","← Home"),icon="🏠")
