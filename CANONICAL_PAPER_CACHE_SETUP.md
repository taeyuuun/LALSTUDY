# Canonical Paper Cache setup

1. Open Supabase Dashboard.
2. Go to SQL Editor -> New query.
3. Copy all contents of `SUPABASE_CANONICAL_PAPER_CACHE_MIGRATION.sql`.
4. Run it once.
5. No new secrets are required.
6. Existing `SUPABASE_URL` and `SUPABASE_SECRET_KEY` are reused.
7. Deploy/reboot LALSTUDY.

Identity priority:
- DOI
- PMCID
- PMID
- normalized PDF metadata title + publication year
- exact PDF SHA-256 fallback

The app shows the detected identity below the active paper name.

When the same article is uploaded in a different PDF format but resolves to the
same DOI/PMCID/PMID, paper-level analysis can be reused.

Figure results additionally require the same Figure label + legend hash.
