import os
from datetime import datetime, timezone

import streamlit as st

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

# Backward-compatible wrappers only.
# Actual OpenAI UI lives in openai_sidebar.py.
def render_openai_usage_panel(*, lang: str = "ko") -> None:
    from openai_sidebar import render_openai_usage_panel as _render
    _render(lang=lang)


def render_ai_provider_panel(*, lang: str = "ko") -> None:
    render_openai_usage_panel(lang=lang)
