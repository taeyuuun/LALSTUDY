-- ============================================================
-- LALSTUDY v0.4.2
-- Shared Paper Analysis Cache
--
-- Run ONCE in:
-- Supabase Dashboard -> SQL Editor -> New query
--
-- Stores:
--   exact PDF SHA-256 hash
--   AI result JSON
--   model/provider/usage metadata
--
-- Does NOT store:
--   PDF bytes
--   extracted full paper text
--   Figure image bytes
--
-- Retrieval requires the exact same PDF hash.
-- ============================================================

create extension if not exists pgcrypto;

create table if not exists public.lalstudy_papers (
    id uuid primary key default gen_random_uuid(),

    paper_hash text not null unique,
    filename text not null default '',
    file_size_bytes bigint not null default 0,

    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now()
);

create table if not exists public.paper_analysis_cache (
    id uuid primary key default gen_random_uuid(),

    paper_hash text not null
        references public.lalstudy_papers(paper_hash)
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
        paper_hash,
        depth,
        stage,
        analysis_version
    )
);

create index if not exists idx_lalstudy_papers_hash
    on public.lalstudy_papers (paper_hash);

create index if not exists idx_paper_analysis_cache_lookup
    on public.paper_analysis_cache (
        paper_hash,
        depth,
        stage,
        analysis_version
    );

create index if not exists idx_paper_analysis_cache_hits
    on public.paper_analysis_cache (hit_count desc);

create or replace function public.lalstudy_set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_paper_analysis_cache_updated_at
    on public.paper_analysis_cache;

create trigger trg_paper_analysis_cache_updated_at
before update on public.paper_analysis_cache
for each row
execute function public.lalstudy_set_updated_at();


create or replace function public.paper_analysis_increment_hit(
    p_cache_id uuid
)
returns void
language sql
security definer
set search_path = public
as $$
    update public.paper_analysis_cache
    set hit_count = hit_count + 1
    where id = p_cache_id;
$$;


create or replace function public.lalstudy_touch_paper(
    p_paper_hash text
)
returns void
language sql
security definer
set search_path = public
as $$
    update public.lalstudy_papers
    set last_seen_at = now()
    where paper_hash = p_paper_hash;
$$;


-- Server-only access.
alter table public.lalstudy_papers enable row level security;
alter table public.paper_analysis_cache enable row level security;

revoke all on table public.lalstudy_papers
    from anon, authenticated;

revoke all on table public.paper_analysis_cache
    from anon, authenticated;

grant all on table public.lalstudy_papers
    to service_role;

grant all on table public.paper_analysis_cache
    to service_role;

grant execute on function
    public.paper_analysis_increment_hit(uuid)
    to service_role;

grant execute on function
    public.lalstudy_touch_paper(text)
    to service_role;
