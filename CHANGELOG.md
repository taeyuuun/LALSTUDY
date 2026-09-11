# Changelog

## [0.5.1.1-beta] - 2026-09-12

### Method Wiki schema hotfix
- Fixed `KeyError: 'key_question_ko'` during method readability upgrade
- Added defensive `method_wiki_ai_v2.py`
- Normalizes partial/legacy AI outputs into complete structured `article_json`
- Removed fragile direct indexing of optional readability fields
- Added explicit `article_json` migration guidance

## [0.5.1-beta] - 2026-09-12

### Method Wiki readability
- Rebuilt method articles around an at-a-glance question + one-line answer
- Added compact quick facts for purpose / material / principle / output
- Replaced long prose walls with three concise bullet cards
- Added a one-line interpretation tip
- Added a local SVG Method Map for every method (no image API / no storage)
- Added optional representative OA corpus Figure display
- Added `article_json` for structured, reusable method knowledge
- Existing v0.5.0 entries remain readable and can be upgraded once

## [0.5.0.1-beta] - 2026-09-12

### Method Wiki import hotfix
- Moved Method Wiki generation helper into `method_wiki_ai.py`
- Removed the hard dependency on the newly-added `ai_router.generate_method_encyclopedia_entry` symbol
- Prevents mixed-version Streamlit deployments from crashing with ImportError
- No SQL, secret, or dependency changes

## [0.5.0-beta] - 2026-09-12

### Method Wiki
- Rebuilt Method Explorer as a search-first encyclopedia home
- Removed the default ATAC-seq selection
- Added name + alias search
- Added four faceted browse dimensions: purpose, material, principle, output
- Added a lean Supabase `method_encyclopedia` table for reusable method explanations
- Added one-time OpenAI generation + DB reuse for missing encyclopedia entries
- Kept paper/Figure relationships in the existing corpus instead of duplicating them in SQL
- Preserved paper filtering and Europe PMC Figure loading

## [0.4.4.2-beta] - 2026-09-12

### Auto local enrichment
- Automatically computes actual detected-method count for cached papers
- Automatically extracts Figure crops + source legends after a cached Core load
- Fixed a regression where Figure extractors received `canonical_key` instead of the required `paper_hash`
- Figure crops remain local and are never stored in Supabase Storage
- Surface local Figure-preparation errors instead of silently showing zero Figures

## [0.4.4.1-beta] - 2026-09-12

### Compact PDF metadata
- Replaced large Streamlit metric widgets in the PDF metadata row
- Fixed oversized `Detected methods / On demand` text
- Unified Pages / Detected methods / PDF size as compact text metadata

## [0.4.4-beta] - 2026-09-12

### Fast cache load
- Added exact-file alias fast lookup before PDF text extraction
- Unseen PDFs use only the first 2 pages for canonical identity detection
- Cached Core/Plus analyses display without extracting the complete PDF text
- Full PDF text is lazy-loaded only when an uncached AI stage is requested
- Figure crops remain local/on-demand and are not stored in Supabase Storage
- Cached Core can be used even if OpenAI is temporarily unavailable

## [0.4.3-beta] - 2026-09-12

### Canonical paper identity
- Replaced exact-file-only cache identity with DOI > PMCID > PMID > normalized title+year > SHA-256 fallback
- Added canonical paper entity and file-alias tables
- Different PDF files of the same DOI can now reuse paper-level AI results
- Supplementary documents are separated from main-article identities
- Individual Figure cache keys now include Figure label + normalized legend hash
- v0.4.2 exact-hash cache rows are promoted when possible

## [0.4.2-beta] - 2026-09-12

### Shared Paper Analysis Cache
- Added Supabase-backed cache for Core, Plus modules, and per-Figure AI analyses
- Exact PDF SHA-256 hash is used as the paper identity
- Cache hits skip the OpenAI call and reuse saved JSON results
- Stores AI output and metadata only; no PDF bytes, full paper text, or Figure image bytes are stored
- Added cache hit counters and server-only RLS configuration

## [0.4.1.3-beta] - 2026-09-12

### Figure workspace
- Reduced Figure display width by moving it into a compact left column
- Moved the original Figure legend to a right-side column
- Long legends now use an independent scroll area
- Figure AI analysis appears directly below the legend, enabling side-by-side comparison with the Figure

