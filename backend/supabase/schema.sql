-- ResQ AI — Supabase schema
-- Run in Supabase SQL Editor: https://supabase.com/dashboard/project/_/sql

create extension if not exists "pgcrypto";

create table if not exists public.shelters (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    address text,
    lat double precision,
    lon double precision,
    capacity integer not null default 0,
    occupied integer not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists public.community_reports (
    id uuid primary key default gen_random_uuid(),
    area text not null,
    message text not null,
    reporter_name text,
    verified boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists public.emergency_logs (
    id uuid primary key default gen_random_uuid(),
    description text not null,
    emergency_level text not null,
    city text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.sos_events (
    id uuid primary key default gen_random_uuid(),
    latitude double precision not null,
    longitude double precision not null,
    situation text,
    notification_status text not null default 'pending_notification',
    message_id text,
    error_detail text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.device_tokens (
    token text primary key,
    registered_at timestamptz not null default now()
);

create table if not exists public.hospitals (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    address text,
    lat double precision not null,
    lon double precision not null,
    phone text,
    facility_type text,
    district text,
    source text not null default 'supabase',
    source_file text,
    ward text,
    circle text,
    zone text,
    hod text,
    object_id text,
    osm_id bigint,
    osm_type text,
    created_at timestamptz not null default now()
);

create unique index if not exists idx_hospitals_dedupe
    on public.hospitals (lower(trim(name)), lat, lon);

create index if not exists idx_hospitals_lat_lon
    on public.hospitals (lat, lon);

create index if not exists idx_community_reports_created_at
    on public.community_reports (created_at desc);

create index if not exists idx_sos_events_created_at
    on public.sos_events (created_at desc);

alter table public.shelters enable row level security;
alter table public.community_reports enable row level security;
alter table public.emergency_logs enable row level security;
alter table public.sos_events enable row level security;
alter table public.device_tokens enable row level security;
alter table public.hospitals enable row level security;

-- Backend uses service_role key (bypasses RLS). Anon read policies for future frontend direct access:
drop policy if exists "public read shelters" on public.shelters;
create policy "public read shelters"
    on public.shelters for select using (true);

drop policy if exists "public read community reports" on public.community_reports;
create policy "public read community reports"
    on public.community_reports for select using (true);

drop policy if exists "public insert community reports" on public.community_reports;
create policy "public insert community reports"
    on public.community_reports for insert with check (true);

drop policy if exists "public read hospitals" on public.hospitals;
create policy "public read hospitals"
    on public.hospitals for select using (true);

-- Also run: schema_vectors.sql, schema_auth.sql
