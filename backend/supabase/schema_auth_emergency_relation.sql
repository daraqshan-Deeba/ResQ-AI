-- ResQ AI — Emergency contact relation (run after schema_auth.sql)
-- Used in SOS SMS: "Your {relation} has hit an SOS..."

alter table public.profiles
    add column if not exists emergency_contact_relation text;

comment on column public.profiles.emergency_contact_relation is
    'How the signed-in user is related to the emergency contact (e.g. son, daughter, spouse) from the contact''s point of view: "Your {relation} has hit an SOS".';
