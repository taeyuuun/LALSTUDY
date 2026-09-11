# 🧬 LALSTUDY

> Learn a paper, understand the experiment, and keep learning without losing context.

**Current version: `v0.4.1.2-beta`**

## v0.4.0 — OpenAI-only architecture

LALSTUDY now uses one AI provider only: **OpenAI**. Gemini runtime support, provider switching, and `google-genai` were removed.

- Core / Plus analyses: OpenAI
- Per-Figure analysis: OpenAI
- Knowledge Archive MISS generation: OpenAI
- Official organization usage/cost sync: OpenAI Admin API
- Default model chain: `gpt-5.6-luna → gpt-5.6-terra`

Required server secrets:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_ADMIN_KEY = "sk-admin-..."  # optional, needed for official usage sync
OPENAI_COMPLIMENTARY_DAILY_TOKENS = "2500000"
```


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

All visitors use the deployment owner's server-side `OPENAI_API_KEY`.

The key is stored in Streamlit Cloud Secrets and is never shown in the UI.

Automatic model order:

`gpt-5.6-luna → gpt-5.6-terra`

Transient 429/5xx errors are retried before fallback.

**Important:** a public app can consume the owner's API quota and billing budget.


## v0.2.3 — staged / lazy AI analysis

The previous Deep Study architecture requested the whole learning map in one
large multimodal structured-output call.

v0.2.3 splits the workflow into independently cached stages:

```text
Stage 1: Core
  ├─ Overview
  └─ Logic Map

Stage 2: Prerequisites        (on demand)
Stage 3: Experiments          (on demand)
Stage 4: Figures              (on demand; PDF multimodal input)
Stage 5: Critical + Learn Next(on demand)
```

Benefits:
- smaller structured outputs
- much faster first useful result
- fewer wasted calls for sections a user never opens
- a failure in one stage does not erase successful stages
- language switching uses the bilingual result already stored for that stage
- active paper state still survives multipage navigation

Text-oriented stages use extracted paper text rather than repeatedly sending
the full PDF. Only Figure analysis sends the actual PDF again.

Default fallback pools:

```text
Text stages:
gpt-5.6-luna → gpt-5.6-terra

Figure stage:
gpt-5.6-luna → gpt-5.6-terra
```


## v0.2.4 — Figure in Study

The Figures tab now combines **AI interpretation** with the **actual figure image extracted from the uploaded PDF**.

### What it does
- detects caption blocks such as `Fig. 1`, `Figure 2`
- crops likely figure regions from the PDF locally using PyMuPDF
- caches them under `figure_cache/study_figures/<paper_hash>/`
- tries to match AI-analyzed figure labels to the extracted figure crops

### Why this matters
Users no longer need to jump back to the paper PDF just to see the referenced Figure.

### Current limitation
Figure extraction is heuristic. It works best when figure captions are clearly detectable and
the figure appears immediately above its caption. Complex layouts may produce imperfect crops.


## v0.2.4.1 — Figure extractor v2

The first Figure-in-Study extractor matched any text block containing a Figure
reference. This caused Results paragraphs such as `(Fig. 2A)` to be mistaken
for captions and could create duplicate or text-heavy crops.

Extractor v2:
- requires the text block itself to start with `Fig. N` / `Figure N`
- deduplicates one crop per canonical main Figure
- uses the caption's column width rather than the whole page
- uses nearby body prose as an upper crop boundary
- uses embedded raster-image geometry as an additional bound when available
- writes to `figure_cache/study_figures_v2/`, so old bad crops are not reused

The extraction remains deterministic and does not require an additional AI call.


## v0.2.5 — MinerU Precision Figure benchmark

LALSTUDY now supports a MinerU-first Figure extraction path.

```text
Uploaded PDF
↓
MinerU Precision / VLM
↓
structured image/chart block
├─ img_path
├─ image_caption
├─ page_idx
└─ bbox
↓
canonical Fig. N matching
↓
Figure image + source caption + OpenAI interpretation
```

Server configuration:

```toml
MINERU_TOKEN = "..."
```

The token is server-side and should never be committed to Git.

The existing PyMuPDF extractor remains available as a fallback while MinerU is
benchmarked against real scientific PDFs.


## v0.2.5.1 — MinerU bbox PDF rendering

MinerU `img_path` is no longer the primary visual source for Figure-in-Study.

For multi-panel scientific Figures, a simplified MinerU image record can resolve
to only one underlying image span. LALSTUDY now uses MinerU's Figure-level
`bbox` and `page_idx` to render the corresponding rectangle directly from the
original PDF at high resolution.

```text
MinerU
  └─ Figure content block bbox + page_idx
             ↓
