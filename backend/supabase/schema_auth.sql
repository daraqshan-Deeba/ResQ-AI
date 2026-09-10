-- ResQ AI — Auth profiles (run after schema.sql)
-- Works with Supabase Auth + Google OAuth provider

create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    email text not null,
    full_name text,
    display_name text,
    avatar_url text,
    phone text,
    phone_country_dial text not null default '+91',
    phone_national text,
    city text default 'Hyderabad',
    emergency_contact_name text,
    emergency_contact_phone text,
    emergency_contact_country_dial text default '+91',
    emergency_contact_national text,
    registration_complete boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_profiles_email on public.profiles (email);

alter table public.profiles enable row level security;

drop policy if exists "users read own profile" on public.profiles;
create policy "users read own profile"
    on public.profiles for select
    using (auth.uid() = id);

drop policy if exists "users insert own profile" on public.profiles;
create policy "users insert own profile"
    on public.profiles for insert
    with check (auth.uid() = id);

drop policy if exists "users update own profile" on public.profiles;
create policy "users update own profile"
    on public.profiles for update
    using (auth.uid() = id);

-- Seed profile row when a new auth user is created (Google sign-in)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (
        id,
        email,
        full_name,
        display_name,
        avatar_url,
        registration_complete
    )
    values (
        new.id,
        coalesce(new.email, ''),
        coalesce(
            new.raw_user_meta_data->>'full_name',
            new.raw_user_meta_data->>'name'
        ),
        coalesce(
            new.raw_user_meta_data->>'name',
            split_part(coalesce(new.email, 'user'), '@', 1)
        ),
        coalesce(
            new.raw_user_meta_data->>'avatar_url',
            new.raw_user_meta_data->>'picture'
        ),
        false
    )
    on conflict (id) do update set
        email = excluded.email,
        full_name = coalesce(public.profiles.full_name, excluded.full_name),
        display_name = coalesce(public.profiles.display_name, excluded.display_name),
        avatar_url = coalesce(public.profiles.avatar_url, excluded.avatar_url),
        updated_at = now();
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();
