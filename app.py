import streamlit as st

from home_config_store import (
    HomeConfigStore,
    load_published_home_config,
)
from home_editor import render_home_editor
from home_page import render_home
from i18n import language_selector
from knowledge_widget import render_knowledge_archive_widget


APP_VERSION = "v0.6.1-open-beta"


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
    render_knowledge_archive_widget(
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