Original uploaded PDF
             ↓
PyMuPDF high-resolution bbox render
             ↓
whole Figure crop
```

`img_path` remains only as a fallback when bbox rendering is unavailable.


## v0.2.5.2 — MinerU middle.json Figure containers

The previous MinerU integration still depended on simplified `content_list`
geometry. Multi-panel scientific Figures can be flattened in that representation.

v0.2.5.2 reads MinerU's richer `middle.json` hierarchy:

```text
image / chart container
├─ image_body / chart_body
│  ├─ line
│  │  └─ span bbox
│  └─ ...
├─ image_caption
└─ image_footnote
```

LALSTUDY unions all body / line / span bounding boxes inside the same Figure
container and renders that full region from the original uploaded PDF.

The Streamlit session cache key is versioned (`v3`) and a Force Re-extract
button is available so an old panel-only crop cannot be silently reused.


## v0.2.5.3 — MinerU layout.json compatibility

MinerU Precision API packages can expose the intermediate layout structure as
`layout.json` rather than `<stem>_middle.json`.

LALSTUDY now accepts all of:

```text
*_middle.json
middle.json
layout.json
*layout.json
```

as the MinerU intermediate layout artifact.

If none are found, the UI error now reports which JSON files were actually
present in the extracted MinerU result, making future API-format changes easier
to debug.


## v0.2.5.4 — Hybrid caption-anchor Figure recovery

Some scientific PDFs are parsed by MinerU with only one image-body span from a
multi-panel Figure. When the Figure caption clearly refers to multiple panels
but the detected visual body is much narrower than the caption, LALSTUDY now
switches to a hybrid recovery path:

```text
MinerU semantic caption detection
              ↓
real Fig. N caption bbox
              ↓
original PDF page geometry
              ↓
same-column visual region immediately above caption
              ↓
whole-Figure crop
```

MinerU therefore decides *which block is the true Figure caption*, while
PyMuPDF renders the actual page region. This avoids relying on incomplete
panel-level image objects.


## v0.2.5.5 — Original-PDF caption re-anchoring

MinerU is now used primarily for semantic Figure identity.

For every `Fig. N`, LALSTUDY searches the original uploaded PDF text layer for
the actual caption block beginning with `Fig. N` / `Figure N`.

That original source page and bbox become the geometric authority:

```text
MinerU semantic Figure label
           ↓
search original PDF for real "Fig. N." caption
           ↓
actual PDF page + caption bbox
           ↓
same-column visual region above caption
           ↓
whole Figure crop
```

This removes MinerU page-index / coordinate ambiguity and fixes neighbor-Figure
misassociation such as a Fig. 7 card showing a Fig. 6 panel.


## v0.2.5.6 — Source PDF becomes the Figure authority

After repeated MinerU multi-panel edge cases, LALSTUDY now uses the original
uploaded PDF as the primary Figure extraction authority.

```text
Original PDF
↓
text block STARTING with "Fig. N." / "Figure N"
↓
true source page + source caption bbox
↓
same-column region immediately above caption
↓
whole Figure crop
```

This path:
- uses no AI/API calls
- ignores body references such as `(Fig. 7A)`
- deduplicates by Figure number
- preserves the uploaded PDF's actual page geometry

MinerU remains available only as a fallback for PDFs with poor/no usable text
layers or nonstandard caption structures.


## v0.2.6 — Selective AI Analysis

Core Analysis is no longer a mandatory gateway.

After uploading a PDF, users choose exactly which AI modules should run:

```text
☐ Core: Overview + Logic Map
☐ Prerequisites
☐ Experiments
☐ Figures
☐ Critical Reading + Learn Next
              ↓
       Run selected analyses
