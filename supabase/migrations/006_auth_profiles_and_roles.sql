-- Application-owned identity profile and role assignments for Supabase Auth users.
-- Browser roles cannot access these tables directly; FastAPI remains the application access path.

create table public.user_profiles (
  auth_user_id uuid primary key references auth.users (id) on delete cascade,
  display_name varchar(200),
  preferred_language varchar(20),
  avatar_url text,
  status varchar(24) not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ck_user_profiles_status check (status in ('invited', 'active', 'suspended', 'disabled'))
);

create table public.user_roles (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid not null references public.user_profiles (auth_user_id) on delete cascade,
  role_name varchar(32) not null,
  hospital_id uuid references public.hospitals (id) on delete cascade,
  is_primary boolean not null default false,
  granted_by_auth_user_id uuid references auth.users (id) on delete set null,
  granted_at timestamptz not null default now(),
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ck_user_roles_role_name check (
    role_name in ('platform_admin', 'administrator', 'doctor', 'nurse', 'receptionist', 'billing_staff', 'patient')
  ),
  constraint ck_user_roles_scope check (
    (role_name in ('platform_admin', 'patient') and hospital_id is null)
    or
    (role_name in ('administrator', 'doctor', 'nurse', 'receptionist', 'billing_staff') and hospital_id is not null)
  ),
  constraint ck_user_roles_revocation check (revoked_at is null or revoked_at >= granted_at)
);

create unique index uq_user_roles_active_global_role
  on public.user_roles (auth_user_id, role_name)
  where hospital_id is null and revoked_at is null;

create unique index uq_user_roles_active_hospital_role
  on public.user_roles (auth_user_id, role_name, hospital_id)
  where hospital_id is not null and revoked_at is null;

create unique index uq_user_roles_active_primary
  on public.user_roles (auth_user_id)
  where is_primary and revoked_at is null;

create index ix_user_roles_hospital_active
  on public.user_roles (hospital_id, role_name)
  where revoked_at is null;

create trigger set_user_profiles_updated_at
before update on public.user_profiles
for each row execute function public.set_updated_at();

create trigger set_user_roles_updated_at
before update on public.user_roles
for each row execute function public.set_updated_at();

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.user_profiles (auth_user_id, display_name, preferred_language, avatar_url)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'display_name', new.raw_user_meta_data ->> 'full_name'),
    new.raw_user_meta_data ->> 'preferred_language',
    coalesce(new.raw_user_meta_data ->> 'avatar_url', new.raw_user_meta_data ->> 'picture')
  )
  on conflict (auth_user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_auth_user();

-- Backfill Auth users created before this migration.
insert into public.user_profiles (auth_user_id, display_name, preferred_language, avatar_url)
select
  id,
  coalesce(raw_user_meta_data ->> 'display_name', raw_user_meta_data ->> 'full_name'),
  raw_user_meta_data ->> 'preferred_language',
  coalesce(raw_user_meta_data ->> 'avatar_url', raw_user_meta_data ->> 'picture')
from auth.users
on conflict (auth_user_id) do nothing;

create or replace function public.sync_auth_user_role_metadata(target_auth_user_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  primary_role text;
  active_roles jsonb;
  role_metadata jsonb;
begin
  select role_name
  into primary_role
  from public.user_roles
  where auth_user_id = target_auth_user_id
    and revoked_at is null
  order by is_primary desc, granted_at, id
  limit 1;

  select coalesce(jsonb_agg(role_name order by role_name), '[]'::jsonb)
  into active_roles
  from (
    select distinct role_name
    from public.user_roles
    where auth_user_id = target_auth_user_id
      and revoked_at is null
  ) roles;

  role_metadata := case
    when primary_role is null then '{}'::jsonb
    else jsonb_build_object('role', primary_role, 'roles', active_roles)
  end;

  update auth.users
  set raw_app_meta_data = (coalesce(raw_app_meta_data, '{}'::jsonb) - 'role' - 'roles') || role_metadata,
      updated_at = now()
  where id = target_auth_user_id;
end;
$$;

create or replace function public.sync_auth_role_metadata_after_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    perform public.sync_auth_user_role_metadata(old.auth_user_id);
    return old;
  end if;

  perform public.sync_auth_user_role_metadata(new.auth_user_id);
  if tg_op = 'UPDATE' and old.auth_user_id is distinct from new.auth_user_id then
    perform public.sync_auth_user_role_metadata(old.auth_user_id);
  end if;
  return new;
end;
$$;

create trigger sync_auth_role_metadata
after insert or update or delete on public.user_roles
for each row execute function public.sync_auth_role_metadata_after_change();

alter table public.user_profiles enable row level security;
alter table public.user_roles enable row level security;

revoke all on table public.user_profiles from anon, authenticated;
revoke all on table public.user_roles from anon, authenticated;
revoke all on function public.handle_new_auth_user() from public, anon, authenticated;
revoke all on function public.sync_auth_user_role_metadata(uuid) from public, anon, authenticated;
revoke all on function public.sync_auth_role_metadata_after_change() from public, anon, authenticated;

grant select, insert, update, delete on table public.user_profiles to service_role;
grant select, insert, update, delete on table public.user_roles to service_role;
grant execute on function public.sync_auth_user_role_metadata(uuid) to service_role;

