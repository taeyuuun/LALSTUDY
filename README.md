# 🧬 LALSTUDY

> Learn a paper, understand the experiment, and keep learning without losing context.

**Current version: `v0.2.2-beta`**

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

## v0.1.1-beta features

### 🌐 Korean / English support
- Global language selector shared across pages
- Bilingual primary UI
- Bilingual prerequisite and method-purpose explanations
- Original paper title/abstract/caption preserved as source text

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

LALSTUDY `v0.1.1-beta` is intentionally an MVP.

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


### Dynamic Korean paper output

When Korean mode is selected, LALSTUDY translates dynamically extracted paper content such as:
- Paper at a Glance
- Why This Study?
- Abstract
- Figure auto-extracted summaries
- In-paper concept context

The English source is retained for verification. The beta currently uses `deep-translator` for machine translation and can fall back to the original source if translation is unavailable.


### v0.2 UX adjustment

Quick Scan is removed from the primary Learn a Paper workflow.  
The page now focuses on one path:

**PDF upload → API key → AI Deep Study → linked Method/Figure learning**

The API-key input and primary analysis button are displayed directly in the main content area.


## v0.2.1 state & bilingual update

The active paper is now a session-level object rather than a page-local upload widget.

```text
Active Paper
├─ PDF bytes
├─ filename / hash
├─ bilingual AI analysis
└─ current learning preferences
```

This means users can move from `Learn a Paper` to `Method Explorer` or
`Figure Explorer` and return without uploading the PDF again.

One Deep Study call generates both:
- Korean learning output
- English learning output

Switching the UI language only changes which stored view is rendered.

Korean mode follows an **English-first scientific terminology** style:
Korean explanatory grammar is mixed with conventional English terms such as
`lysosome`, `autophagy`, `Flow cytometry`, `phosphorylation`, and gene/protein names.

## v0.2.2 server-side AI

All visitors use the deployment owner's server-side `GEMINI_API_KEY`.

The key is stored in Streamlit Cloud Secrets and is never shown in the UI.

Automatic model order:

`gemini-3.8-flash → gemini-3.7-flash → gemini-3.6-flash`

Transient 429/5xx errors are retried before fallback.

**Important:** a public app can consume the owner's API quota and billing budget.
