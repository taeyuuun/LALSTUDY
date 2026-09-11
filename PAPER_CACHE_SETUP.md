# Shared Paper Analysis Cache setup

1. Open Supabase Dashboard.
2. Open SQL Editor -> New query.
3. Copy all contents of `SUPABASE_PAPER_CACHE_MIGRATION.sql`.
4. Run it once.
5. No new secrets are required. Existing `SUPABASE_URL` and `SUPABASE_SECRET_KEY` are reused.
6. Redeploy/reboot LALSTUDY.

When connected, the Learn a Paper sidebar shows:

`☁️ Shared analysis cache · connected`

A reused AI result shows:

`AI: OpenAI · <model> · ☁️ cached`
