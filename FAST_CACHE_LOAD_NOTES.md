# v0.4.4 Fast Cache Load

No new Supabase tables, secrets, or dependencies are required beyond v0.4.3.

The existing v0.4.3 tables are reused:
- lalstudy_papers_v2
- paper_file_aliases_v2
- paper_analysis_cache_v2

Behavior:
- Exact same PDF seen before: SHA-256 alias lookup -> cached analysis immediately.
- Different PDF of the same paper: inspect only the first 2 pages -> canonical DOI/PMCID/PMID -> cached analysis.
- Full PDF text extraction happens only when an uncached AI stage is requested.
- Figure images are not saved to Supabase Storage. Figure crop/legend extraction remains local/on-demand.

Expected cached-paper UX:
- `⚡ 저장된 Core Analysis를 불러왔습니다...`
- AI badge includes `☁️ cached`
