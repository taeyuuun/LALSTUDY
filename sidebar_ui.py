"""Shared public sidebar.

This file only orchestrates visibility/order/state.
Actual widgets live in their own modules.
"""

from __future__ import annotations

from home_config_store import (
    HomeConfigStore,
    load_published_home_config,
)
from knowledge_widget import render_knowledge_archive_widget
from openai_sidebar import render_openai_usage_panel


DEFAULTS = {
    "show_knowledge_archive": True,
    "knowledge_expanded": True,
    "show_openai_usage": True,
    "openai_expanded": False,
    "openai_detail": "minimal",
    "order": "knowledge_first",
}


def load_sidebar_config() -> dict:
    config = load_published_home_config(
        HomeConfigStore()
    )

    sidebar = dict(DEFAULTS)
    sidebar.update(
        config.get(
            "sidebar",
            {},
        )
        or {}
    )
    return sidebar


def render_public_sidebar(
    *,
    lang: str,
    depth: str = "undergraduate",
    paper_context: str = "",
) -> None:
    config = load_sidebar_config()

    def knowledge() -> None:
        if not config.get(
            "show_knowledge_archive",
            True,
        ):
            return

        render_knowledge_archive_widget(
            lang=lang,
            depth=depth,
            paper_context=paper_context,
            compact=True,
            expanded=bool(
                config.get(
                    "knowledge_expanded",
                    True,
                )
            ),
            show_divider=False,
        )

    def usage() -> None:
        if not config.get(
            "show_openai_usage",
            True,
        ):
            return

        render_openai_usage_panel(
            lang=lang,
            expanded=bool(
                config.get(
                    "openai_expanded",
                    False,
                )
            ),
            detail=str(
                config.get(
                    "openai_detail",
                    "minimal",
                )
            ),
            show_divider=False,
        )

    if (
        config.get(
            "order",
            "knowledge_first",
        )
        == "openai_first"
    ):
        usage()
        knowledge()
    else:
        knowledge()
        usage()
