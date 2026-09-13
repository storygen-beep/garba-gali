-- A piece is photographed from the front, the back, and sometimes a detail.
-- photo_path stays the one the app shows; photos holds every view, front first.
alter table public.lehengas add column if not exists photos jsonb not null default '[]'::jsonb;
