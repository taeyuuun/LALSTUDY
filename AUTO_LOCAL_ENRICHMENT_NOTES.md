# v0.4.4.2 Auto Local Enrichment

Behavior for a cached paper:

1. Supabase Core/Plus analysis loads immediately.
2. LALSTUDY parses the currently uploaded PDF locally.
3. Actual method count is calculated.
4. Figure crops and original legends are extracted locally.
5. The page reruns with the complete Main Analysis.

No OpenAI call is made for cached Core data.
No Figure image is uploaded to Supabase Storage.

Important fix:
v0.4.3/v0.4.4 accidentally passed `canonical_key=` into local Figure
extractors whose API requires `paper_hash=`. That failure was swallowed by
fallback handling and could leave `Figures · 0`. v0.4.4.2 fixes this.