```

Each selected module is an independent API request and existing cached results
are reused. Selecting only `Figures` therefore makes **zero Core API calls**.

### Figure crop fix

Source-PDF extractor v2 now requires a meaningful density of alphabetic words
before a text block can be treated as article prose. Numeric axis/lane-label
blocks inside scientific Figures no longer push the crop boundary downward.

This fixes the uploaded PNAS test case where Fig. 6 panels A/B were previously
cut off while C-F remained visible.


## v0.3.0 — Shared Knowledge Archive

LALSTUDY now has a persistent shared scientific knowledge layer backed by
Supabase Postgres.

```text
selected concepts
       ↓
Supabase batch lookup
 ┌─────┴─────┐
 HIT        MISS
 ↓            ↓
instant     batch OpenAI request
              ↓
       reusable explanation
              ↓
           archive
```

A later user requesting the same canonical concept or an archived alias receives
an Archive HIT without an OpenAI request.

The archive stores reusable general scientific knowledge only. Paper-specific
findings remain outside the shared concept record.

See `SUPABASE_SETUP.md` and `supabase_schema.sql`.

### Server secrets

```toml
SUPABASE_URL = "https://..."
SUPABASE_SECRET_KEY = "sb_secret_..."
```

The secret key must remain server-side.


## v0.3.0.1 — Supabase connection diagnostics

Archive connection health is now based only on a minimal
`knowledge_concepts` table ping. Concept counting is informational and cannot
mark a healthy connection as disconnected.

When the Archive is disconnected, the sidebar exposes a safe diagnostic panel
showing:

- whether `SUPABASE_URL` exists
- whether `SUPABASE_SECRET_KEY` exists
- key type/prefix category (never the key itself)
- whether the Python client library loaded
- whether a client was created
- whether the `knowledge_concepts` table ping succeeded
- the exact Supabase error message


## v0.3.1 — Global Knowledge Archive widget

Knowledge Archive is no longer a large section inside `Learn a Paper`.

It is now available from every LALSTUDY page as a compact top-right popover:

```text
                              [🧠 Knowledge Archive]
                                      ↓
                              Archive-only search
                                      ↓
                         HIT → immediate, zero OpenAI
                         MISS → explicit AI generation
```

Archive search never triggers OpenAI automatically. Missing concepts are sent
to OpenAI only when the user explicitly clicks `Generate MISSes + archive`,
and all current MISSes are batched into one request.

The query and search state live in global Streamlit session state, so they
remain available while navigating between LALSTUDY pages.


## v0.3.2 — Learn a Paper hierarchy

`Learn a Paper` now has one clear primary flow:

```text
Upload PDF
↓
Analyze paper
↓
Core Analysis
+ Figure crop
+ original Figure legend
↓
MAIN
- Core
- Figures
↓
PLUS
- Prerequisites
- Experimental Strategy
- Critical Reading
```

The initial `Analyze paper` action uses OpenAI for Core Analysis.
Figure images and source legends are extracted from the source PDF without
an AI call whenever possible.

Figure images are no longer stretched to the full Streamlit container width.
The original source legend is shown immediately below each Figure.

AI Figure interpretation remains a Main feature. Its single button ensures
Figure crops exist first, then runs Figure AI analysis sequentially.

Prerequisites, Experimental Strategy, and Critical Reading are visually and
functionally demoted to optional Plus modules.


## v0.3.2.1 — Sidebar Archive queue

Knowledge Archive is now a persistent left-sidebar tool on every page.

The user adds exactly one scientific term or phrase at a time:

```text
[ apoptotic stress ]
[ + Add term ]

Queued:
- apoptotic stress
- p53 conformational change

