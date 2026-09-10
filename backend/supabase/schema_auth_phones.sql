-- ResQ AI — Phone normalization (country dial + national + E.164)
-- Run after schema_auth.sql

alter table public.profiles
    add column if not exists phone_country_dial text not null default '+91',
    add column if not exists phone_national text,
    add column if not exists emergency_contact_country_dial text default '+91',
    add column if not exists emergency_contact_national text;

-- Backfill structured columns from legacy phone values
update public.profiles
set
    phone_country_dial = '+91',
    phone_national = right(regexp_replace(phone, '[^0-9]', '', 'g'), 10)
where phone is not null
  and phone_national is null
  and regexp_replace(phone, '[^0-9]', '', 'g') ~ '^\d{10}$';

update public.profiles
set
    phone_country_dial = '+91',
    phone_national = right(regexp_replace(phone, '[^0-9]', '', 'g'), 10)
where phone is not null
  and phone_national is null
  and regexp_replace(phone, '[^0-9]', '', 'g') ~ '^91\d{10}$';

update public.profiles
set
    phone_country_dial = '+1',
    phone_national = right(regexp_replace(phone, '[^0-9]', '', 'g'), 10)
where phone is not null
  and phone_national is null
  and regexp_replace(phone, '[^0-9]', '', 'g') ~ '^1\d{10}$';

update public.profiles
set phone = phone_country_dial || phone_national
where phone_national is not null
  and (phone is null or phone !~ '^\+[1-9]\d{6,14}$');

update public.profiles
set
    emergency_contact_country_dial = '+91',
    emergency_contact_national = right(
        regexp_replace(emergency_contact_phone, '[^0-9]', '', 'g'),
        10
    )
where emergency_contact_phone is not null
  and emergency_contact_national is null
  and regexp_replace(emergency_contact_phone, '[^0-9]', '', 'g') ~ '^(91)?\d{10}$';

update public.profiles
set emergency_contact_phone = emergency_contact_country_dial || emergency_contact_national
where emergency_contact_national is not null
  and (
      emergency_contact_phone is null
      or emergency_contact_phone !~ '^\+[1-9]\d{6,14}$'
  );

alter table public.profiles drop constraint if exists profiles_phone_e164_check;
alter table public.profiles
    add constraint profiles_phone_e164_check
    check (phone is null or phone ~ '^\+[1-9]\d{6,14}$');

alter table public.profiles drop constraint if exists profiles_emergency_phone_e164_check;
alter table public.profiles
    add constraint profiles_emergency_phone_e164_check
    check (
        emergency_contact_phone is null
        or emergency_contact_phone ~ '^\+[1-9]\d{6,14}$'
    );

alter table public.profiles drop constraint if exists profiles_phone_national_digits_check;
alter table public.profiles
    add constraint profiles_phone_national_digits_check
    check (phone_national is null or phone_national ~ '^\d{7,15}$');

alter table public.profiles drop constraint if exists profiles_emergency_national_digits_check;
alter table public.profiles
    add constraint profiles_emergency_national_digits_check
    check (
        emergency_contact_national is null
        or emergency_contact_national ~ '^\d{7,15}$'
    );
