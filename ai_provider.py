import os
from datetime import datetime, timezone

import streamlit as st

from openai_usage_sync import fetch_openai_official_usage

USAGE_STATE_KEY = "lal_ai_usage_daily_v1"
SELECTED_PROVIDER_KEY = "lal_selected_ai_provider_v1"
OPENAI_REFRESH_NONCE_KEY = "lal_openai_usage_refresh_nonce_v1"

PROVIDERS = ["gemini", "openai"]


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


def get_provider_api_key(provider: str) -> str:
    mapping = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    return _get_secret_or_env(mapping.get(provider, ""), "")


def get_openai_admin_key() -> str:
    return _get_secret_or_env("OPENAI_ADMIN_KEY", "")


def provider_sdk_available(provider: str) -> bool:
    provider = (provider or "gemini").lower()

    if provider == "gemini":
        try:
            from google import genai  # noqa: F401
            from google.genai import types  # noqa: F401
            return True
        except Exception:
            return False

    if provider == "openai":
        try:
            from openai import OpenAI  # noqa: F401
            return True
        except Exception:
            return False

    return False


def provider_ready(provider: str) -> bool:
    return provider_sdk_available(provider) and bool(get_provider_api_key(provider))


def provider_label(provider: str, lang: str = "ko") -> str:
    provider = (provider or "gemini").lower()
    return "OpenAI" if provider == "openai" else "Gemini"


def _safe_int(value, default: int) -> int:
    try:
        return int(str(value).replace(",", "").strip())
    except Exception:
        return default


def provider_daily_budget(provider: str) -> int:
    provider = (provider or "gemini").lower()

    if provider == "openai":
        raw = _get_secret_or_env(
            "OPENAI_COMPLIMENTARY_DAILY_TOKENS",
            _get_secret_or_env("OPENAI_DAILY_TOKEN_BUDGET", "2500000"),
        )
        return _safe_int(raw, 2_500_000)

    raw = _get_secret_or_env("GEMINI_DAILY_TOKEN_BUDGET", "0")
    return _safe_int(raw, 0)


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_provider_usage(provider: str) -> dict:
    usage_root = st.session_state.get(USAGE_STATE_KEY, {}) or {}
    today = usage_root.get(_today_key(), {}) or {}
    bucket = today.get(provider, {}) or {}

    return {
        "input_tokens": int(bucket.get("input_tokens", 0) or 0),
        "output_tokens": int(bucket.get("output_tokens", 0) or 0),
        "total_tokens": int(bucket.get("total_tokens", 0) or 0),
        "calls": int(bucket.get("calls", 0) or 0),
    }


def get_selected_provider() -> str:
    current = st.session_state.get(SELECTED_PROVIDER_KEY)

    if current in PROVIDERS:
        return current

    if provider_ready("openai"):
        current = "openai"
    elif provider_ready("gemini"):
        current = "gemini"
    else:
        current = "gemini"

    st.session_state[SELECTED_PROVIDER_KEY] = current
    return current


def set_selected_provider(provider: str):
    provider = (provider or "gemini").lower()
    if provider not in PROVIDERS:
        provider = "gemini"
    st.session_state[SELECTED_PROVIDER_KEY] = provider


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
        daily_budget=provider_daily_budget("openai"),
        refresh_nonce=nonce,
    )


def _provider_summary_line(provider: str, lang: str, official_openai: dict) -> str:
    if provider == "openai" and official_openai.get("ok"):
        remaining = official_openai.get("complimentary_remaining_tokens")
        exact = bool(official_openai.get("complimentary_exact"))
        badge = "🟢 Official" if exact else "🟡 Official usage"
        if remaining is None:
            return f"{badge} · OpenAI"
        suffix = "" if exact else "*"
        return f"{badge} · OpenAI · {remaining:,}{suffix} left"

    usage = get_provider_usage(provider)
    budget = provider_daily_budget(provider)
    if budget > 0:
        remaining = max(budget - usage["total_tokens"], 0)
        return f"⚪ App estimate · {provider_label(provider, lang)} · {remaining:,} left"

    return f"⚪ App estimate · {provider_label(provider, lang)}"


