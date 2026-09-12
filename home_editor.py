"""Private, browser-based Home Studio.

Open with:
    ?home_editor=1

Authentication:
    HOME_ADMIN_PASSWORD in Streamlit Secrets

Publishing:
    Supabase `home_page_config` table
"""

from __future__ import annotations

import copy
import hmac

import streamlit as st

from home_config_store import (
    HomeConfigStore,
    load_default_home_config,
    load_published_home_config,
)
from home_page import render_home


AUTH_KEY = "lal_home_admin_authenticated"
DRAFT_KEY = "lal_home_editor_draft"
WIDGET_PREFIX = "home_edit_"


def _admin_password() -> str:
    try:
        value = st.secrets.get(
            "HOME_ADMIN_PASSWORD",
            "",
        )
    except Exception:
        value = ""

    return str(
        value
        or ""
    )


def _clear_widget_state():
    for key in list(
        st.session_state.keys()
    ):
        if str(key).startswith(
            WIDGET_PREFIX
        ):
            del st.session_state[key]


def _reset_draft(config):
    st.session_state[
        DRAFT_KEY
    ] = copy.deepcopy(
        config
    )
    _clear_widget_state()


def _authenticate():
    expected = _admin_password()

    if not expected:
        st.error(
            "`HOME_ADMIN_PASSWORD`가 설정되어 있지 않아 Home Studio를 열 수 없습니다."
        )
        st.code(
            'HOME_ADMIN_PASSWORD = "원하는-강한-비밀번호"',
            language="toml",
        )
        return False

    if st.session_state.get(
        AUTH_KEY
    ):
        return True

    st.title(
        "🔐 LALSTUDY Home Studio"
    )
    st.caption(
        "관리자 전용 · 비밀번호는 브라우저 세션에만 유지됩니다."
    )

    entered = st.text_input(
        "Admin password",
        type="password",
        key="home_admin_password_input",
    )

    if st.button(
        "Home Studio 열기",
        type="primary",
    ):
        if hmac.compare_digest(
            str(entered),
            expected,
        ):
            st.session_state[
                AUTH_KEY
            ] = True
            st.rerun()
        else:
            st.error(
                "비밀번호가 맞지 않습니다."
            )

    return False


def _text_input(
    label,
    value,
    key,
):
    return st.text_input(
        label,
        value=str(value or ""),
        key=WIDGET_PREFIX + key,
    )


def _text_area(
    label,
    value,
    key,
    height=90,
):
    return st.text_area(
        label,
        value=str(value or ""),
        height=height,
        key=WIDGET_PREFIX + key,
    )


