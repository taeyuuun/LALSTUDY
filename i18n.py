import streamlit as st

from terminology import terminology_selector

LANG_OPTIONS = {"한국어": "ko", "English": "en"}

def language_selector():
    if "lalstudy_language_label" not in st.session_state:
        st.session_state.lalstudy_language_label = "한국어"
    label = st.sidebar.selectbox(
        "🌐 Language / 언어",
        list(LANG_OPTIONS.keys()),
        key="lalstudy_language_label",
    )
    lang = LANG_OPTIONS[label]
    terminology_selector(lang)
    return lang

def L(lang, ko, en):
    return ko if lang == "ko" else en
