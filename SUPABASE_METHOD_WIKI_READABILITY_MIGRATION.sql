-- ============================================================
-- LALSTUDY v0.5.1
-- Method Wiki readability upgrade
--
-- Run ONCE in Supabase SQL Editor AFTER the v0.5.0 Method Wiki migration.
-- Existing method descriptions are preserved.
-- ============================================================

alter table public.method_encyclopedia
    add column if not exists article_json jsonb
    not null default '{}'::jsonb;

create index if not exists idx_method_encyclopedia_quality
    on public.method_encyclopedia (quality_status);
