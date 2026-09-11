import streamlit as st
from i18n import language_selector, L
from knowledge_widget import render_knowledge_archive_widget
from openai_sidebar import render_openai_usage_panel

APP_VERSION = "v0.5.1-beta"
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

st.header(L(lang,"주요 패치노트","Major Patch Notes"))
st.caption(L(lang,
    "세부 hotfix를 모두 나열하기보다 사용자 경험이 크게 바뀐 milestone만 정리합니다.",
    "This timeline highlights major user-facing milestones rather than every hotfix."
))

with st.container(border=True):
    st.subheader("v0.4.1.2-beta · Official-only Usage UI")
    st.markdown(L(lang,"""
- 무료 token **추정 잔량 표시를 제거**하고 공식값만 표시
- official incentive service tier가 확인될 때만 무료 사용량/잔량 표시
- sidebar 숫자를 단일-column 작은 글씨로 고정해 ellipsis 문제 제거
- stale UI 확인을 위한 `usage UI · v0.4.1.2` 표시 추가
""","""
- Removed estimated complimentary-token balances; the UI now shows official values only
- Complimentary usage/remaining appears only when the official incentive service tier is confirmed
- Forced the sidebar into a compact single-column text layout to eliminate ellipsis
- Added a `usage UI · v0.4.1.2` deployment marker
"""))

with st.container(border=True):
    st.subheader("v0.4.1.1-beta · Compact Usage UI")
    st.markdown(L(lang,"""
- sidebar의 3열 metric / 큰 숫자 UI를 완전히 제거
- 무료 잔량, 오늘 사용량, 요청 수, 비용을 세로형 compact layout으로 정리
- 긴 service-tier 안내문을 한 줄 상태 메시지로 축약
""","""
- Removed narrow 3-column metrics and oversized number rendering
- Reworked usage / remaining / requests / cost into a compact vertical layout
- Shortened the service-tier explanation into a one-line status note
"""))

with st.container(border=True):
    st.subheader("v0.4.1-beta · Usage UI")
    st.markdown(L(lang,"""
- OpenAI Usage 숫자가 sidebar에서 잘리지 않도록 UI 재설계
- 공식 usage와 무료 잔량 **추정치**를 명확히 구분
- 사용량 / 일일 한도 / 요청 수 / 실제 과금액을 한눈에 표시
""","""
- Redesigned the OpenAI Usage sidebar so large numbers are never truncated
- Clearly distinguishes official usage from an **estimated** complimentary balance
- Shows usage / daily allowance / request count / billed cost at a glance
"""))

with st.container(border=True):
    st.subheader("v0.4.0-beta · OpenAI Only")
    st.markdown(L(lang,"""
- Gemini runtime 제거, 모든 AI 기능을 OpenAI로 단일화
- Core / Plus / Figure / Knowledge Archive AI를 하나의 engine으로 통합
- OpenAI Organization Usage / Costs 공식 sync 추가
""","""
- Removed the Gemini runtime and unified all AI features under OpenAI
- Core / Plus / Figure / Knowledge Archive now share one AI engine
- Added official OpenAI Organization Usage / Costs sync
"""))

with st.container(border=True):
    st.subheader("v0.3.x · Knowledge Archive & Learn UX")
    st.markdown(L(lang,"""
- Supabase 기반 재사용형 Knowledge Archive 구축
- Archive를 전역 sidebar로 이동하고 용어를 하나씩 queue에 추가하도록 개선
- Learn a Paper를 **Main(Core + Figures) / Plus** 계층으로 단순화
- Figure별 독립 AI 분석 구조 도입
""","""
- Added a reusable Supabase-backed Knowledge Archive
- Moved Archive to a global sidebar with one-concept-at-a-time queueing
- Simplified Learn a Paper into **Main (Core + Figures) / Plus** layers
- Introduced independent per-Figure AI analysis
"""))

with st.container(border=True):
    st.subheader("v0.2.x · AI Deep Study & Figure Extraction")
    st.markdown(L(lang,"""
- Core / 선수지식 / 실험전략 / Figure / 비판적 읽기 AI 모듈 구축
- AI 호출을 stage별로 분리해 실패 격리 및 cache 적용
- 원본 PDF caption-anchor 기반 Figure crop engine 정착
- Figure 이미지 + 원문 legend를 함께 학습하는 흐름 구축
""","""
- Added Core / prerequisites / experimental strategy / Figure / critical-reading AI modules
- Split AI calls into stages for failure isolation and caching
- Stabilized source-PDF caption-anchor Figure extraction
- Paired Figure images with their original source legends
"""))

with st.container(border=True):
    st.subheader("v0.1.x · Integrated Beta")
    st.markdown(L(lang,"""
- Learn a Paper / Method Explorer / Figure Explorer / Panel Crop 통합
- 한국어 / English 전역 UI 지원
- 약 1,000편 OA 논문 기반 Method ↔ Paper ↔ Figure 탐색
""","""
- Integrated Learn a Paper / Method Explorer / Figure Explorer / Panel Crop
- Added global Korean / English UI
- Enabled Method ↔ Paper ↔ Figure exploration over ~1,000 OA papers
"""))

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
