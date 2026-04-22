-- Mochi Academia Planner — Supabase schema
-- Run this in the Supabase SQL editor (one-time).
-- Includes RLS so each user can only touch their own rows.

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------
create table if not exists public.classes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  professor text default '',
  location text default '',
  color text default '#FADADD',
  created_at timestamptz default now()
);

create table if not exists public.schedule (
  id uuid primary key default gen_random_uuid(),
  class_id uuid not null references public.classes(id) on delete cascade,
  day_of_week int not null check (day_of_week between 0 and 6), -- 0 = Monday
  start_time time not null,
  end_time time not null
);

create table if not exists public.assignments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  class_id uuid references public.classes(id) on delete set null,
  title text not null,
  due_date date,
  priority text default 'medium' check (priority in ('low','medium','high')),
  status text default 'todo' check (status in ('todo','in_progress','done')),
  created_at timestamptz default now()
);

create table if not exists public.gpa_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  class_id uuid references public.classes(id) on delete set null,
  credits numeric(4,2) not null,
  grade text not null
);

create table if not exists public.lab_folders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null,
  description text default '',
  created_at timestamptz default now()
);

create table if not exists public.lab_entries (
  id uuid primary key default gen_random_uuid(),
  folder_id uuid not null references public.lab_folders(id) on delete cascade,
  title text not null,
  date date default current_date,
  summary text default '',
  notes text default '',
  created_at timestamptz default now()
);

create table if not exists public.lab_files (
  id uuid primary key default gen_random_uuid(),
  entry_id uuid not null references public.lab_entries(id) on delete cascade,
  file_url text not null,
  file_type text default ''
);

create table if not exists public.notes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text default 'Untitled',
  content text default '',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.study_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  class_id uuid references public.classes(id) on delete set null,
  duration int not null,  -- minutes
  date date default current_date,
  notes text default ''
);

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------
alter table public.classes        enable row level security;
alter table public.schedule       enable row level security;
alter table public.assignments    enable row level security;
alter table public.gpa_records    enable row level security;
alter table public.lab_folders    enable row level security;
alter table public.lab_entries    enable row level security;
alter table public.lab_files      enable row level security;
alter table public.notes          enable row level security;
alter table public.study_sessions enable row level security;

-- Helper: owner-only policies for tables with user_id.
do $$
declare t text;
begin
  for t in select unnest(array[
    'classes','assignments','gpa_records','lab_folders','notes','study_sessions'
  ]) loop
    execute format($f$
      drop policy if exists "%1$s_owner_all" on public.%1$s;
      create policy "%1$s_owner_all" on public.%1$s
        for all using (user_id = auth.uid()) with check (user_id = auth.uid());
    $f$, t);
  end loop;
end $$;

-- schedule: joined ownership via classes.
drop policy if exists "schedule_owner_all" on public.schedule;
create policy "schedule_owner_all" on public.schedule for all
  using (exists (select 1 from public.classes c where c.id = schedule.class_id and c.user_id = auth.uid()))
  with check (exists (select 1 from public.classes c where c.id = schedule.class_id and c.user_id = auth.uid()));

-- lab_entries: joined via lab_folders.
drop policy if exists "lab_entries_owner_all" on public.lab_entries;
create policy "lab_entries_owner_all" on public.lab_entries for all
  using (exists (select 1 from public.lab_folders f where f.id = lab_entries.folder_id and f.user_id = auth.uid()))
  with check (exists (select 1 from public.lab_folders f where f.id = lab_entries.folder_id and f.user_id = auth.uid()));

-- lab_files: joined via lab_entries -> lab_folders.
drop policy if exists "lab_files_owner_all" on public.lab_files;
create policy "lab_files_owner_all" on public.lab_files for all
  using (exists (
    select 1 from public.lab_entries e
    join public.lab_folders f on f.id = e.folder_id
    where e.id = lab_files.entry_id and f.user_id = auth.uid()
  ))
  with check (exists (
    select 1 from public.lab_entries e
    join public.lab_folders f on f.id = e.folder_id
    where e.id = lab_files.entry_id and f.user_id = auth.uid()
  ));

-- ---------------------------------------------------------------------------
-- Storage bucket for lab files
-- ---------------------------------------------------------------------------
-- Create a 'lab' bucket in Supabase Storage (public read; upload restricted by policy).
-- Run separately in the Storage UI or:
--   insert into storage.buckets (id, name, public) values ('lab','lab',true)
--     on conflict (id) do nothing;
-- Then add a policy so users can upload only into their own folder prefix:
--   create policy "lab_user_upload" on storage.objects for insert
--     with check (bucket_id = 'lab' and (storage.foldername(name))[1] = auth.uid()::text);
--   create policy "lab_user_read" on storage.objects for select
--     using (bucket_id = 'lab');
