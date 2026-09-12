"""Canonical OpenAI sidebar UI.

Architecture:
- ai_provider.py: OpenAI keys/readiness/state
- openai_usage_sync.py: official usage retrieval
- openai_sidebar.py: OpenAI sidebar rendering
"""

from __future__ import annotations

import streamlit as st

from ai_provider import (
    OPENAI_REFRESH_NONCE_KEY,
    get_openai_admin_key,
    openai_daily_budget,
    openai_ready,
)
from openai_usage_sync import fetch_openai_official_usage


def _L(lang: str, ko: str, en: str) -> str:
    return ko if lang == "ko" else en


def _official_snapshot() -> dict:
    admin_key = get_openai_admin_key()

    if not admin_key:
        return {
            "ok": False,
            "official": False,
            "error": "OPENAI_ADMIN_KEY is not configured.",
        }

    nonce = int(
        st.session_state.get(
            OPENAI_REFRESH_NONCE_KEY,
            0,
        )
        or 0
    )

    return fetch_openai_official_usage(
        admin_key=admin_key,
        daily_budget=openai_daily_budget(),
        refresh_nonce=nonce,
    )


def render_openai_usage_panel(
    *,
    lang: str = "ko",
    expanded: bool = False,
    detail: str = "minimal",
    show_divider: bool = False,  # compatibility only; intentionally unused
) -> None:
    """Compact public OpenAI widget with no developer/debug copy."""

    ready = openai_ready()
    official = _official_snapshot()

    title = (
        "🟢 OpenAI Usage"
        if ready
        else "⚪ OpenAI Usage"
    )

    with st.sidebar:
        with st.expander(
            title,
            expanded=expanded,
        ):
            if ready:
                st.success("OpenAI READY")
            else:
                st.error(
                    _L(
                        lang,
                        "OpenAI 연결 필요",
                        "OpenAI connection required",
                    )
                )
                return

            if official.get("ok"):
                total_tokens = int(
                    official.get(
                        "total_tokens",
                        0,
                    )
                    or 0
                )
                total_requests = int(
                    official.get(
                        "total_requests",
                        0,
                    )
                    or 0
                )
                cost = official.get(
                    "today_cost_usd"
                )

                cost_text = (
                    f" · ${float(cost):.4f}"
                    if cost is not None
                    else ""
                )

                st.markdown(
                    f"""
<div style="font-size:0.92rem; line-height:1.20; margin:0; padding:0;">
  <div><strong>{total_tokens:,} tokens</strong></div>
  <div style="margin-top:0.05rem; opacity:0.82;">
    {_L(lang, '요청', 'Requests')} {total_requests:,}{cost_text}
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )

                if (
                    detail == "compact"
                    and bool(
                        official.get(
                            "complimentary_exact"
                        )
                    )
                ):
                    remaining = official.get(
                        "complimentary_remaining_tokens"
                    )
                    if remaining is not None:
                        st.caption(
                            _L(
                                lang,
                                f"무료 잔여 {int(remaining):,} tokens",
                                f"Complimentary {int(remaining):,} tokens left",
                            )
                        )

                if st.button(
                    "↻",
                    key="lal_refresh_openai_usage_v063",
                    help=_L(
                        lang,
                        "사용량 새로고침",
                        "Refresh usage",
                    ),
                ):
                    st.session_state[
                        OPENAI_REFRESH_NONCE_KEY
                    ] = (
                        int(
                            st.session_state.get(
                                OPENAI_REFRESH_NONCE_KEY,
                                0,
                            )
                            or 0
                        )
                        + 1
                    )
                    st.rerun()

            elif detail == "compact":
                st.caption(
                    _L(
                        lang,
                        "공식 사용량을 불러올 수 없습니다.",
                        "Official usage is unavailable.",
                    )
                )
