# Sportscenter

Sportscenter is the development name for this football and handball statistics project. The current application is a browser-based single-page app in index.html; it is being modernized incrementally so existing match data, analysis, odds integration and account sync are not lost.

## Current application

- Football and Danish handball league selectors.
- Match and result entry, standings and home/away team statistics.
- Football Over 1.5 / Over 2.5 analysis, Poisson-based estimates, fair odds and expected value calculations.
- Optional pre-match odds retrieval through the existing Supabase Edge Function.
- Local browser storage, JSON backup/import and optional per-user Supabase cloud sync.
- Responsive midnight-navy / blue visual design.

The Over 1.5 / Over 2.5 analysis is a core football feature. The app distinguishes model-derived fair/expected odds from bookmaker prices. Model estimates are not guarantees and must not be presented as certain outcomes.

## Supabase cloud sync setup

1. Create a Supabase project.
2. Open the project's SQL Editor.
3. Run the complete script in [fodboldcenter_supabase_setup.sql](./fodboldcenter_supabase_setup.sql).
4. In the app's Backup tab, enter the Supabase Project URL and the publishable (or legacy anon) key.
5. Create an account or sign in. Use the same account on each device.
6. When prompted about existing cloud data, make a JSON backup first and choose deliberately whether to load cloud data or keep local data.

The SQL creates the public.fodboldcenter_data table and enables row-level security. Each signed-in user can access only the row whose user_id equals their Supabase Auth user ID. Never put a Supabase service_role or secret key in browser code.

## Data and odds integrations

- The browser app currently uses the existing result sources and the existing football-odds Supabase Edge Function.
- Provider coverage, league identifiers, historical depth, bookmaker availability, rate limits and commercial redistribution rights must be verified before the service is marketed as fully automatic or used in a paid product.
- The current handball client query is limited to Denmark. SportsEvents24 documents a country + sport filter and a free-open-beta quota of 100 requests/day per IP, 5,000 records/month per IP and 10 requests/minute. This is useful for prototyping, but not yet a production reliability or commercial-licensing basis: https://sportsevents24.com/api.
- SportsEvents24's public handball listings show German men's top-flight competition names such as “1. Bundesliga Männer”. The exact tournament ID and event-query behavior must be verified before wiring this into the app; do not broaden the current German request to all handball events because that could consume the provider quota and mix youth/regional competitions into the model.
- Football Soccer API documents a coverage endpoint for league-season match counts and data availability. The repository includes a coverage-check script, but a successful live coverage check still requires the private FSAPI_KEY secret: https://footballsoccerapi.com/documentation/coverage.
- Do not fabricate missing fixtures, odds or results. Missing provider data should remain visibly unavailable or be entered manually.
- Do not describe a model estimate as a bookmaker quote.

## Development workflow

- Work on codex/sportscenter-development.
- Keep main as the production/live branch until a reviewed release is approved.
- Test the app on mobile and desktop after changes.
- Preserve user data compatibility and provide a backup path before any schema or storage migration.
- Keep API secrets server-side (for example, in Supabase Edge Function secrets or GitHub Actions secrets).

## Planned work (not yet complete)

1. Validate football league and season coverage, including Superligaen and 1. Division.
2. Validate and implement the requested German Handball-Bundesliga and complete Danish handball coverage using a permitted source.
3. Separate football and handball model logic and calibrate each against appropriate historical data.
4. Add immutable prediction snapshots, odds-at-publication snapshots, result settlement and transparent performance metrics.
5. Add secure free/premium entitlements and payment webhooks only after backend and legal/data-provider review.

No subscription payment flow, public paid picks service or independently audited ROI reporting is claimed to be implemented at this stage.

## Automatisk opdatering af kampresultater

Preview-repositoryet indeholder en GitHub Actions-workflow, der hver dag kl. 04:30 UTC henter afsluttede fodboldresultater fra API-Football. Workflowet kan også startes manuelt under fanen Actions.

For at aktivere opdateringen skal repositoryets ejer tilføje en GitHub Actions secret:

1. Åbn Settings → Secrets and variables → Actions.
2. Vælg New repository secret.
3. Navn: API_FOOTBALL_KEY.
4. Værdi: din API-Football API-nøgle.
5. Gem. Nøglen bliver kun brugt af workflowet og lægges ikke i hjemmesidens JavaScript.

Workflowet kontrollerer de seneste 7 dage for afsluttede kampe i de otte konfigurerede fodboldligaer. Det udfylder kun manglende resultater; eksisterende eller manuelle resultater overskrives ikke. Konflikter markeres i workflow-loggen til manuel kontrol. Når index.html ændres, udløser det automatisk en ny publicering af preview-siden.

Bemærk: Dette automatiserer de fodboldresultater, som den nuværende API-Football-integration dækker. Det er ikke endnu en komplet automatisk resultatløsning for håndbold eller alle ønskede ligaer.

## Test af gratis sportsdatakilder

En manuel GitHub Actions-test undersøger SportsEvents24's turneringsoversigter for de 13 ønskede fodbold- og håndboldligaer. Testen følger `nextCursor` og læser flere sider (med en grænse på otte sider pr. land/sport) i stedet for kun den første side. For hver fundet liga testes flere relevante sæson-ID'er separat (op til 24 event-opslag samlet), så forkerte dubletter, 2. Bundesliga og træningskampe lettere kan frasorteres. For hvert ID undersøges offentliggjorte kampe i API'ets seneste 7-dages vindue. Sæsonformaterne `2026/27` og `2026/2027` normaliseres. Hvis turneringslisten ikke finder engelske eller spanske ligaer, laver testen desuden et begrænset land+sport-opslag på kampe i API'ets tilladte datovindue for at lede efter turnerings-ID'er.

Sådan køres testen:

1. Åbn fanen Actions i dette repository.
2. Vælg **Test gratis sportsdatakilder**.
3. Klik **Run workflow**.
4. Åbn den færdige kørsel og hent artifactet **sports-events24-coverage**.

Testen er skrivebeskyttet og ændrer ikke `index.html` eller kampdata. Den kræver ingen API-nøgle. Et fundet turneringsnavn eller et enkelt event-opslag beviser ikke komplet sæsondækning, historisk dybde, odds eller kommercielle rettigheder. SportsEvents24 dokumenterer gratis beta med 100 dataforespørgsler pr. dag/IP, 5.000 returnerede poster pr. måned/IP, 100 poster pr. svar og op til 10 forespørgsler pr. minut.