[ Search Archive ]
```

Multi-word concepts are never split automatically. `apoptotic stress` remains
one query unless the user explicitly adds `apoptotic` and `stress` separately.

Search remains API-free. Archive MISSes can still be generated together in one
explicit OpenAI batch request.


## v0.3.3 — Independent Figure AI + OpenAI primary

Figure interpretation is no longer one large whole-PDF AI request.
Each extracted Figure now has its own `Analyze this Figure` button directly
below its source image and original Figure legend.

Per-Figure request payload:

```text
single Figure crop
+ original Figure legend
+ compact Core context
```

The only AI provider is OpenAI (`gpt-5.6-luna`, then `gpt-5.6-terra`). There is no cross-provider fallback. Every Figure is cached independently, so one failure does not erase any successful Figure analyses.

Required server secret for OpenAI Figure analysis:

```toml
OPENAI_API_KEY = "sk-..."
```

Never commit the real key. `.streamlit/secrets.toml` remains gitignored.


## v0.3.4.1 — Official OpenAI usage sync (historical)

- Historical dual-provider selector before v0.4.0
- Per-Figure analysis remains independent per Figure
- OpenAI Organization Usage + Costs official sync with `OPENAI_ADMIN_KEY`
- Complimentary token remaining display when the data-sharing incentive tier is visible
- Clearly labelled estimate if the incentive tier is not exposed

See `OPENAI_USAGE_SETUP.md`.


## v0.4.1 — Usage UI polish

- Full-width OpenAI token balance in the sidebar
- No more truncated large numbers
- Clear distinction between official usage and estimated complimentary balance
- Concise milestone patch notes in About


## v0.4.1.1 — Compact Usage UI

The OpenAI Usage sidebar now uses a single-column compact layout so token counts no longer truncate on narrow sidebars.


## v0.4.1.2 — Official-only Usage UI

The sidebar no longer displays estimated complimentary-token balances. It always shows official organization usage/costs when available, and only shows complimentary remaining tokens when the OpenAI Usage API explicitly reports the data-sharing incentive service tier.


## v0.4.1.3 — Compact Figure Workspace

Learn a Paper now renders each Figure in a two-column workspace:
the Figure stays compact on the left, while the source legend and Figure AI
interpretation remain on the right. Long legends scroll independently so the
analysis starts closer to the Figure.


## v0.4.2 — Shared Paper Analysis Cache

AI analysis results are now reusable across sessions/users when the exact same
PDF is uploaded. LALSTUDY uses the PDF SHA-256 hash as the cache key.

Cached stages:
- Core Analysis
- Prerequisites
- Experimental Strategy
- Critical Reading
- Individual Figure AI analyses

The Supabase cache stores structured AI output and model metadata only.
It does not store uploaded PDF bytes, extracted full paper text, or Figure images.

Run `SUPABASE_PAPER_CACHE_MIGRATION.sql` once before using this feature.


## v0.4.3 — Canonical Paper Identity

Paper-level cache identity now follows:

`DOI > PMCID > PMID > normalized title + year > exact PDF SHA-256`

This means a publisher PDF and author manuscript can reuse the same paper-level
analysis when they expose the same stable identifier.

Individual Figure cache identity is intentionally stricter:
`canonical paper key + Figure label + normalized Figure legend hash`.

Supplementary documents are separated from main-article cache identities.

Run `SUPABASE_CANONICAL_PAPER_CACHE_MIGRATION.sql` once before using v0.4.3.


## v0.4.4 — Fast Cache Load

Saved analyses now load before full-PDF text extraction.

Fast path:
1. SHA-256 lookup in `paper_file_aliases_v2`
2. Resolve canonical paper identity
3. Load cached Core / Plus JSON
4. Skip full PDF parsing

For unseen files, only the first two pages are inspected to resolve DOI/PMCID/PMID.
The complete PDF text is loaded only when a missing AI stage is explicitly requested.

Figure crops are intentionally NOT stored in Supabase Storage. They continue to
be generated locally/on-demand from the uploaded PDF.