## [0.4.1.2-beta] - 2026-09-12

### OpenAI Usage UI
- Removed all estimated complimentary-token remaining balances
- Shows complimentary remaining tokens only when the official data-sharing incentive service tier is present
- Replaced the previous renderer with a new `openai_sidebar.py` module to prevent stale layout reuse
- Added an explicit `usage UI · v0.4.1.2` deployment marker
- Uses a single-column compact text layout with no `st.metric()` cards

## [0.4.1.1-beta] - 2026-09-12

### Sidebar hotfix
- Removed 3-column usage metrics from the narrow sidebar
- Replaced oversized metric values with compact single-column text
- Shortened complimentary-balance estimation messaging
- Added matching About patch note

## [0.4.1-beta] - 2026-09-12

### OpenAI Usage UI
- Replaced narrow three-column metrics with full-width token display
- Added progress indicator for daily complimentary-token allowance
- Changed service-tier-missing state from alarming warning to a clear official-usage / estimated-balance distinction
- Added concise milestone patch notes to About

## [0.4.0-beta] - 2026-09-12

### OpenAI-only architecture
- Removed Gemini runtime support and provider selection
- Removed `google-genai` dependency and `GEMINI_API_KEY` requirement
- Routed Core, Plus analyses, per-Figure analysis, and Knowledge Archive MISS generation through OpenAI only
- Kept independent per-Figure caching and native Figure + legend display
- Kept official OpenAI Organization Usage / Costs sync
- Sidebar now shows a single `OpenAI Usage` panel


## [0.3.4.2-beta] - 2026-09-12

### Hotfix
- AI Engine sidebar is now rendered explicitly on every page instead of indirectly through Knowledge Archive.
- Prevents mixed/partial deployments from hiding the provider selector and usage panel.


## [0.3.4.1-beta] - 2026-09-12

### Global AI provider
- Gemini / OpenAI choice persists for subsequent AI calls until changed
- Core, Plus analyses, per-Figure analysis, and Knowledge Archive MISS generation follow the selected provider
- No silent cross-provider fallback

### OpenAI official usage sync
- Added server-side OpenAI Organization Usage API sync using `OPENAI_ADMIN_KEY`
- Added official Organization Costs API sync for today's billed cost
- Data-sharing incentive tier is detected when exposed by the Usage API
- Complimentary remaining tokens use the configured daily allowance (default 2.5M for this account)
- 60-second cache plus manual refresh button
- Admin key is never displayed in the UI

All notable LALSTUDY updates will be recorded here.

## [0.3.3-beta] - 2026-09-11

### Figure AI
- Removed the all-Figures-at-once AI workflow from the main Figure UI
- Added one independent `Analyze this Figure` action below every Figure + source legend
- Added OpenAI Responses API + structured-output Figure analysis
- OpenAI model routing: `gpt-5.6-luna` → `gpt-5.6-terra`
- Gemini remains a per-Figure fallback provider
- Figure image + original legend + compact Core context are sent instead of the whole PDF
- Each Figure result is cached independently
- Added per-Figure provider/model badge and token usage when available
- Export JSON now includes independent `figure_analyses` records

All notable LALSTUDY updates will be recorded here.

## [0.3.2.1-beta] - 2026-09-11

### Knowledge Archive UX
- Moved the global Knowledge Archive into the persistent left sidebar
- Replaced free-form multi-term parsing with one-term-at-a-time addition
- Multi-word phrases such as `apoptotic stress` remain one concept
- Added visible concept queue with per-item removal and clear-all controls
- Archive search remains API-free
- Only explicit MISS generation calls Gemini, still batched into one request

All notable LALSTUDY updates will be recorded here.

## [0.3.2-beta] - 2026-09-11

### Learn a Paper
- Replaced upfront module-selection UI with one `Analyze paper` primary action
- Initial analysis now prepares Core + Figure crops + original Figure legends
- Main hierarchy reduced to Core and Figures
- Prerequisites, Experimental Strategy, and Critical Reading moved to optional Plus Analysis
- Figure images display at native crop size instead of stretching to container width
- Original PDF Figure legend is always displayed directly beneath each Figure
- Figure AI button runs crop preparation first when needed, then AI interpretation

