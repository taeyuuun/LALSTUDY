import streamlit as st

APP_VERSION = "v0.1.0-beta"

st.set_page_config(
    page_title="LALSTUDY · About",
    page_icon="ℹ️",
    layout="wide",
)

st.title("ℹ️ About LALSTUDY")
st.caption(f"Current version: {APP_VERSION}")

st.markdown("""
**LALSTUDY** is an experimental scientific-paper learning platform.

The project is designed around one question:

> How can a student move from *seeing a paper* to *understanding the logic, background concepts, experimental methods, and figures* without repeatedly leaving the learning context?

The current corpus-based features use approximately 1,000 **Nature Communications open-access papers matching an immunology-related search query**.  
This is not a complete immunology corpus and is not the journal *Nature Immunology*.
""")

st.header("Version History")

with st.container(border=True):
    st.subheader("v0.1.0-beta")
    st.markdown("""
- Initial LALSTUDY integrated beta
- Learn a Paper
- Prerequisite biology glossary
- Method ontology linkage
- Paper ↔ Method exploration
- Figure Gallery
- Figure Study Card
- Panel-aware caption parsing
- Experimental panel crop beta
- Article-level Creative Commons metadata
- Conservative Figure rights flagging
""")

st.header("Roadmap")

st.markdown("""
### v0.2 candidates
- Generative-AI explanation layer
- Better research-question / conclusion reconstruction
- Concept dependency graph
- `Learn a Paper → Method Explorer` deep linking
- Combined queries such as `Flow cytometry + Treg + FOXP3`
- Better Figure / panel segmentation

### Later
- Personal knowledge profile
- Learning history
- "I already know this" concept filtering
- User corrections / QA feedback
- Multi-paper comparison
""")

st.header("Beta limitations")

st.markdown("""
- Automated method detection can produce false positives.
- Figure ↔ Method coverage is less complete than Paper ↔ Method coverage.
- Panel parsing is heuristic and can fail on complex layouts.
- Learn a Paper v0.1 uses extractive / rule-based analysis rather than a full LLM.
- PDF extraction depends on an accessible text layer.
- Rights metadata is a conservative automated aid, not legal advice.
""")

st.divider()
st.page_link("app.py", label="← Home", icon="🏠")
