-- ResQ AI — Supabase vectors + object storage (run after schema.sql)
-- https://supabase.com/dashboard/project/_/sql

create extension if not exists vector with schema extensions;

-- Object storage bucket for report images and emergency documents
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'resq-assets',
    'resq-assets',
    true,
    5242880,
    array[
        'image/jpeg',
        'image/png',
        'image/webp',
        'image/gif',
        'text/plain',
        'text/markdown',
        'application/pdf'
    ]
)
on conflict (id) do nothing;

drop policy if exists "public read resq assets" on storage.objects;
create policy "public read resq assets"
    on storage.objects for select
    using (bucket_id = 'resq-assets');

drop policy if exists "service role upload resq assets" on storage.objects;
create policy "service role upload resq assets"
    on storage.objects for insert
    with check (bucket_id = 'resq-assets');

drop policy if exists "service role update resq assets" on storage.objects;
create policy "service role update resq assets"
    on storage.objects for update
    using (bucket_id = 'resq-assets');

-- Optional attachments on community reports
alter table public.community_reports
    add column if not exists attachment_path text,
    add column if not exists attachment_url text,
    add column if not exists attachment_mime text;

-- Searchable knowledge corpus (images, documents, linked reports)
create table if not exists public.knowledge_assets (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    content_text text not null,
    asset_type text not null default 'document'
        check (asset_type in ('image', 'document', 'report')),
    storage_path text,
    storage_url text,
    mime_type text,
    area text,
    source_type text,
    source_id uuid,
    embedding extensions.vector(384),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_knowledge_assets_created_at
    on public.knowledge_assets (created_at desc);

create index if not exists idx_knowledge_assets_area
    on public.knowledge_assets (area);

create index if not exists idx_knowledge_assets_embedding
    on public.knowledge_assets
    using hnsw (embedding extensions.vector_cosine_ops);

alter table public.knowledge_assets enable row level security;

drop policy if exists "public read knowledge assets" on public.knowledge_assets;
create policy "public read knowledge assets"
    on public.knowledge_assets for select using (true);

-- Semantic search RPC (cosine distance; lower = more similar)
create or replace function public.match_knowledge_assets(
    query_embedding extensions.vector(384),
    match_threshold float default 0.7,
    match_count int default 5,
    filter_area text default null
)
returns table (
    id uuid,
    title text,
    content_text text,
    asset_type text,
    storage_url text,
    mime_type text,
    area text,
    source_type text,
    source_id uuid,
    similarity float,
    created_at timestamptz
)
language sql stable
as $$
    select
        ka.id,
        ka.title,
        ka.content_text,
        ka.asset_type,
        ka.storage_url,
        ka.mime_type,
        ka.area,
        ka.source_type,
        ka.source_id,
        1 - (ka.embedding <=> query_embedding) as similarity,
        ka.created_at
    from public.knowledge_assets ka
    where ka.embedding is not null
      and (filter_area is null or ka.area ilike '%' || filter_area || '%')
      and 1 - (ka.embedding <=> query_embedding) >= match_threshold
    order by ka.embedding <=> query_embedding
    limit match_count;
$$;
