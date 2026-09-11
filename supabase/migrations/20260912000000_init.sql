-- Garba Gali: stock, bookings, and who is allowed to touch them.

create table if not exists public.staff (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text,
  added_at timestamptz not null default now()
);

-- Only people listed in staff may read or write. A stray signup gets nothing.
create or replace function public.is_staff() returns boolean
  language sql stable security definer set search_path = public
  as $$ select exists (select 1 from public.staff s where s.user_id = auth.uid()) $$;

create table if not exists public.lehengas (
  id uuid primary key default gen_random_uuid(),
  code text,
  title text not null,
  rent numeric not null default 0,
  deposit numeric not null default 0,
  colour text,
  size text,
  photo_path text,
  created_at timestamptz not null default now()
);

create table if not exists public.bookings (
  id uuid primary key default gen_random_uuid(),
  lehenga_id uuid not null references public.lehengas(id) on delete restrict,
  name text not null,
  phone text,
  from_date date not null,
  to_date date not null,
  payment text not null default 'Online',
  advance numeric not null default 0,
  discount numeric not null default 0,
  cancelled boolean not null default false,
  returned boolean not null default false,
  deposit_status text not null default 'Not collected',
  created_at timestamptz not null default now()
);

create index if not exists bookings_lehenga_idx on public.bookings (lehenga_id);
create index if not exists bookings_dates_idx on public.bookings (from_date, to_date);

alter table public.staff enable row level security;
alter table public.lehengas enable row level security;
alter table public.bookings enable row level security;

create policy "staff read own row" on public.staff for select using (user_id = auth.uid());
create policy "staff read lehengas" on public.lehengas for select using (public.is_staff());
create policy "staff write lehengas" on public.lehengas for all using (public.is_staff()) with check (public.is_staff());
create policy "staff read bookings" on public.bookings for select using (public.is_staff());
create policy "staff write bookings" on public.bookings for all using (public.is_staff()) with check (public.is_staff());

-- Lehenga photos: anyone may view an image, only staff may upload or delete.
insert into storage.buckets (id, name, public)
  values ('photos', 'photos', true)
  on conflict (id) do update set public = true;

create policy "photos are viewable" on storage.objects for select using (bucket_id = 'photos');
create policy "staff upload photos" on storage.objects for insert with check (bucket_id = 'photos' and public.is_staff());
create policy "staff change photos" on storage.objects for update using (bucket_id = 'photos' and public.is_staff());
create policy "staff delete photos" on storage.objects for delete using (bucket_id = 'photos' and public.is_staff());