def _edit_language(
    draft,
    lang_key,
    label,
):
    content = copy.deepcopy(
        draft.get(
            lang_key,
            {},
        )
    )

    st.markdown(
        f"#### {label}"
    )

    with st.expander(
        "① Hero",
        expanded=True,
    ):
        content[
            "hero_title"
        ] = _text_area(
            "메인 제목",
            content.get(
                "hero_title",
                "",
            ),
            f"{lang_key}_hero_title",
            height=120,
        )

        content[
            "hero_subtitle"
        ] = _text_area(
            "설명",
            content.get(
                "hero_subtitle",
                "",
            ),
            f"{lang_key}_hero_subtitle",
            height=110,
        )

        c1, c2 = st.columns(2)

        with c1:
            content[
                "paper_button"
            ] = _text_input(
                "논문 버튼",
                content.get(
                    "paper_button",
                    "",
                ),
                f"{lang_key}_paper_button",
            )

        with c2:
            content[
                "method_button"
            ] = _text_input(
                "Method 버튼",
                content.get(
                    "method_button",
                    "",
                ),
                f"{lang_key}_method_button",
            )

    with st.expander(
        "② Feature cards",
    ):
        content[
            "feature_section_title"
        ] = _text_input(
            "섹션 제목",
            content.get(
                "feature_section_title",
                "",
            ),
            f"{lang_key}_feature_section_title",
        )

        content[
            "feature_section_subtitle"
        ] = _text_area(
            "섹션 설명",
            content.get(
                "feature_section_subtitle",
                "",
            ),
            f"{lang_key}_feature_section_subtitle",
            height=75,
        )

        for index in range(
            1,
            5,
        ):
            st.markdown(
                f"**Card {index}**"
            )

            a, b = st.columns(
                [0.25, 0.75]
            )

            with a:
                content[
                    f"feature_{index}_icon"
                ] = _text_input(
                    "Icon",
                    content.get(
                        f"feature_{index}_icon",
                        "",
                    ),
                    f"{lang_key}_feature_{index}_icon",
                )

            with b:
                content[
                    f"feature_{index}_title"
                ] = _text_input(
                    "제목",
                    content.get(
                        f"feature_{index}_title",
                        "",
                    ),
                    f"{lang_key}_feature_{index}_title",
                )

            content[
                f"feature_{index}_text"
            ] = _text_area(
                "설명",
                content.get(
                    f"feature_{index}_text",
                    "",
                ),
                f"{lang_key}_feature_{index}_text",
                height=78,
            )

    with st.expander(
        "③ Start flows",
    ):
        content[
            "flow_section_title"
        ] = _text_input(
            "섹션 제목",
            content.get(
                "flow_section_title",
                "",
            ),
            f"{lang_key}_flow_section_title",
        )

        left, right = st.columns(
            2
        )

        with left:
            content[
                "paper_flow_title"
            ] = _text_input(
                "논문 flow 제목",
                content.get(
                    "paper_flow_title",
                    "",
                ),
                f"{lang_key}_paper_flow_title",
            )

            for index in range(
                1,
                5,
            ):
                content[
                    f"paper_flow_{index}"
                ] = _text_input(
                    f"Step {index}",
                    content.get(
                        f"paper_flow_{index}",
                        "",
                    ),
                    f"{lang_key}_paper_flow_{index}",
                )

        with right:
            content[
                "method_flow_title"
            ] = _text_input(
                "Method flow 제목",
                content.get(
                    "method_flow_title",
                    "",
                ),
                f"{lang_key}_method_flow_title",
            )

            for index in range(
                1,
                5,
            ):
                content[
                    f"method_flow_{index}"
                ] = _text_input(
                    f"Step {index}",
                    content.get(
                        f"method_flow_{index}",
                        "",
                    ),
                    f"{lang_key}_method_flow_{index}",
                )

    with st.expander(
        "④ Open Beta note / About",
    ):
        content[
            "open_beta_note"
        ] = _text_area(
            "Open Beta 안내",
            content.get(
                "open_beta_note",
                "",
            ),
            f"{lang_key}_open_beta_note",
            height=100,
        )

        content[
            "about_link"
        ] = _text_input(
            "About 링크 문구",
            content.get(
                "about_link",
                "",
            ),
            f"{lang_key}_about_link",
        )

    return content


