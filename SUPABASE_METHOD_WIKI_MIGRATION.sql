-- ============================================================
-- LALSTUDY v0.5.0
-- Method Encyclopedia / Method Wiki
--
-- Run ONCE in Supabase SQL Editor.
--
-- Design choice:
-- - This DB stores ONLY reusable method explanation + browse facets.
-- - Paper/Figure relationships stay in the existing method_profiles.json /
--   figure_images.json corpus data. They are intentionally NOT duplicated.
-- ============================================================

create table if not exists public.method_encyclopedia (
    canonical_name text not null,
    normalized_name text primary key,

    summary_ko text not null default '',
    summary_en text not null default '',

    principle_ko text not null default '',
    principle_en text not null default '',

    best_for_ko text not null default '',
    best_for_en text not null default '',

    limitations_ko text not null default '',
    limitations_en text not null default '',

    facets jsonb not null default '{}'::jsonb,

    quality_status text not null default 'AI_GENERATED'
        check (quality_status in ('AI_GENERATED', 'REVIEWED', 'CURATED')),

    source_model text not null default '',
    hit_count bigint not null default 0,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);


create index if not exists idx_method_encyclopedia_canonical
    on public.method_encyclopedia (canonical_name);


create or replace function public.method_encyclopedia_set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;


drop trigger if exists trg_method_encyclopedia_updated_at
    on public.method_encyclopedia;

create trigger trg_method_encyclopedia_updated_at
before update on public.method_encyclopedia
for each row
execute function public.method_encyclopedia_set_updated_at();


create or replace function public.method_encyclopedia_increment_hit(
    p_normalized_name text
)
returns void
language sql
security definer
set search_path = public
as $$
    update public.method_encyclopedia
    set hit_count = hit_count + 1
    where normalized_name = p_normalized_name;
$$;


alter table public.method_encyclopedia enable row level security;

revoke all on table public.method_encyclopedia
    from anon, authenticated;

grant all on table public.method_encyclopedia
    to service_role;

grant execute on function
    public.method_encyclopedia_increment_hit(text)
    to service_role;