All notable LALSTUDY updates will be recorded here.

## [0.3.1-beta] - 2026-09-11

### UX
- Moved Knowledge Archive out of the Learn a Paper body
- Added a top-right global Knowledge Archive popover to every page
- Archive query/results persist while navigating between pages
- Search itself never calls Gemini
- Archive MISS generation requires an explicit user click
- Multiple MISSes remain batched into one Gemini request

### Cleanup
- Removed duplicate Learn a Paper Archive UI/backend wiring
- Fixed stale About-page version display

All notable LALSTUDY updates will be recorded here.

## [0.3.0.1-beta] - 2026-09-11

### Fixed
- Supabase row-count errors no longer mark a healthy Archive connection as disconnected
- Streamlit Secrets access is more robust across runtimes
- Archive DB ping is now independent from informational concept count

### Diagnostics
- Added safe Archive connection diagnostics to the sidebar
- Shows presence of URL/key, key type, package status, client creation and DB/table ping
- Displays the exact Supabase error while never revealing secret values

All notable LALSTUDY updates will be recorded here.

## [0.3.0-beta] - 2026-09-11

### Knowledge Archive
- Added Supabase-backed persistent cross-user Knowledge Archive
- Added canonical concept normalization and alias table
- Added Archive HIT / MISS batch lookup
- Missing concepts are generated together in one Gemini request
- New reusable AI-generated knowledge is persisted automatically
- Added hit counts and quality states: AI_GENERATED / REVIEWED / CURATED
- Added `supabase_schema.sql` and `SUPABASE_SETUP.md`

### Security
- Uses backend-only `SUPABASE_SECRET_KEY`
- Archive tables use RLS with no public anon/authenticated policies

### UX
- Added Knowledge Archive concept input and HIT/MISS diagnostics
- Current text-input UI is the backend-validation step before Core drag-selection

All notable LALSTUDY updates will be recorded here.

## [0.2.6-beta] - 2026-09-11

### UX
- Added upfront AI-module selection
- Core Analysis is no longer mandatory
- Users may run only Figures, only Prerequisites, or any combination
- Cached modules are skipped automatically
- UI shows the maximum number of new API requests before execution

### Figure extraction
- Source PDF extractor v2 distinguishes article prose from numeric/axis Figure text
- Fixed Fig. 6 A/B being cut off in the XAF1–MT2A PNAS test PDF
- New source-PDF cache namespace prevents reuse of the old crop

All notable LALSTUDY updates will be recorded here.

## [0.2.5.6-beta] - 2026-09-11

### Architecture
- Original PDF caption-anchor extraction is now the primary Figure engine
- MinerU moved to fallback-only status
- Figure image extraction no longer requires an external API on normal text-layer PDFs

### Fixed
- Prevents persistent Fig. 6 / Fig. 7 misassociation by eliminating MinerU geometry from the primary path
- Anchored caption matching ignores in-text Figure references
- Direct extractor deduplicates one crop per main Figure number
- Source Figure cache versioned independently

### Validation
- Directly validated on the uploaded XAF1–MT2A PNAS paper
- Fig. 1 through Fig. 8 were recovered as distinct whole Figures

All notable LALSTUDY updates will be recorded here.

## [0.2.5.5-beta] - 2026-09-11

### Fixed
- Re-anchors MinerU Figure labels to the actual caption block in the original PDF
- Original PDF page number and caption bbox are now authoritative for Figure cropping
- Fixes isolated neighbor-Figure misassociation (for example Fig. 7 displaying Fig. 6 E/F)
- Versioned Figure state/cache to v6

### Extraction priority
1. Original-PDF caption anchor
2. MinerU caption anchor fallback
3. MinerU body bbox fallback

All notable LALSTUDY updates will be recorded here.

## [0.2.5.4-beta] - 2026-09-11

### Fixed
- Added hybrid recovery for multi-panel Figures when MinerU returns only a narrow panel body
- Uses real MinerU Figure captions as semantic anchors
- Crops the original PDF region immediately above the caption in the same journal column
- Detects multi-panel captions and compares Figure-body width against caption width
- Versioned Figure session/cache state to v5

### Extraction modes
- `mineru_body_bbox_union`
- `hybrid_caption_anchor_crop`
- existing PyMuPDF fallback

