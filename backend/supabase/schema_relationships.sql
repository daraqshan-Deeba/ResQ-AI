-- ResQ AI — Foreign-key relationships (run after schema.sql, schema_vectors.sql, schema_auth.sql)
-- Links user-owned activity tables to profiles. Reference tables (hospitals, shelters) stay independent.

-- ── User-owned rows → profiles ───────────────────────────────────────────────
alter table public.community_reports
    add column if not exists user_id uuid references public.profiles (id) on delete set null;

alter table public.sos_events
    add column if not exists user_id uuid references public.profiles (id) on delete set null;

alter table public.emergency_logs
    add column if not exists user_id uuid references public.profiles (id) on delete set null;

alter table public.device_tokens
    add column if not exists user_id uuid references public.profiles (id) on delete set null;

create index if not exists idx_community_reports_user_id
    on public.community_reports (user_id);

create index if not exists idx_sos_events_user_id
    on public.sos_events (user_id);

create index if not exists idx_emergency_logs_user_id
    on public.emergency_logs (user_id);

create index if not exists idx_device_tokens_user_id
    on public.device_tokens (user_id);

-- ── Knowledge assets ← community reports (when source_type = community_report) ─
-- source_id stores the community_reports.id for report-derived embeddings.
alter table public.knowledge_assets
    drop constraint if exists knowledge_assets_source_report_fkey;

alter table public.knowledge_assets
    add constraint knowledge_assets_source_report_fkey
    foreign key (source_id) references public.community_reports (id) on delete set null;

-- ── Comments (Supabase schema visualizer) ─────────────────────────────────────
comment on table public.hospitals is 'Reference directory — no user FK (imported from KML/OSM).';
comment on table public.shelters is 'Reference directory — admin-seeded capacity data.';
comment on table public.profiles is 'App user profile; FK to auth.users(id).';
comment on column public.community_reports.user_id is 'Optional reporter; null for anonymous/demo reports.';
comment on column public.knowledge_assets.source_id is 'FK to community_reports when source_type = community_report.';