def _edit_design(
    draft,
):
    design = copy.deepcopy(
        draft.get(
            "design",
            {},
        )
    )

    with st.expander(
        "🎨 디자인",
        expanded=True,
    ):
        design[
            "badge"
        ] = _text_input(
            "상단 badge",
            design.get(
                "badge",
                "OPEN BETA",
            ),
            "design_badge",
        )

        st.markdown(
            "**표시할 블록**"
        )

        a, b, c = st.columns(
            3
        )

        with a:
            design[
                "show_feature_cards"
            ] = st.toggle(
                "Feature cards",
                value=bool(
                    design.get(
                        "show_feature_cards",
                        True,
                    )
                ),
                key=WIDGET_PREFIX
                + "show_feature_cards",
            )

        with b:
            design[
                "show_start_flows"
            ] = st.toggle(
                "Start flows",
                value=bool(
                    design.get(
                        "show_start_flows",
                        True,
                    )
                ),
                key=WIDGET_PREFIX
                + "show_start_flows",
            )

        with c:
            design[
                "show_open_beta_note"
            ] = st.toggle(
                "Open Beta note",
                value=bool(
                    design.get(
                        "show_open_beta_note",
                        True,
                    )
                ),
                key=WIDGET_PREFIX
                + "show_open_beta_note",
            )

        st.markdown(
            "**Typography**"
        )

        design[
            "hero_font_px"
        ] = st.slider(
            "메인 제목 크기",
            min_value=28,
            max_value=100,
            value=int(
                design.get(
                    "hero_font_px",
                    66,
                )
            ),
            step=1,
            format="%d px",
            key=WIDGET_PREFIX
            + "hero_font_px",
        )

        design[
            "subtitle_font_px"
        ] = st.slider(
            "Hero 설명 크기",
            min_value=12,
            max_value=30,
            value=int(
                design.get(
                    "subtitle_font_px",
                    18,
                )
            ),
            format="%d px",
            key=WIDGET_PREFIX
            + "subtitle_font_px",
        )

        design[
            "section_title_font_px"
        ] = st.slider(
            "섹션 제목 크기",
            min_value=16,
            max_value=44,
            value=int(
                design.get(
                    "section_title_font_px",
                    26,
                )
            ),
            format="%d px",
            key=WIDGET_PREFIX
            + "section_title_font_px",
        )

        x, y = st.columns(2)

        with x:
            design[
                "card_title_font_px"
            ] = st.slider(
                "카드 제목 크기",
                min_value=12,
                max_value=26,
                value=int(
                    design.get(
                        "card_title_font_px",
                        17,
                    )
                ),
                format="%d px",
                key=WIDGET_PREFIX
                + "card_title_font_px",
            )

        with y:
            design[
                "card_body_font_px"
            ] = st.slider(
                "본문 크기",
                min_value=11,
                max_value=22,
                value=int(
                    design.get(
                        "card_body_font_px",
                        15,
                    )
                ),
                format="%d px",
                key=WIDGET_PREFIX
                + "card_body_font_px",
            )

        design[
            "hero_line_height"
        ] = st.slider(
            "메인 제목 줄간격",
            min_value=0.90,
            max_value=1.50,
            value=float(
                design.get(
                    "hero_line_height",
                    1.05,
                )
            ),
            step=0.05,
            key=WIDGET_PREFIX
            + "hero_line_height",
        )

        design[
            "hero_align"
        ] = st.segmented_control(
            "Hero 정렬",
            options=[
                "left",
                "center",
            ],
            format_func=lambda value: (
                "왼쪽"
                if value == "left"
                else "가운데"
            ),
            default=str(
                design.get(
                    "hero_align",
                    "left",
                )
            ),
            key=WIDGET_PREFIX
            + "hero_align",
        ) or "left"

        st.markdown(
            "**Layout**"
        )

        design[
            "page_max_width_px"
        ] = st.slider(
            "페이지 최대 폭",
            min_value=800,
            max_value=1500,
            value=int(
                design.get(
                    "page_max_width_px",
                    1180,
                )
            ),
            step=20,
            format="%d px",
            key=WIDGET_PREFIX
            + "page_max_width_px",
        )

        a, b = st.columns(2)

        with a:
            design[
                "card_radius_px"
            ] = st.slider(
                "카드 둥글기",
                min_value=0,
                max_value=36,
                value=int(
                    design.get(
                        "card_radius_px",
                        18,
                    )
                ),
                format="%d px",
                key=WIDGET_PREFIX
                + "card_radius_px",
            )

        with b:
            design[
                "card_min_height_px"
            ] = st.slider(
                "카드 최소 높이",
                min_value=110,
                max_value=240,
                value=int(
                    design.get(
                        "card_min_height_px",
                        158,
                    )
                ),
                step=4,
                format="%d px",
                key=WIDGET_PREFIX
                + "card_min_height_px",
            )

    return design



def _edit_sidebar(
    draft,
):
    sidebar = copy.deepcopy(
        draft.get(
            "sidebar",
            {},
        )
    )

    with st.expander(
        "🧭 사이드바",
        expanded=True,
    ):
        st.caption(
            "공개 페이지의 공통 사이드바입니다."
        )

        c1, c2 = st.columns(2)

        with c1:
            sidebar[
                "show_knowledge_archive"
            ] = st.toggle(
                "Knowledge Archive 표시",
                value=bool(
                    sidebar.get(
                        "show_knowledge_archive",
                        True,
                    )
                ),
                key=WIDGET_PREFIX
                + "sidebar_show_knowledge",
            )

            sidebar[
                "knowledge_expanded"
            ] = st.toggle(
                "Knowledge Archive 펼치기",
                value=bool(
                    sidebar.get(
                        "knowledge_expanded",
                        True,
                    )
                ),
                key=WIDGET_PREFIX
                + "sidebar_knowledge_expanded",
            )

        with c2:
            sidebar[
                "show_openai_usage"
            ] = st.toggle(
                "OpenAI Usage 표시",
                value=bool(
                    sidebar.get(
                        "show_openai_usage",
                        True,
                    )
                ),
                key=WIDGET_PREFIX
                + "sidebar_show_openai",
            )

            sidebar[
                "openai_expanded"
            ] = st.toggle(
                "OpenAI Usage 펼치기",
                value=bool(
                    sidebar.get(
                        "openai_expanded",
                        False,
                    )
                ),
                key=WIDGET_PREFIX
                + "sidebar_openai_expanded",
            )

        sidebar[
            "order"
        ] = st.segmented_control(
            "순서",
            options=[
                "knowledge_first",
                "openai_first",
            ],
            format_func=lambda value: (
                "Knowledge → OpenAI"
                if value
                == "knowledge_first"
                else "OpenAI → Knowledge"
            ),
            default=str(
                sidebar.get(
                    "order",
                    "knowledge_first",
                )
            ),
            key=WIDGET_PREFIX
            + "sidebar_order",
        ) or "knowledge_first"

        sidebar[
            "openai_detail"
        ] = st.segmented_control(
            "OpenAI Usage 표시",
            options=[
                "minimal",
                "compact",
            ],
            format_func=lambda value: (
                "최소"
                if value == "minimal"
                else "조금 자세히"
            ),
            default=str(
                sidebar.get(
                    "openai_detail",
                    "minimal",
                )
            ),
            key=WIDGET_PREFIX
            + "sidebar_openai_detail",
        ) or "minimal"

        st.caption(
            "기본값은 Knowledge Archive를 위에 두고 OpenAI는 접힌 최소 표시입니다."
        )

    return sidebar


