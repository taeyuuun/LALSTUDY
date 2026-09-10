# Changelog

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