All notable LALSTUDY updates will be recorded here.

## [0.2.5.3-beta] - 2026-09-11

### Fixed
- MinerU online API `layout.json` is now recognized as the middle/intermediate layout artifact
- Supports `*_middle.json`, `middle.json`, `layout.json`, and `*layout.json`
- Missing-layout errors now list available JSON artifacts for debugging
- Versioned MinerU session cache to v4

All notable LALSTUDY updates will be recorded here.

## [0.2.5.2-beta] - 2026-09-11

### Fixed
- Replaced simplified MinerU content-list Figure geometry with `middle.json`
- Multi-panel Figure crops now union all image-body / line / span bboxes inside the Figure container
- Versioned the Streamlit MinerU session cache to prevent old panel-only results from being reused
- Added explicit Force Re-extract control

### Architecture
- MinerU provides semantic Figure grouping
- LALSTUDY renders the grouped body region directly from the original PDF
- `img_path` is no longer the Figure-boundary authority

All notable LALSTUDY updates will be recorded here.

## [0.2.5.1-beta] - 2026-09-11

### Fixed
- Multi-panel Figures no longer rely primarily on MinerU `img_path`
- MinerU Figure block `bbox` + `page_idx` are now used to render directly from the original PDF
- Prevents cases where only the last panel (for example panel H) is shown for an A-H Figure

### Fallback
- MinerU `img_path` is retained only when bbox-based PDF rendering is unavailable

All notable LALSTUDY updates will be recorded here.

## [0.2.5-beta] - 2026-09-11

### Added
- MinerU Open API SDK integration
- Precision VLM Figure extraction from local uploaded PDFs
- Server-side `MINERU_TOKEN`
- MinerU Figure cache by paper hash
- Figure extraction engine diagnostics
- PyMuPDF v2 fallback button

### Architecture
- LALSTUDY now consumes MinerU `content_list` image/chart records
- Figure identity is derived from actual caption text
- Body-text Figure references are not considered extraction targets
- AI interpretation remains separate from visual extraction

All notable LALSTUDY updates will be recorded here.

## [0.2.4.1-beta] - 2026-09-11

### Fixed
- Body paragraphs that merely mention `(Fig. N)` are no longer detected as Figure captions
- Main Figures are deduplicated by canonical Figure label
- Single-column Figures no longer crop the opposite article-text column
- Old v1 Figure extraction cache is bypassed automatically

### Improved
- Caption-column-aware crop bounds
- Nearby prose boundary detection
- Embedded raster-image bounding-box refinement
- Reduced duplicate Figure display in the Learn a Paper UI

All notable LALSTUDY updates will be recorded here.

## [0.2.4-beta] - 2026-09-11

### Added
- Figure in Study: local extraction of study figures from the uploaded PDF
- `figure_in_study.py` helper module using PyMuPDF
- Figure crop cache under `figure_cache/study_figures/<paper_hash>/`
- Figure gallery of extracted study figures inside Learn a Paper

### Changed
- Figure-by-Figure now shows the actual extracted Figure image together with AI interpretation
- Figure images are obtained locally and do not require extra AI API calls
- Added PyMuPDF dependency

### Known limitations
- Figure extraction is heuristic and may be imperfect for complex journal layouts
- Matching between extracted crops and AI figure labels is approximate

All notable LALSTUDY updates will be recorded here.

## [0.2.3-beta] - 2026-09-11

### Architecture
- Replaced one giant Deep Study request with staged / lazy analysis
- Core Analysis now generates only Overview + Logic Map
- Prerequisites, Experiments, Figures, and Critical Reading are generated on demand
- Each module is cached independently in Streamlit session state
- Failed modules no longer invalidate successful modules

### Reliability / cost
- Text-oriented stages use extracted paper text instead of re-sending the PDF
- Only Figure analysis sends the PDF as multimodal input
- Reduced retry count per model to avoid long failure loops
- Text fallback: Gemini 3.8 Flash → 3.5 Flash → 3.5 Flash-Lite
- Figure fallback: Gemini 3.8 Flash → 3.5 Flash
- Low thinking level is used to reduce latency and output overhead

