-- AI-telefonassistent: grundtabeller
-- Kör i Supabase SQL Editor, eller: supabase db push

create table if not exists samtal (
  id uuid primary key default gen_random_uuid(),
  vapi_call_id text unique,
  fran_nummer text,
  startad_at timestamptz,
  avslutad_at timestamptz,
  varaktighet_sek int,
  utfall text check (utfall in ('bokning','meddelande','avbrutet','okant')),
  transkript text,
  sammanfattning text,
  skapad_at timestamptz default now()
);

create table if not exists bokningar (
  id uuid primary key default gen_random_uuid(),
  samtal_id uuid references samtal(id),
  namn text not null,
  telefon text not null,
  arende text,
  start_at timestamptz not null,
  google_event_id text,
  sms_skickat boolean default false,
  skapad_at timestamptz default now()
);

create table if not exists meddelanden (
  id uuid primary key default gen_random_uuid(),
  samtal_id uuid references samtal(id),
  namn text,
  telefon text,
  arende text not null,
  bradskande boolean default false,
  hanterat boolean default false,
  skapad_at timestamptz default now()
);

create index if not exists idx_bokningar_start on bokningar (start_at);
create index if not exists idx_meddelanden_ohanterade on meddelanden (skapad_at) where not hanterat;

-- Bara servern (service key) rör de här tabellerna. Ingen anonym åtkomst.
alter table samtal enable row level security;
alter table bokningar enable row level security;
alter table meddelanden enable row level security;
