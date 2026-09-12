import streamlit as st

from home_config_store import (
    HomeConfigStore,
    load_published_home_config,
)
from home_editor import render_home_editor
from home_page import render_home
from i18n import language_selector
from sidebar_ui import render_public_sidebar


APP_VERSION = "v0.6.3-open-beta"


st.set_page_config(
    page_title="LALSTUDY",
    page_icon="🧬",
    layout="wide",
)


lang = language_selector()

editor_mode = (
    str(
        st.query_params.get(
            "home_editor",
            "",
        )
    )
    == "1"
)


if editor_mode:
    render_home_editor(
        lang=lang
    )

else:
    render_public_sidebar(
        lang=lang
    )

    store = HomeConfigStore()

    content = (
        load_published_home_config(
            store
        )
    )

    render_home(
        content,
        lang=lang,
        interactive=True,
    )
