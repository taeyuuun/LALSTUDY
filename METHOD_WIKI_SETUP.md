# Method Wiki setup

## 1. Apply files

Overwrite the project with the v0.5.0 patch.

Do NOT overwrite/remove your persistent:
- method_profiles.json
- figure_images.json
- license_metadata.json
- research_1000.db
- figure_cache/
- .streamlit/secrets.toml

## 2. Create the one new Supabase table

Supabase Dashboard -> SQL Editor -> New query

Run the full contents of:

`SUPABASE_METHOD_WIKI_MIGRATION.sql`

This creates:
- `method_encyclopedia`

No new secret is required.

## 3. Existing secrets reused

- OPENAI_API_KEY
- SUPABASE_URL
- SUPABASE_SECRET_KEY

## 4. Expected UI

Sidebar:
`🧬 Method DB · connected`

Method Wiki opens on a home/search screen instead of ATAC-seq.

A method with no DB description shows:
`✨ 설명 생성하고 DB에 저장`

After the first generation, the description is reused from Supabase.
