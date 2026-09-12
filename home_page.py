"""Public landing-page renderer.

All visual values come from the home configuration so the admin can edit the
landing page without touching Python.
"""

from __future__ import annotations

import html

import streamlit as st


def safe(value) -> str:
    return html.escape(
        str(value or "")
    )


def multiline_html(value) -> str:
    return safe(value).replace(
        "\n",
        "<br>",
    )


def current_copy(
    content,
    lang,
):
    return content.get(
        "ko" if lang == "ko" else "en",
        {},
    )


def _bounded_int(
    value,
    fallback,
    minimum,
    maximum,
):
    try:
        value = int(value)
    except Exception:
        value = fallback

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
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
    copy = current_copy(
        content,
        lang,
    )

    hero_font = _bounded_int(
        design.get("hero_font_px"),
        66,
        28,
        110,
    )
    subtitle_font = _bounded_int(
        design.get("subtitle_font_px"),
        18,
        12,
        32,
    )
    section_font = _bounded_int(
        design.get("section_title_font_px"),
        26,
        16,
        48,
    )
    card_title_font = _bounded_int(
        design.get("card_title_font_px"),
        17,
        12,
        30,
    )
    card_body_font = _bounded_int(
        design.get("card_body_font_px"),
        15,
        11,
        24,
    )
    page_width = _bounded_int(
        design.get("page_max_width_px"),
        1180,
        760,
        1600,
    )
    radius = _bounded_int(
        design.get("card_radius_px"),
        18,
        0,
        40,
    )
    card_height = _bounded_int(
        design.get("card_min_height_px"),
        158,
        110,
        280,
    )

    try:
        hero_line_height = float(
            design.get(
                "hero_line_height",
                1.05,
            )
        )
    except Exception:
        hero_line_height = 1.05

    hero_line_height = max(
        0.85,
        min(
            1.8,
            hero_line_height,
        ),
    )

    hero_align = (
        "center"
        if str(
            design.get(
                "hero_align",
                "left",
            )
        ).lower()
        == "center"
        else "left"
    )

    st.markdown(
        f"""
        <style>
        .block-container {{
            max-width: {page_width}px;
            padding-top: 2.2rem;
            padding-bottom: 4rem;
        }}

        .lal-hero-wrap {{
            text-align: {hero_align};
        }}

        .lal-hero-wrap .lal-hero-copy {{
            margin-left: {"auto" if hero_align == "center" else "0"};
            margin-right: {"auto" if hero_align == "center" else "0"};
        }}

        .lal-badge {{
            display: inline-block;
            padding: .34rem .72rem;
            border-radius: 999px;
            border: 1px solid rgba(49, 51, 63, .14);
            background: rgba(247, 249, 252, .88);
            font-size: .76rem;
            font-weight: 800;
            letter-spacing: .08em;
            margin-bottom: 1rem;
        }}

        .lal-hero-title {{
            font-size: {hero_font}px;
            line-height: {hero_line_height};
            letter-spacing: -.045em;
            font-weight: 850;
            margin: 0 0 1rem 0;
        }}

        .lal-hero-copy {{
            font-size: {subtitle_font}px;
            line-height: 1.75;
            opacity: .78;
            max-width: 780px;
            margin-bottom: 1.5rem;
        }}

        .lal-section-title {{
            font-size: {section_font}px;
            font-weight: 820;
            letter-spacing: -.02em;
            margin-top: .2rem;
            margin-bottom: .35rem;
        }}

        .lal-section-copy {{
            opacity: .68;
            line-height: 1.65;
            margin-bottom: 1.2rem;
        }}

        .lal-feature {{
            border: 1px solid rgba(49, 51, 63, .12);
            border-radius: {radius}px;
            padding: 1.15rem 1.2rem;
            background: rgba(255,255,255,.76);
            min-height: {card_height}px;
        }}

        .lal-feature-icon {{
            font-size: 1.3rem;
            margin-bottom: .65rem;
        }}

        .lal-feature-title {{
            font-size: {card_title_font}px;
            font-weight: 800;
            margin-bottom: .35rem;
        }}

        .lal-feature-copy {{
            line-height: 1.6;
            opacity: .72;
            font-size: {card_body_font}px;
        }}

        .lal-flow {{
            border: 1px solid rgba(49, 51, 63, .12);
            border-radius: {radius}px;
            padding: 1.25rem 1.3rem;
            background: rgba(248, 249, 251, .70);
            min-height: 225px;
        }}

        .lal-flow-title {{
            font-size: {card_title_font + 1}px;
            font-weight: 820;
            margin-bottom: .75rem;
        }}

        .lal-flow-step {{
            margin: .45rem 0;
            line-height: 1.55;
            font-size: {card_body_font}px;
        }}

        .lal-flow-arrow {{
            opacity: .35;
            margin-left: .2rem;
        }}

        .lal-openbeta {{
            border-left: 4px solid #5b8def;
            border-radius: 10px;
            padding: .9rem 1rem;
            background: rgba(91, 141, 239, .07);
            line-height: 1.65;
            font-size: {card_body_font}px;
        }}

        div[data-testid="stPageLink"] a {{
            border-radius: 12px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="lal-hero-wrap">',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="lal-badge">{safe(design.get("badge", "OPEN BETA"))}</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="lal-hero-title">{multiline_html(copy.get("hero_title", ""))}</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="lal-hero-copy">{safe(copy.get("hero_subtitle", ""))}</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )

    start1, start2, spacer = st.columns(
        [1.15, 1.15, 2.7]
    )

    if interactive:
        with start1:
            st.page_link(
                "pages/1_Learn_a_Paper.py",
                label=copy.get(
                    "paper_button",
                    "📄 Start with a paper",
                ),
                use_container_width=True,
            )

        with start2:
            st.page_link(
                "pages/2_Method_Wiki.py",
                label=copy.get(
                    "method_button",
                    "🧬 Explore methods",
                ),
                use_container_width=True,
            )
    else:
        with start1:
            st.button(
                copy.get(
                    "paper_button",
                    "📄 Start with a paper",
                ),
                disabled=True,
                use_container_width=True,
                key="home_preview_paper_button",
            )

        with start2:
            st.button(
                copy.get(
                    "method_button",
                    "🧬 Explore methods",
                ),
                disabled=True,
                use_container_width=True,
                key="home_preview_method_button",
            )

    if design.get(
        "show_feature_cards",
        True,
    ):
        st.write("")
        st.write("")

        st.markdown(
            f'<div class="lal-section-title">{safe(copy.get("feature_section_title", ""))}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="lal-section-copy">{safe(copy.get("feature_section_subtitle", ""))}</div>',
            unsafe_allow_html=True,
        )

        features = [
            (
                copy.get("feature_1_icon", "🎯"),
                copy.get("feature_1_title", ""),
                copy.get("feature_1_text", ""),
            ),
            (
                copy.get("feature_2_icon", "🖼️"),
                copy.get("feature_2_title", ""),
                copy.get("feature_2_text", ""),
            ),
            (
                copy.get("feature_3_icon", "🧬"),
                copy.get("feature_3_title", ""),
                copy.get("feature_3_text", ""),
            ),
            (
                copy.get("feature_4_icon", "🧠"),
                copy.get("feature_4_title", ""),
                copy.get("feature_4_text", ""),
            ),
        ]

        cols = st.columns(4)

        for col, (
            icon,
            title,
            body,
        ) in zip(
            cols,
            features,
        ):
            with col:
                st.markdown(
                    f"""
                    <div class="lal-feature">
                      <div class="lal-feature-icon">{safe(icon)}</div>
                      <div class="lal-feature-title">{safe(title)}</div>
                      <div class="lal-feature-copy">{safe(body)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    if design.get(
        "show_start_flows",
        True,
    ):
        st.write("")
        st.write("")

        st.markdown(
            f'<div class="lal-section-title">{safe(copy.get("flow_section_title", ""))}</div>',
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
                  <div class="lal-flow-title">📄 {safe(copy.get("paper_flow_title", ""))}</div>
                  <div class="lal-flow-step">{safe(copy.get("paper_flow_1", ""))}</div>
                  <div class="lal-flow-arrow">↓</div>
                  <div class="lal-flow-step"><b>{safe(copy.get("paper_flow_2", ""))}</b></div>
                  <div class="lal-flow-arrow">↓</div>
                  <div class="lal-flow-step">{safe(copy.get("paper_flow_3", ""))}</div>
                  <div class="lal-flow-arrow">↓</div>
                  <div class="lal-flow-step">{safe(copy.get("paper_flow_4", ""))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with flow2:
            st.markdown(
                f"""
                <div class="lal-flow">
                  <div class="lal-flow-title">🧬 {safe(copy.get("method_flow_title", ""))}</div>
                  <div class="lal-flow-step">{safe(copy.get("method_flow_1", ""))}</div>
                  <div class="lal-flow-arrow">↓</div>
                  <div class="lal-flow-step"><b>{safe(copy.get("method_flow_2", ""))}</b></div>
                  <div class="lal-flow-arrow">↓</div>
                  <div class="lal-flow-step">{safe(copy.get("method_flow_3", ""))}</div>
                  <div class="lal-flow-arrow">↓</div>
                  <div class="lal-flow-step">{safe(copy.get("method_flow_4", ""))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if design.get(
        "show_open_beta_note",
        True,
    ):
        st.write("")
        st.write("")

        st.markdown(
            (
                '<div class="lal-openbeta"><b>'
                + safe(
                    design.get(
                        "badge",
                        "OPEN BETA",
                    )
                )
                + "</b> · "
                + safe(
                    copy.get(
                        "open_beta_note",
                        "",
                    )
                )
                + "</div>"
            ),
            unsafe_allow_html=True,
        )

    st.write("")

    if interactive:
        st.page_link(
            "pages/5_About.py",
            label=copy.get(
                "about_link",
                "Learn more about LALSTUDY →",
            ),
            icon="ℹ️",
        )
