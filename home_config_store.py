"""Persistent Home Studio configuration.

Public home content:
1. HOME_CONTENT.toml provides safe defaults.
2. Supabase `home_page_config` overrides those defaults after an admin publishes.

The public browser never receives the Supabase secret key.
"""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any, Dict

import streamlit as st
from supabase import create_client


HOME_CONTENT_PATH = Path(__file__).with_name("HOME_CONTENT.toml")
HOME_CONFIG_SLUG = "default"


def load_default_home_config() -> Dict[str, Any]:
    with HOME_CONTENT_PATH.open("rb") as file:
        return tomllib.load(file)


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    output = copy.deepcopy(base)

    for key, value in (override or {}).items():
        if (
            isinstance(value, dict)
            and isinstance(output.get(key), dict)
        ):
            output[key] = deep_merge(
                output[key],
                value,
            )
        else:
            output[key] = copy.deepcopy(value)

    return output


def _secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default

    return str(value or "").strip()


class HomeConfigStore:
    def __init__(self):
        self.url = _secret("SUPABASE_URL")
        self.secret_key = _secret("SUPABASE_SECRET_KEY")
        self.client = None
        self.error = ""

        if not self.url or not self.secret_key:
            self.error = "Supabase secrets are missing."
            return

        try:
            self.client = create_client(
                self.url,
                self.secret_key,
            )
        except Exception as exc:
            self.error = str(exc)

    @property
    def configured(self) -> bool:
        return self.client is not None

    def ping(self) -> bool:
        if not self.client:
            return False

        try:
            (
                self.client
                .table("home_page_config")
                .select("slug")
                .limit(1)
                .execute()
            )
            self.error = ""
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    def load_override(self) -> Dict[str, Any]:
        if not self.client:
            return {}

        try:
            response = (
                self.client
                .table("home_page_config")
                .select("config")
                .eq("slug", HOME_CONFIG_SLUG)
                .limit(1)
                .execute()
            )

            rows = response.data or []

            if not rows:
                return {}

            config = rows[0].get("config") or {}

            return (
                config
                if isinstance(config, dict)
                else {}
            )

        except Exception as exc:
            self.error = str(exc)
            return {}

    def save(self, config: Dict[str, Any]) -> None:
        if not self.client:
            raise RuntimeError(
                "Supabase is not configured."
            )

        payload = {
            "slug": HOME_CONFIG_SLUG,
            "config": config,
        }

        (
            self.client
            .table("home_page_config")
            .upsert(
                payload,
                on_conflict="slug",
            )
            .execute()
        )

    def clear_override(self) -> None:
        if not self.client:
            raise RuntimeError(
                "Supabase is not configured."
            )

        (
            self.client
            .table("home_page_config")
            .delete()
            .eq("slug", HOME_CONFIG_SLUG)
            .execute()
        )


def load_published_home_config(store: HomeConfigStore | None = None) -> Dict[str, Any]:
    defaults = load_default_home_config()
    store = store or HomeConfigStore()

    if not store.configured:
        return defaults

    override = store.load_override()

    return deep_merge(
        defaults,
        override,
    )