### UX
- First useful result arrives after Core Analysis
- Four Deep Study module status cards show what has and has not been generated
- Korean / English switching remains instant for generated modules
- Active PDF persists across pages
- Partial Learning Map JSON can be exported at any time

All notable LALSTUDY updates will be recorded here.

## [0.2.2-beta] - 2026-09-10

### Added
- Server-side Gemini API key shared by public users
- Automatic model fallback: Gemini 3.8 Flash → 3.7 Flash → 3.6 Flash
- Automatic retry with exponential backoff for transient 429/5xx errors

### Changed
- Removed user-facing API-key input
- API key is read only from Streamlit Secrets or the server environment

### Operational note
Public users consume the owner's Gemini quota/cost. Configure quota and billing safeguards.

All notable LALSTUDY updates will be recorded here.

## [0.2.1-beta] - 2026-09-10

### Fixed
- Active uploaded paper now survives navigation away from Learn a Paper
- Language switching no longer creates a separate PDF-analysis cache
- Gemini API key remains independent of language and active-paper state

### Changed
- A single AI request now produces both Korean and English learning maps
- Korean output uses an English-first scientific terminology policy
- Specialized biological terms should remain in their conventional English form where practical
- Added explicit Active Paper / Clear Paper controls

All notable LALSTUDY updates will be recorded here.

## [0.2.0-beta] - 2026-09-10

### Added
- AI Deep Study for uploaded scientific PDFs
- Gemini native PDF analysis
- Structured paper logic map
- Learner-depth selector
- AI-generated prerequisite dependency explanations
- Experiment-level What / Why / Readout / inference cards
- Figure- and panel-level interpretation
- Critical-reading module
- Reviewer-question generation
- Ordered learning path
- Direct method deep links into Method Explorer / Figure Explorer
- Korean/English AI output generated directly in the selected language
- Session-level AI result reuse to avoid repeated API calls
- Gemini secret / environment / session-key support

### Design changes
- AI mode separates general background knowledge from paper-specific evidence.
- Rule-based ontology detection is retained as an API-free Quick Scan.
- Translation services are no longer required for AI-generated Korean content.

### Known limitations
- AI interpretation can still contain errors and must be checked against the paper.
- Inline Gemini PDF mode is limited to 50 MB.
- Method ontology linking is approximate for names not already in the alias table.
- API availability and quotas depend on the user's Gemini project.

All notable LALSTUDY updates will be recorded here.

## [0.1.1-beta]

### Improved bilingual learning output
- Korean mode now translates dynamically extracted paper content
- Paper at a Glance is displayed in Korean
- Why This Study? extraction is displayed in Korean
- Abstract translation is shown while preserving the original
- Figure auto-extracted summaries are displayed in Korean
- In-paper concept context is translated with the English source preserved
- Scientific method/concept terms are protected where possible during translation
 - 2026-09-10

### Added
- Global Korean / English language selector
- Bilingual primary UI across the integrated app
- Bilingual prerequisite explanations in Learn a Paper
- Bilingual experimental-method purpose explanations
- Original source-paper text remains unchanged

## [0.1.0-beta] - 2026-09-10

### Added
- Integrated Streamlit multipage application
- Learn a Paper beta
- Prerequisite knowledge cards
- Experimental method detection and ontology linkage
- Method Explorer
- Figure Explorer
- Panel-aware caption interpretation
- Automatic panel crop beta
- Article license metadata support
- Conservative Figure rights handling
- Version History page

### Known limitations
- Learn a Paper uses rule-based / extractive analysis
- Figure extraction and panel splitting are heuristic
- Method matching can contain false positives
- Current corpus is a keyword-retrieved Nature Communications OA subset


### v0.2.0-beta UX hotfix
- Removed Quick Scan from the main Learn a Paper interface
- Moved Gemini API-key input into the main page
- Made the AI Deep Study action the single primary workflow
- Added explicit button activation guidance


### API key state hotfix
- Fixed Gemini API key disappearing after pressing the analysis button
- API key input now uses one stable Streamlit session-state key
- The key widget remains mounted across reruns
- Added a clear-key control for session-entered keys


### Gemini model hotfix
- Updated default AI model from `gemini-2.5-flash` to `gemini-3.6-flash`
- Keeps the current GenerateContent-based structured PDF analysis pipeline
