-- Add lat/lon to community_reports for distance-filtered traffic nearby.
-- Safe to re-run.

alter table public.community_reports
    add column if not exists lat double precision;

alter table public.community_reports
    add column if not exists lon double precision;

create index if not exists idx_community_reports_lat_lon
    on public.community_reports (lat, lon);
