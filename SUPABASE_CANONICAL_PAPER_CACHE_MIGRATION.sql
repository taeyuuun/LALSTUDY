-- ============================================================
-- LALSTUDY v0.4.3
-- Canonical Paper Identity + Shared Analysis Cache V2
--
-- Run ONCE in Supabase SQL Editor.
--
-- Identity hierarchy:
--   DOI
--   > PMCID
--   > PMID
--   > normalized title + publication year
--   > exact PDF SHA-256
--
-- Same paper in a publisher PDF / author manuscript can therefore share
-- paper-level AI results when they expose the same stable identifier.
--
-- Supplementary documents are intentionally separated from the main article.
-- ============================================================

create extension if not exists pgcrypto;


create table if not exists public.lalstudy_papers_v2 (
    id uuid primary key default gen_random_uuid(),

    canonical_key text not null unique,

    identity_type text not null,
    identity_value text not null default '',
    confidence text not null default '',
    document_kind text not null default 'main',

    doi text not null default '',
    pmcid text not null default '',
    pmid text not null default '',

    title text not null default '',
    normalized_title text not null default '',
    publication_year integer,

    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now()
);


create table if not exists public.paper_file_aliases_v2 (
    id uuid primary key default gen_random_uuid(),

    file_hash text not null unique,

    canonical_key text not null
        references public.lalstudy_papers_v2(canonical_key)
        on delete cascade,

    filename text not null default '',
    file_size_bytes bigint not null default 0,

    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now()
);


create table if not exists public.paper_analysis_cache_v2 (
    id uuid primary key default gen_random_uuid(),

    canonical_key text not null
        references public.lalstudy_papers_v2(canonical_key)
        on delete cascade,

    depth text not null,
    stage text not null,
    analysis_version text not null,

    result_json jsonb not null default '{}'::jsonb,

    provider text not null default 'openai',
    model text not null default '',
    usage_json jsonb not null default '{}'::jsonb,

    hit_count bigint not null default 0,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    unique (
        canonical_key,
        depth,
        stage,
        analysis_version
    )
);


create index if not exists idx_lalstudy_papers_v2_doi
    on public.lalstudy_papers_v2 (doi)
    where doi <> '';

create index if not exists idx_lalstudy_papers_v2_pmcid
    on public.lalstudy_papers_v2 (pmcid)
    where pmcid <> '';

create index if not exists idx_lalstudy_papers_v2_pmid
    on public.lalstudy_papers_v2 (pmid)
    where pmid <> '';

create index if not exists idx_paper_file_aliases_v2_canonical
    on public.paper_file_aliases_v2 (canonical_key);

create index if not exists idx_paper_analysis_cache_v2_lookup
    on public.paper_analysis_cache_v2 (
        canonical_key,
        depth,
        stage,
        analysis_version
    );

create index if not exists idx_paper_analysis_cache_v2_hits
    on public.paper_analysis_cache_v2 (
        hit_count desc
    );


create or replace function public.lalstudy_set_updated_at_v2()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;


drop trigger if exists trg_paper_analysis_cache_v2_updated_at
    on public.paper_analysis_cache_v2;

create trigger trg_paper_analysis_cache_v2_updated_at
before update on public.paper_analysis_cache_v2
for each row
execute function public.lalstudy_set_updated_at_v2();


create or replace function public.paper_analysis_increment_hit_v2(
    p_cache_id uuid
)
returns void
language sql
security definer
set search_path = public
as $$
    update public.paper_analysis_cache_v2
    set hit_count = hit_count + 1
    where id = p_cache_id;
$$;


create or replace function public.lalstudy_touch_paper_v2(
    p_canonical_key text
)
returns void
language sql
security definer
set search_path = public
as $$
    update public.lalstudy_papers_v2
    set last_seen_at = now()
    where canonical_key = p_canonical_key;
$$;


alter table public.lalstudy_papers_v2
    enable row level security;

alter table public.paper_file_aliases_v2
    enable row level security;

alter table public.paper_analysis_cache_v2
    enable row level security;


revoke all on table public.lalstudy_papers_v2
    from anon, authenticated;

revoke all on table public.paper_file_aliases_v2
    from anon, authenticated;

revoke all on table public.paper_analysis_cache_v2
    from anon, authenticated;


grant all on table public.lalstudy_papers_v2
    to service_role;

grant all on table public.paper_file_aliases_v2
    to service_role;

grant all on table public.paper_analysis_cache_v2
    to service_role;


grant execute on function
    public.paper_analysis_increment_hit_v2(uuid)
    to service_role;

grant execute on function
    public.lalstudy_touch_paper_v2(text)
    to service_role;
