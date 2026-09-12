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

    nonce = int(st.session_state.get(OPENAI_REFRESH_NONCE_KEY, 0) or 0)
    return fetch_openai_official_usage(
        admin_key=admin_key,
        daily_budget=openai_daily_budget(),
        refresh_nonce=nonce,
    )


def render_openai_usage_panel(*, lang: str = "ko") -> None:
    """Official-only OpenAI usage UI.

    Rules for this panel:
    - Never show app-estimated remaining quota.
    - Never use st.metric or multi-column number cards in the narrow sidebar.
    - Show complimentary remaining tokens only when the official Usage API
      actually exposes the data-sharing incentive service tier.
    """
    official = _official_snapshot()

    with st.sidebar:
        with st.expander("🤖 OpenAI Usage", expanded=True):
            if openai_ready():
                st.success("OpenAI READY")
            else:
                st.error(
                    _L(
                        lang,
                        "OPENAI_API_KEY 또는 OpenAI SDK가 준비되지 않았습니다.",
                        "OPENAI_API_KEY or the OpenAI SDK is not ready.",
                    )
                )

            st.caption(
                _L(
                    lang,
                    "LALSTUDY의 모든 AI 분석은 OpenAI를 사용합니다.",
                    "All LALSTUDY AI analysis uses OpenAI.",
                )
            )

            if official.get("ok"):
                total_tokens = int(official.get("total_tokens", 0) or 0)
                total_requests = int(official.get("total_requests", 0) or 0)
                cost = official.get("today_cost_usd")

                st.divider()

                # Compact text-only layout: no st.metric, no columns, no giant digits.
                st.markdown(
                    f"""
<div style="font-size:0.92rem; line-height:1.25;">
  <div style="opacity:0.72;">{_L(lang, '오늘 공식 사용량', 'Official usage today')}</div>
  <div><strong>{total_tokens:,} tokens</strong></div>
  <div style="margin-top:0.10rem; opacity:0.82;">
    {_L(lang, '요청', 'Requests')} {total_requests:,}
    {(' · ' + _L(lang, '오늘 과금', 'Cost today') + ' $' + format(float(cost), '.4f')) if cost is not None else ''}
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )

                # Only show free-token balance when the official service tier is visible.
                if bool(official.get("complimentary_exact")):
                    used = int(official.get("complimentary_used_tokens", 0) or 0)
                    remaining = official.get("complimentary_remaining_tokens")
                    budget = int(official.get("daily_budget", 0) or 0)

                    st.divider()
                    st.caption(
                        _L(
                            lang,
                            "무료 토큰 · 공식 incentive tier",
                            "Complimentary tokens · official incentive tier",
                        )
                    )

                    if remaining is not None:
                        st.markdown(
                            f"""
<div style="font-size:0.92rem; line-height:1.25;">
  <div>{_L(lang, '사용', 'Used')} <strong>{used:,}</strong> tokens</div>
  <div>{_L(lang, '잔여', 'Remaining')} <strong>{int(remaining):,}</strong> tokens</div>
</div>
""",
                            unsafe_allow_html=True,
                        )

                    if budget > 0:
                        st.progress(min(max(used / budget, 0.0), 1.0))
                else:
                    # Deliberately omit any estimated complimentary balance.
                    st.caption(
                        _L(
                            lang,
                            "🟢 공식 Usage sync 완료",
                            "🟢 Official Usage sync complete",
                        )
                    )

                synced = official.get("synced_at_utc")
                if synced:
                    st.caption(f"sync · {synced} UTC")

                if st.button(
                    _L(lang, "↻ 공식 usage 새로고침", "↻ Refresh official usage"),
                    key="lal_refresh_openai_official_usage_v0412",
                    use_container_width=True,
                ):
                    st.session_state[OPENAI_REFRESH_NONCE_KEY] = (
                        int(st.session_state.get(OPENAI_REFRESH_NONCE_KEY, 0) or 0) + 1
                    )
                    st.rerun()

            else:
                # No estimates. If official sync is unavailable, say only that.
                st.divider()
                if not get_openai_admin_key():
                    st.caption(
                        _L(
                            lang,
                            "공식 usage 표시에는 OPENAI_ADMIN_KEY가 필요합니다.",
                            "OPENAI_ADMIN_KEY is required for official usage display.",
                        )
                    )
                else:
                    st.caption(
                        _L(
                            lang,
                            "공식 usage를 불러오지 못했습니다.",
                            "Official usage could not be loaded.",
                        )
                    )
                    with st.expander(_L(lang, "오류 보기", "View error"), expanded=False):
                        st.code(str(official.get("error", "Unknown error")))

            # Visible deployment marker so stale UI is obvious immediately.
            st.caption("usage UI · v0.4.1.2")
