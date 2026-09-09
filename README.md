# 🧬 LALSTUDY

> Learn a paper, understand the experiment, and keep learning without losing context.

**Current version: `v0.1.0-beta`**

LALSTUDY is an experimental scientific-paper learning platform that connects two workflows:

1. **Learn a Paper** — turn a PDF into a structured learning path.
2. **Explore Experiments** — move from experimental methods to real papers, figures, and panels.

## Why LALSTUDY?

General-purpose AI can summarize a paper, but students often still need to leave the conversation to answer questions such as:

- What prerequisite concepts am I missing?
- Why did the authors choose this experiment?
- What exactly does this Figure measure?
- Where can I see other real examples of this experimental method?

LALSTUDY is designed around those links.

## v0.1.0-beta features

### 📄 Learn a Paper
- PDF upload
- Paper at a Glance
- Why This Study?
- Prerequisite Knowledge
- Experimental Strategy
- Figure-by-Figure Story
- Recommended next learning steps

### 🧬 Method Explorer
- Canonical experimental-method ontology
- Alias / parent / subtype relationships
- Paper ↔ Method links
- Related Figure captions

### 🖼 Figure Explorer
- Figure Gallery
- Method-linked real examples
- Panel-aware caption parsing
- Study-oriented Figure interpretation

### ✂️ Panel Crop Beta
- Caption-based A/B/C/D detection
- Whitespace/layout-based automatic crop candidates
- Regular-grid fallback

### ⚖️ License-aware display
- Article-level Creative Commons metadata
- Conservative Figure-rights exception flags
- Local on-demand Figure cache

## Corpus note

The current corpus consists of approximately 1,000 **Nature Communications open-access papers matching an immunology-related keyword query**.

It is **not**:
- all immunology literature,
- all Nature Communications papers,
- or a *Nature Immunology* corpus.

Automated prevalence counts should therefore be interpreted as corpus-level estimates, not scientific prevalence.

## Local run

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run:

```bash
python -m streamlit run app.py
```

## Required generated data

For the current beta, place these files beside `app.py`:

```text
method_profiles.json
figure_images.json
license_metadata.json
research_1000.db
```

The local `figure_cache/` directory is intentionally ignored by Git.

## Project structure

```text
LALSTUDY/
├─ app.py
├─ pages/
│  ├─ 1_Learn_a_Paper.py
│  ├─ 2_Method_Explorer.py
│  ├─ 3_Figure_Explorer.py
│  ├─ 4_Panel_Crop_Beta.py
│  └─ 5_About.py
├─ data/
│  └─ README.md
├─ .streamlit/
│  └─ config.toml
├─ requirements.txt
├─ CHANGELOG.md
├─ .gitignore
└─ LICENSE
```

## Current limitations

LALSTUDY `v0.1.0-beta` is intentionally an MVP.

- Learn a Paper currently uses rule-based / extractive analysis.
- PDF parsing depends on the document text layer.
- Method matching can contain false positives.
- Figure ↔ Method coverage is incomplete relative to Paper ↔ Method coverage.
- Panel segmentation is heuristic.
- Automated rights classification is conservative and is not legal advice.

## Roadmap

### v0.2
- Generative-AI explanation layer
- Concept dependency graph
- Direct Learn-a-Paper ↔ Method/Figure Explorer linking
- Better paper-logic reconstruction
- Compound scientific search
- Improved Figure panel detection

### Later
- Personal knowledge profiles
- Learning history
- User corrections / QA feedback
- Multi-paper comparison

## Version history

See [`CHANGELOG.md`](CHANGELOG.md).

## License

Code is released under the MIT License.  
Research articles and figures remain subject to their respective source licenses and third-party rights.
