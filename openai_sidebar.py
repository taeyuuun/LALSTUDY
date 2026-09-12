import streamlit as st

from ai_provider import (
    get_openai_admin_key,
    openai_ready,
    OPENAI_REFRESH_NONCE_KEY,
)
from openai_usage_sync import fetch_openai_official_usage
from ai_provider import openai_daily_budget


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


def _compact_number(value: int) -> str:
    value = int(value or 0)

    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"

    if value >= 1_000:
        return f"{value / 1_000:.1f}k"

    return f"{value:,}"


def render_openai_usage_panel(
    *,
    lang: str = "ko",
    expanded: bool = False,
    detail: str = "minimal",
    show_divider: bool = False,
) -> None:
    """
    Public OpenAI usage widget.

    `minimal` deliberately keeps operational/developer copy out of the UI.
    Official usage is shown only when OpenAI exposes it through the admin API.
    """

    official = _official_snapshot()

    total_tokens = int(
        official.get(
            "total_tokens",
            0,
        )
        or 0
    )

    title = (
        "🟢 OpenAI"
        if openai_ready()
        else "⚪ OpenAI"
    )

    if (
        detail == "minimal"
        and official.get("ok")
    ):
        title += (
            " · "
            + _compact_number(
                total_tokens
            )
            + " tok"
        )

    with st.sidebar:
        if show_divider:
            st.divider()

        with st.expander(
            title,
            expanded=expanded,
        ):
            if not openai_ready():
                st.error(
                    _L(
                        lang,
                        "OpenAI 연결 필요",
                        "OpenAI connection required",
                    )
                )
                return

            st.success(
                _L(
                    lang,
                    "OpenAI 사용 가능",
                    "OpenAI available",
                )
            )

            if official.get("ok"):
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

                if detail == "minimal":
                    parts = [
                        _L(
                            lang,
                            f"오늘 {_compact_number(total_tokens)} tokens",
                            f"Today {_compact_number(total_tokens)} tokens",
                        ),
                        f"{total_requests:,} req",
                    ]

                    if cost is not None:
                        parts.append(
                            f"${float(cost):.4f}"
                        )

                    st.caption(
                        " · ".join(parts)
                    )

                else:
                    st.markdown(
                        (
                            f"**{total_tokens:,} tokens**  \n"
                            f"{total_requests:,} requests"
                            + (
                                f" · ${float(cost):.4f}"
                                if cost is not None
                                else ""
                            )
                        )
                    )

                if bool(
                    official.get(
                        "complimentary_exact"
                    )
                ):
                    remaining = official.get(
                        "complimentary_remaining_tokens"
                    )

                    if remaining is not None:
                        st.caption(
                            _L(
                                lang,
                                f"무료 잔여 {_compact_number(int(remaining))} tokens",
                                f"Complimentary {_compact_number(int(remaining))} tokens left",
                            )
                        )

                if st.button(
                    "↻",
                    key="lal_refresh_openai_usage_compact",
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

            else:
                # Do not surface setup instructions to normal users.
                if detail != "minimal":
                    st.caption(
                        _L(
                            lang,
                            "공식 사용량을 표시할 수 없습니다.",
                            "Official usage is unavailable.",
                        )
                    )
