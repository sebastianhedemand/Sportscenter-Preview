-- Sportscenter: additive analytics storage. Run only after reviewing in Supabase SQL editor.
-- This does not modify legacy public.fodboldcenter_data or existing browser backups.
create extension if not exists pgcrypto;

create table if not exists public.sportscenter_fixtures (
  id uuid primary key default gen_random_uuid(),
  sport text not null check (sport in ('football','handball')),
  league_key text not null,
  season_key text not null,
  provider text not null,
  provider_event_id text not null,
  home_team text not null,
  away_team text not null,
  kickoff_at timestamptz not null,
  status text not null default 'scheduled' check (status in ('scheduled','live','finished','postponed','cancelled','abandoned')),
  home_score integer check (home_score >= 0),
  away_score integer check (away_score >= 0),
  provider_updated_at timestamptz,
  fetched_at timestamptz not null default now(),
  unique(provider,provider_event_id),
  check ((home_score is null and away_score is null) or (home_score is not null and away_score is not null))
);
create index if not exists sportscenter_fixtures_kickoff_idx on public.sportscenter_fixtures(sport,league_key,kickoff_at);

create table if not exists public.sportscenter_odds_snapshots (
  id uuid primary key default gen_random_uuid(),
  fixture_id uuid not null references public.sportscenter_fixtures(id),
  bookmaker text not null,
  market text not null,
  selection text not null,
  line numeric(8,2),
  decimal_odds numeric(12,4) not null check (decimal_odds > 1),
  source text not null,
  observed_at timestamptz not null,
  ingested_at timestamptz not null default now(),
  unique(fixture_id,bookmaker,market,selection,line,observed_at)
);
create index if not exists sportscenter_odds_lookup_idx on public.sportscenter_odds_snapshots(fixture_id,market,observed_at desc);

create table if not exists public.sportscenter_predictions (
  id uuid primary key default gen_random_uuid(),
  fixture_id uuid not null references public.sportscenter_fixtures(id),
  model_name text not null,
  model_version text not null,
  market text not null,
  selection text not null,
  line numeric(8,2),
  predicted_probability numeric(10,8) not null check (predicted_probability > 0 and predicted_probability < 1),
  fair_odds numeric(12,4) not null check (fair_odds > 1),
  offered_odds numeric(12,4) check (offered_odds > 1),
  bookmaker text,
  odds_snapshot_id uuid references public.sportscenter_odds_snapshots(id),
  expected_value numeric(12,8),
  published_at timestamptz not null default now(),
  source text not null default 'model',
  check ((offered_odds is null and expected_value is null) or (offered_odds is not null))
);
create index if not exists sportscenter_predictions_fixture_idx on public.sportscenter_predictions(fixture_id,published_at desc);

create table if not exists public.sportscenter_settlements (
  prediction_id uuid primary key references public.sportscenter_predictions(id),
  outcome text not null check (outcome in ('won','lost','void','push')),
  profit_units numeric(14,6) not null,
  settled_at timestamptz not null default now(),
  verified_source text not null,
  verified_event_id text not null,
  check ((outcome in ('void','push') and profit_units = 0) or outcome in ('won','lost'))
);

-- No direct anonymous/authenticated writes to provider data or published predictions.
-- Provider ingestion must use a trusted server-side role, never a browser service key.
alter table public.sportscenter_fixtures enable row level security;
alter table public.sportscenter_odds_snapshots enable row level security;
alter table public.sportscenter_predictions enable row level security;
alter table public.sportscenter_settlements enable row level security;

-- Public read is deliberately NOT granted until data redistribution and product access rules are approved.
-- Do not expose these tables directly to the frontend before entitlement checks are implemented.

-- Immutable published history: ordinary UPDATE/DELETE attempts are rejected, including service-role writes.
create or replace function public.sportscenter_reject_history_mutation()
returns trigger language plpgsql set search_path = '' as $$
begin
  raise exception 'Published Sportscenter history is append-only';
end;
$$;
drop trigger if exists sportscenter_odds_immutable on public.sportscenter_odds_snapshots;
create trigger sportscenter_odds_immutable before update or delete on public.sportscenter_odds_snapshots
for each row execute function public.sportscenter_reject_history_mutation();
drop trigger if exists sportscenter_predictions_immutable on public.sportscenter_predictions;
create trigger sportscenter_predictions_immutable before update or delete on public.sportscenter_predictions
for each row execute function public.sportscenter_reject_history_mutation();
drop trigger if exists sportscenter_settlements_immutable on public.sportscenter_settlements;
create trigger sportscenter_settlements_immutable before update or delete on public.sportscenter_settlements
for each row execute function public.sportscenter_reject_history_mutation();

-- One unit staked per settled prediction. Push/void are excluded from win/loss hit rate and ROI denominator.
create or replace view public.sportscenter_performance_summary
with (security_invoker = true) as
select f.sport, f.league_key, p.market,
       count(*) filter (where s.outcome in ('won','lost')) as graded_bets,
       count(*) filter (where s.outcome = 'won') as wins,
       count(*) filter (where s.outcome = 'lost') as losses,
       count(*) filter (where s.outcome in ('void','push')) as void_or_push,
       round(100.0 * count(*) filter (where s.outcome = 'won')
         / nullif(count(*) filter (where s.outcome in ('won','lost')),0),2) as hit_rate_pct,
       round(sum(s.profit_units) filter (where s.outcome in ('won','lost'))
         / nullif(count(*) filter (where s.outcome in ('won','lost')),0) * 100,2) as roi_pct
from public.sportscenter_predictions p
join public.sportscenter_fixtures f on f.id=p.fixture_id
join public.sportscenter_settlements s on s.prediction_id=p.id
group by f.sport,f.league_key,p.market;
