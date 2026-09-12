# v0.5.2.2 Method Wiki readability

`SUPABASE_METHOD_WIKI_READABILITY_MIGRATION.sql` is NO LONGER REQUIRED.

LALSTUDY now stores readable Method Wiki content using only the original
`method_encyclopedia` columns created by `SUPABASE_METHOD_WIKI_MIGRATION.sql`.

Existing columns reused:
- summary_ko / summary_en
- principle_ko / principle_en
- best_for_ko / best_for_en
- limitations_ko / limitations_en
- facets
- quality_status
- source_model

The UI reconstructs the readable cards from those values.

If you already created `article_json`, it may remain in Supabase; v0.5.2.2 simply
does not depend on it.
