import os
from datetime import datetime, timezone

import streamlit as st

from openai_usage_sync import fetch_openai_official_usage

USAGE_STATE_KEY = "lal_ai_usage_daily_v1"
OPENAI_REFRESH_NONCE_KEY = "lal_openai_usage_refresh_nonce_v1"


def _L(lang: str, ko: str, en: str) -> str:
    return ko if lang == "ko" else en


def _get_secret_or_env(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            value = str(st.secrets[name]).strip()
            if value:
                return value
    except Exception:
        pass
    return str(os.getenv(name, default) or "").strip()


def get_openai_api_key() -> str:
    return _get_secret_or_env("OPENAI_API_KEY", "")


def get_openai_admin_key() -> str:
    return _get_secret_or_env("OPENAI_ADMIN_KEY", "")


def openai_sdk_available() -> bool:
    try:
        from openai import OpenAI  # noqa: F401
        return True
    except Exception:
        return False


def openai_ready() -> bool:
    return openai_sdk_available() and bool(get_openai_api_key())


def _safe_int(value, default: int) -> int:
    try:
        return int(str(value).replace(",", "").strip())
    except Exception:
        return default


def openai_daily_budget() -> int:
    raw = _get_secret_or_env(
        "OPENAI_COMPLIMENTARY_DAILY_TOKENS",
        _get_secret_or_env("OPENAI_DAILY_TOKEN_BUDGET", "2500000"),
    )
    return _safe_int(raw, 2_500_000)


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_openai_app_usage() -> dict:
    usage_root = st.session_state.get(USAGE_STATE_KEY, {}) or {}
    today = usage_root.get(_today_key(), {}) or {}
    bucket = today.get("openai", {}) or {}
    return {
        "input_tokens": int(bucket.get("input_tokens", 0) or 0),
        "output_tokens": int(bucket.get("output_tokens", 0) or 0),
        "total_tokens": int(bucket.get("total_tokens", 0) or 0),
        "calls": int(bucket.get("calls", 0) or 0),
    }


def _official_openai_snapshot() -> dict:
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
    """Compact single-column OpenAI usage panel for the narrow Streamlit sidebar."""
    official = _official_openai_snapshot()
    ready = openai_ready()

    with st.sidebar:
        with st.expander("🤖 OpenAI Usage", expanded=True):
            if ready:
                st.caption("🟢 OpenAI READY")
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
                used = int(official.get("complimentary_used_tokens", 0) or 0)
                remaining = official.get("complimentary_remaining_tokens")
                requests_count = int(official.get("eligible_group_requests", 0) or 0)
                exact = bool(official.get("complimentary_exact"))
                budget = int(official.get("daily_budget", 0) or 0)

                st.divider()

                if remaining is not None:
                    st.caption(
                        _L(
                            lang,
                            "무료 잔량" if exact else "추정 무료 잔량",
                            "Free tokens left" if exact else "Estimated free tokens left",
                        )
                    )
                    # Normal body-sized text instead of st.metric / heading-size text.
                    st.write(f"**{int(remaining):,} tokens**")

                if budget > 0:
                    ratio = min(max(used / budget, 0.0), 1.0)
                    st.progress(ratio)
                    st.caption(
                        _L(lang, "오늘 사용", "Used today")
                        + f" · {used:,} / {budget:,} tokens"
                    )
                else:
                    st.caption(
                        _L(lang, "오늘 사용", "Used today")
                        + f" · {used:,} tokens"
                    )

                cost = official.get("today_cost_usd")
                summary_parts = [
                    _L(lang, "요청", "Requests") + f" {requests_count:,}"
                ]
                if cost is not None:
                    summary_parts.append(
                        _L(lang, "오늘 과금", "Cost today") + f" ${float(cost):.4f}"
                    )
                st.caption(" · ".join(summary_parts))

                if exact:
                    st.caption(
                        _L(
                            lang,
                            "🟢 공식 complimentary-token usage 확인됨",
                            "🟢 Official complimentary-token usage confirmed",
                        )
                    )
               
                if st.button(
                    _L(lang, "↻ 공식 usage 새로고침", "↻ Refresh official usage"),
                    key="lal_refresh_openai_official_usage",
                    use_container_width=True,
                ):
                    st.session_state[OPENAI_REFRESH_NONCE_KEY] = (
                        int(st.session_state.get(OPENAI_REFRESH_NONCE_KEY, 0) or 0) + 1
                    )
                    st.rerun()

            else:
                usage = get_openai_app_usage()
                budget = openai_daily_budget()
                remaining = max(budget - usage["total_tokens"], 0) if budget > 0 else None

                st.divider()
                st.caption(_L(lang, "앱 추적 추정 잔량", "App-tracked estimated balance"))
                if remaining is not None:
                    st.write(f"**{remaining:,} tokens**")
                if budget > 0:
                    ratio = min(max(usage["total_tokens"] / budget, 0.0), 1.0)
                    st.progress(ratio)
                st.caption(
                    _L(lang, "오늘 앱 추적 사용", "App-tracked usage today")
                    + f" · {usage['total_tokens']:,} tokens"
                )
                st.caption(
                    _L(lang, "호출", "Calls")
                    + f" · {usage['calls']:,}"
                )

                if not get_openai_admin_key():
                    st.caption(
                        _L(
                            lang,
                            "ⓘ OPENAI_ADMIN_KEY를 추가하면 공식 Usage/Costs sync를 사용할 수 있습니다.",
                            "ⓘ Add OPENAI_ADMIN_KEY to enable official Usage/Costs sync.",
                        )
                    )
                else:
                    st.error(official.get("error", "Official OpenAI sync failed."))

            with st.expander(_L(lang, "Usage 상세", "Usage details"), expanded=False):
                app_usage = get_openai_app_usage()
                st.write(
                    {
                        "app_input_tokens": app_usage["input_tokens"],
                        "app_output_tokens": app_usage["output_tokens"],
                        "app_total_tokens": app_usage["total_tokens"],
                        "app_calls": app_usage["calls"],
                    }
                )
                if official.get("ok"):
                    st.write(
                        {
                            "official_total_tokens_today": official.get("total_tokens"),
                            "eligible_group_tokens": official.get("eligible_group_tokens"),
                            "complimentary_used": official.get("complimentary_used_tokens"),
                            "complimentary_exact": official.get("complimentary_exact"),
                            "service_tiers": official.get("service_tiers"),
                        }
                    )


def render_ai_provider_panel(*, lang: str = "ko") -> None:
    """Backward-compatible alias retained for older pages."""
    render_openai_usage_panel(lang=lang)
