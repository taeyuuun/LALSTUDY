"""Shared public sidebar.

The sidebar order/visibility is controlled by the same persistent config used
by Home Studio. This keeps public pages consistent and avoids page-specific
sidebar spaghetti.
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


def load_sidebar_config():
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
):
    config = load_sidebar_config()

    def knowledge():
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

    def usage():
        if not config.get(
            "show_openai_usage",
            True,
        ):
            return

        render_openai_usage_panel(
            lang=lang
        )

    if (
        config.get(
            "order"
        )
        == "openai_first"
    ):
        usage()
        knowledge()
    else:
        knowledge()
        usage()
