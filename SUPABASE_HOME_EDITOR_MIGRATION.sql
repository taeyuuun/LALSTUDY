-- ============================================================
-- LALSTUDY v0.6.1 Open Beta
-- Home Studio persistent configuration
-- ============================================================

create table if not exists public.home_page_config (
    slug text primary key,
    config jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

alter table public.home_page_config enable row level security;

-- Public browser users must never write the home configuration directly.
revoke all on table public.home_page_config from anon;
revoke all on table public.home_page_config from authenticated;

-- LALSTUDY's server-side Supabase secret key performs read/write operations.
grant all on table public.home_page_config to service_role;

create or replace function public.home_page_config_touch_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_home_page_config_touch_updated_at
on public.home_page_config;

create trigger trg_home_page_config_touch_updated_at
before update on public.home_page_config
for each row
execute function public.home_page_config_touch_updated_at();
