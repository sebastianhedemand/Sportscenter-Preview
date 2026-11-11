-- Sportscenter / Fodboldcenter personal cloud-sync table
-- Run this script in Supabase SQL Editor for the project used by the app.
-- Each authenticated user can read and write only their own row.

create table if not exists public.fodboldcenter_data (
  user_id uuid primary key references auth.users (id) on delete cascade,
  data jsonb not null default '{"matches":[],"teams":{}}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.fodboldcenter_data enable row level security;

grant select, insert, update, delete
  on public.fodboldcenter_data to authenticated;

drop policy if exists "Users can read their own Sportscenter data"
  on public.fodboldcenter_data;
create policy "Users can read their own Sportscenter data"
  on public.fodboldcenter_data
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "Users can insert their own Sportscenter data"
  on public.fodboldcenter_data;
create policy "Users can insert their own Sportscenter data"
  on public.fodboldcenter_data
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "Users can update their own Sportscenter data"
  on public.fodboldcenter_data;
create policy "Users can update their own Sportscenter data"
  on public.fodboldcenter_data
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users can delete their own Sportscenter data"
  on public.fodboldcenter_data;
create policy "Users can delete their own Sportscenter data"
  on public.fodboldcenter_data
  for delete
  to authenticated
  using (auth.uid() = user_id);

-- Enable cross-device UPDATE notifications when Supabase Realtime is available.
do $$
begin
  if exists (
    select 1 from pg_publication where pubname = 'supabase_realtime'
  ) and not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'fodboldcenter_data'
  ) then
    alter publication supabase_realtime
      add table public.fodboldcenter_data;
  end if;
end
$$;