def render_ai_provider_panel(*, lang: str = "ko") -> str:
    """
    Global sidebar selector. The chosen provider persists in session state,
    so later AI calls keep using it until the user changes it.
    """
    current = get_selected_provider()
    official_openai = _official_openai_snapshot()

    with st.sidebar:
        with st.expander("🤖 AI Engine", expanded=True):
            st.caption(
                _L(
                    lang,
                    "한 번 선택하면 이후 AI 분석에 계속 적용됩니다. 중간에 바꾸면 그 다음 호출부터 새 provider를 사용합니다.",
                    "Your selection persists for later AI analyses. If you switch, the next call uses the new provider.",
                )
            )

            st.caption(_provider_summary_line("openai", lang, official_openai))
            st.caption(_provider_summary_line("gemini", lang, official_openai))

            choice = st.radio(
                _L(lang, "AI provider", "AI provider"),
                options=PROVIDERS,
                index=PROVIDERS.index(current),
                format_func=lambda p: provider_label(p, lang),
                key="lal_ai_provider_radio_v1",
            )

            if choice != current:
                set_selected_provider(choice)
                current = choice

            readiness_lines = []
            for provider in PROVIDERS:
                sdk_ok = provider_sdk_available(provider)
                key_ok = bool(get_provider_api_key(provider))
                ready = provider_ready(provider)
                readiness_lines.append(
                    f"- {provider_label(provider, lang)}: "
                    f"{'READY' if ready else 'NOT READY'} "
                    f"(SDK {'✅' if sdk_ok else '❌'}, KEY {'✅' if key_ok else '❌'})"
                )

            st.markdown("\n".join(readiness_lines))

            # -------------------------------------------------
            # OPENAI: official organization usage when possible
            # -------------------------------------------------
            if current == "openai" and official_openai.get("ok"):
                used = int(official_openai.get("complimentary_used_tokens", 0) or 0)
                remaining = official_openai.get("complimentary_remaining_tokens")
                requests_count = int(official_openai.get("eligible_group_requests", 0) or 0)
                exact = bool(official_openai.get("complimentary_exact"))

                c1, c2, c3 = st.columns(3)
                c1.metric(_L(lang, "무료 사용", "Free used"), f"{used:,}")
                c2.metric(
                    _L(lang, "무료 잔량", "Free left"),
                    f"{remaining:,}" if remaining is not None else "—",
                )
                c3.metric(_L(lang, "요청", "Requests"), f"{requests_count:,}")

                if exact:
                    st.success(
                        _L(
                            lang,
                            "🟢 OpenAI 공식 Usage API · data-sharing incentive tier 기준",
                            "🟢 OpenAI official Usage API · data-sharing incentive tier",
                        )
                    )
                else:
                    st.warning(
                        _L(
                            lang,
                            "🟡 OpenAI 공식 usage는 동기화됐지만 incentive service tier가 응답에서 확인되지 않았습니다. 별표(*) 잔량은 eligible model usage를 이용한 보수적 추정입니다.",
                            "🟡 Official OpenAI usage synced, but the incentive service tier was not visible in the response. Remaining values marked * use eligible-model usage as a conservative fallback.",
                        )
                    )

                cost = official_openai.get("today_cost_usd")
                if cost is not None:
                    st.caption(
                        _L(lang, "오늘 공식 과금", "Official billed cost today")
                        + f": ${float(cost):.4f}"
                    )

                synced = official_openai.get("synced_at_utc")
                if synced:
                    st.caption(f"sync: {synced} UTC")

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
                # Gemini, or OpenAI without Admin API access: app-side estimate.
                usage = get_provider_usage(current)
                budget = provider_daily_budget(current)
                used = usage["total_tokens"]
                remaining = max(budget - used, 0) if budget > 0 else None

                c1, c2, c3 = st.columns(3)
                c1.metric(_L(lang, "현재", "Current"), provider_label(current, lang))
                c2.metric(_L(lang, "앱 추적 사용", "App-tracked"), f"{used:,}")
                c3.metric(
                    _L(lang, "추정 잔량", "Est. left"),
                    f"{remaining:,}" if remaining is not None else "—",
                )

                if current == "openai":
                    st.info(
                        _L(
                            lang,
                            "OPENAI_ADMIN_KEY를 추가하면 OpenAI Organization Usage/Costs API로 공식 동기화됩니다.",
                            "Add OPENAI_ADMIN_KEY to enable official OpenAI Organization Usage/Costs sync.",
                        )
                    )
                else:
                    st.caption(
                        _L(
                            lang,
                            "Gemini는 현재 앱 추적값입니다. Google Cloud quota sync는 후속 버전에서 연결할 수 있습니다.",
                            "Gemini currently uses app-tracked usage. Google Cloud quota sync can be connected in a later version.",
                        )
                    )

            with st.expander(_L(lang, "Usage 상세", "Usage details"), expanded=False):
                for provider in PROVIDERS:
                    provider_usage = get_provider_usage(provider)
                    st.write(
                        {
                            "provider": provider_label(provider, lang),
                            "app_input_tokens": provider_usage["input_tokens"],
                            "app_output_tokens": provider_usage["output_tokens"],
                            "app_total_tokens": provider_usage["total_tokens"],
                            "app_calls": provider_usage["calls"],
                        }
                    )

                if official_openai.get("ok"):
                    st.write(
                        {
                            "OpenAI official total tokens today": official_openai.get("total_tokens"),
                            "OpenAI eligible-group tokens": official_openai.get("eligible_group_tokens"),
                            "OpenAI complimentary used": official_openai.get("complimentary_used_tokens"),
                            "OpenAI complimentary exact": official_openai.get("complimentary_exact"),
                            "OpenAI service tiers": official_openai.get("service_tiers"),
                            "OpenAI models": official_openai.get("models"),
                        }
                    )
                elif get_openai_admin_key():
                    st.error(official_openai.get("error", "Official OpenAI sync failed."))

            st.caption(
                _L(
                    lang,
                    "OpenAI 공식 sync에는 서버의 Admin API key가 사용되며 브라우저에는 노출되지 않습니다. 무료 토큰 한도는 설정값이며 현재 계정 화면의 2.5M/day 기준입니다.",
                    "OpenAI official sync uses a server-side Admin API key and never exposes it to the browser. The complimentary budget is configurable and defaults to the account's current 2.5M/day offer.",
                )
            )

    return current
