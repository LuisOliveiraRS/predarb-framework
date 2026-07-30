begin;

do $$
begin
    create type public.app_role as enum (
        'viewer',
        'operator',
        'admin'
    );
exception
    when duplicate_object then null;
end
$$;

create table if not exists public.profiles (
    id uuid primary key
        references auth.users(id)
        on delete cascade,

    email text,
    display_name text,

    role public.app_role
        not null
        default 'viewer',

    is_active boolean
        not null
        default true,

    mfa_required boolean
        not null
        default true,

    created_at timestamptz
        not null
        default now(),

    updated_at timestamptz
        not null
        default now()
);

create index if not exists profiles_role_idx
    on public.profiles(role);

create index if not exists profiles_active_idx
    on public.profiles(is_active);

alter table public.profiles
    enable row level security;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists profiles_set_updated_at
    on public.profiles;

create trigger profiles_set_updated_at
before update on public.profiles
for each row
execute function public.set_updated_at();

create or replace function public.sync_auth_user_profile()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    resolved_name text;
begin
    resolved_name := coalesce(
        nullif(
            new.raw_user_meta_data ->> 'display_name',
            ''
        ),
        nullif(split_part(new.email, '@', 1), ''),
        'PredArb User'
    );

    insert into public.profiles (
        id,
        email,
        display_name
    )
    values (
        new.id,
        new.email,
        resolved_name
    )
    on conflict (id) do update
    set
        email = excluded.email,
        display_name = coalesce(
            nullif(excluded.display_name, ''),
            public.profiles.display_name
        ),
        updated_at = now();

    return new;
end;
$$;

drop trigger if exists auth_user_profile_sync
    on auth.users;

create trigger auth_user_profile_sync
after insert or update of email, raw_user_meta_data
on auth.users
for each row
execute function public.sync_auth_user_profile();

create or replace function public.current_app_role()
returns public.app_role
language sql
stable
security definer
set search_path = ''
as $$
    select profile.role
    from public.profiles as profile
    where profile.id = (select auth.uid())
      and profile.is_active = true
    limit 1
$$;

revoke all
    on function public.current_app_role()
    from public, anon;

grant execute
    on function public.current_app_role()
    to authenticated, service_role;

drop policy if exists profiles_select_own
    on public.profiles;

create policy profiles_select_own
on public.profiles
for select
to authenticated
using (
    id = (select auth.uid())
);

drop policy if exists profiles_admin_select_all
    on public.profiles;

create policy profiles_admin_select_all
on public.profiles
for select
to authenticated
using (
    (select public.current_app_role()) = 'admin'
);

drop policy if exists profiles_admin_update_all
    on public.profiles;

create policy profiles_admin_update_all
on public.profiles
for update
to authenticated
using (
    (select public.current_app_role()) = 'admin'
)
with check (
    (select public.current_app_role()) = 'admin'
);

revoke all on public.profiles from anon;

grant select, update
    on public.profiles
    to authenticated;

create table if not exists public.audit_events (
    id bigint
        generated always as identity
        primary key,

    actor_user_id uuid
        references auth.users(id)
        on delete set null,

    action text not null,
    target_type text,
    target_id text,

    ip_address inet,
    user_agent text,

    metadata jsonb
        not null
        default '{}'::jsonb,

    created_at timestamptz
        not null
        default now()
);

create index if not exists audit_events_actor_idx
    on public.audit_events(actor_user_id);

create index if not exists audit_events_created_at_idx
    on public.audit_events(created_at desc);

create index if not exists audit_events_action_idx
    on public.audit_events(action);

alter table public.audit_events
    enable row level security;

drop policy if exists audit_events_admin_select
    on public.audit_events;

create policy audit_events_admin_select
on public.audit_events
for select
to authenticated
using (
    (select public.current_app_role()) = 'admin'
);

revoke all on public.audit_events from anon;

grant select
    on public.audit_events
    to authenticated;

grant select, insert
    on public.audit_events
    to service_role;

grant usage, select
    on sequence public.audit_events_id_seq
    to service_role;

comment on table public.profiles is
    'Perfis e papeis de acesso dos usuarios PredArb.';

comment on table public.audit_events is
    'Eventos administrativos e operacionais do PredArb.';

commit;
