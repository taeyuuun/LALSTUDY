# v0.5.1 Method Wiki readability setup

## Required SQL

After the v0.5.0 Method Wiki migration, run:

`SUPABASE_METHOD_WIKI_READABILITY_MIGRATION.sql`

It adds only one column:

`method_encyclopedia.article_json jsonb`

Existing rows are preserved.

## Existing entries

Existing v0.5.0 descriptions render immediately in the new layout.
They are split conservatively into readable bullet cards.

For best quality, open the small expander:

`✨ 이 설명을 새 가독성 포맷으로 업그레이드`

and generate the structured article once.

## Images

Every method always gets a lightweight local SVG Method Map.
No image API and no Supabase Storage are used.

If the method has a corpus-linked Figure:
- cached Figure -> can be viewed immediately
- uncached Figure -> one button loads it from Europe PMC into the existing local cache

No new secret is required.