def render_home_editor(
    *,
    lang,
):
    if not _authenticate():
        return

    store = HomeConfigStore()
    published = load_published_home_config(
        store
    )
    defaults = load_default_home_config()

    if DRAFT_KEY not in st.session_state:
        _reset_draft(
            published
        )

    st.title(
        "🛠️ Home Studio"
    )
    st.caption(
        "첫 화면을 브라우저에서 직접 편집하고 Supabase에 게시합니다. "
        "입력값을 바꾸면 오른쪽 preview가 즉시 갱신됩니다."
    )

    top1, top2, top3, top4 = st.columns(
        [1.1, 1.1, 1.1, 2]
    )

    with top1:
        if st.button(
            "💾 저장 & 게시",
            type="primary",
            use_container_width=True,
        ):
            if not store.ping():
                st.error(
                    "Home Studio DB가 준비되지 않았습니다. "
                    "`SUPABASE_HOME_EDITOR_MIGRATION.sql`을 먼저 실행하세요."
                )
            else:
                store.save(
                    st.session_state[
                        DRAFT_KEY
                    ]
                )
                st.success(
                    "게시했습니다."
                )

    with top2:
        if st.button(
            "↩️ 게시본으로 되돌리기",
            use_container_width=True,
        ):
            _reset_draft(
                published
            )
            st.rerun()

    with top3:
        if st.button(
            "🧹 기본값 불러오기",
            use_container_width=True,
        ):
            _reset_draft(
                defaults
            )
            st.rerun()

    with top4:
        c1, c2 = st.columns(
            2
        )

        with c1:
            st.page_link(
                "app.py",
                label="🏠 공개 홈",
                use_container_width=True,
            )

        with c2:
            if st.button(
                "로그아웃",
                use_container_width=True,
            ):
                st.session_state[
                    AUTH_KEY
                ] = False
                st.rerun()

    if not store.ping():
        st.warning(
            "편집/preview는 가능하지만 아직 게시할 수 없습니다. "
            "`SUPABASE_HOME_EDITOR_MIGRATION.sql`을 한 번 실행하세요."
        )

    editor_col, preview_col = st.columns(
        [0.92, 1.38],
        gap="large",
    )

    draft = copy.deepcopy(
        st.session_state[
            DRAFT_KEY
        ]
    )

    with editor_col:
        st.subheader(
            "편집"
        )

        draft[
            "design"
        ] = _edit_design(
            draft
        )

        draft[
            "sidebar"
        ] = _edit_sidebar(
            draft
        )

        ko_tab, en_tab = st.tabs(
            [
                "🇰🇷 한국어",
                "🇺🇸 English",
            ]
        )

        with ko_tab:
            draft[
                "ko"
            ] = _edit_language(
                draft,
                "ko",
                "한국어",
            )

        with en_tab:
            draft[
                "en"
            ] = _edit_language(
                draft,
                "en",
                "English",
            )

    st.session_state[
        DRAFT_KEY
    ] = draft

    with preview_col:
        st.subheader(
            "Live preview"
        )

        preview_lang = st.segmented_control(
            "Preview language",
            options=[
                "ko",
                "en",
            ],
            format_func=lambda value: (
                "한국어"
                if value == "ko"
                else "English"
            ),
            default=(
                "ko"
                if lang == "ko"
                else "en"
            ),
            key="home_editor_preview_lang",
        ) or "ko"

        with st.container(
            border=True
        ):
            render_home(
                draft,
                lang=preview_lang,
                interactive=False,
            )
