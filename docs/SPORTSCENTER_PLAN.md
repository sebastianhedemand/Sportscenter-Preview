# Sportscenter – detaljeret funktions- og integrationsplan

Status: udviklingsspecifikation, ikke en påstand om færdig liveintegration. Designretningen er godkendt. Bevar hele det eksisterende Fodboldcenter og dets `initialData`, browser-backups, Supabase-sync og funktioner.

## Produkt og navigation
- Overblik: kommende kampe, seneste verificerede resultater, datakvalitet, analyser, filtrering og synlig seneste opdatering.
- Fodbold: Superligaen, 1. Division, Bundesliga samt de eksisterende ligaer (Premier League, Championship, League One, Serie A, La Liga).
- Håndbold: Herreligaen, Kvindeligaen, 1. Division herrer, 1. Division damer, tysk Handball-Bundesliga for herrer. Kilde- og turnerings-ID skal bekræftes for hver liga.
- Value Finder: sport/liga/marked, sortering efter beregnet EV, modelversion, bookmaker, observeret odds-tidspunkt og datagrundlag.
- Performance Center: faktiske publicerede tips, vundne/tabte, void/push, hit rate, ROI, filtre på sport/liga/marked/tidsrum, historik og diagrammer.
- Konto, backup, adgangsniveauer og abonnement: eksisterende konto bevares. Betaling aktiveres først efter sikker server-side adgangsstyring.

## Fodbold – bevar og udbyg
- Resultater, kampprogram, tabeller, hold og kampdetaljer; hjemme/ude-opdeling for spillede, scorede og indkasserede mål.
- Over 1,5 / Over 2,5, fair odds, Poisson-model, sandsynlighed, manuel bookmakerodds, EV, værdirangering og Top 10.
- Eksisterende datamodeller og brugerindtastninger må ikke tabes ved redesign eller import.
- Vis antal kampe, sæson, datakilde, seneste synkronisering og datamangler. Brug ikke kunstige bookmakerpriser.

## Håndbold – særskilt model
- Mål for/imod, hjemme/ude, form, mål-totaler, kampvinder, handicap og totals-linjer.
- Markedsspecifik sandsynlighedsberegning og kalibrering på håndboldresultater. Genbrug ikke fodboldens Poisson-parametre ukritisk.
- Korrekt ligaidentitet og sæsonmapping; særskilte dame-/herredivisioner.

## Automatisk dataflow
1. Provider adapter henter fixtures, status, resultater og odds på en server med hemmelige nøgler.
2. Hver kamp matches på stabilt provider-event-ID; navn/dato alene må ikke afgøre automatisk settlement.
3. Valider sport, turnering, sæson, hold, starttidspunkt, score og afsluttet status. Opbevar rå kildereferencer og tidsstempler.
4. Odds lagres append-only med bookmaker, marked, selection, line, decimalodds og observed_at; undgå dubletter.
5. Modelberegning lagrer immutable publicerede prediction snapshots med sandsynlighed, fair odds, tilbudt odds og modelversion.
6. Settlement sker kun for verificeret afsluttede kampe og korrekt marked; void/push håndteres særskilt. Fejl rettes med dokumenteret revisionsspor, ikke skjult omskrivning af tidligere tips.
7. Performance beregnes kun på publicerede, afgjorte forslag med faktiske odds. ROI = samlet profit i units / antal afgjorte 1-unit-spil; hit rate = wins / (wins + losses). Ingen uafgjorte/void i nævneren.
8. Vis tydeligt når kilde er nede, odds er gamle, liga mangler dækning, eller data ikke er verificeret. Manuel fallback bevares.

## Nuværende integrationer og kendte begrænsninger
- `scripts/update_results.py` opdaterer indlejret `initialData` ud fra API-Football for et 7-dages interval. Workflowet `.github/workflows/update-results.yml` er planlagt dagligt kl. 04:30 UTC; dette er ikke live.
- Resultatsynkronisering overskriver ikke længere eksisterende/manuelle scorer. Konflikter og delvist udfyldte scorer sendes til manuel kontrol. Håndboldens browserimport følger samme princip. Regressionstests for disse regler køres i GitHub Actions.
- Eksisterende fodboldodds kommer via en Supabase Edge Function i browserappen, ikke via en fuldt verificeret dækkende odds-pipeline.
- `scripts/test_therundown.py` er en prøveforespørgsel for udvalgte udenlandske ligaer, ikke en aktiv oddsimport.
- SportsEvents24 dansk håndbold-query findes, men tysk Bundesliga-ID, stabilitet, kvoter og rettigheder er ikke endeligt valideret.
- API-Football, Football Soccer API, TheRundown og SportsEvents24 har forskellige dækninger; leverandør, priser og kommercielle rettigheder skal afklares før betalt drift.
- GitHub Pages kan ikke sikkert opbevare hemmelige API-nøgler eller selv være en kontinuerligt kørende live-backend. Brug en server-side funktion/worker og database.

## Dataarkitektur
- `fodboldcenter_supabase_setup.sql`: eksisterende personlige synkroniserede data, beholdes.
- `sportscenter_analytics_schema.sql`: additive tabeller for fixtures, odds snapshots, prediction snapshots, settlements og en aggregeret performance view. SQL er endnu ikke kørt i Supabase.
- Ingen offentlige læse-/skriverettigheder til provider-tabeller før adgangsregler, licenser og abonnementslogik er godkendt.
- Alle udbydernøgler skal ligge i server-side secrets. Rate limits, retries, tidsstempler, logs og alarmer kræves.

## Leverancer og acceptkriterier
**Fase 1 – databevaring og detaljeret UI:** eksisterende ligaer, tabeller, hold, analyser, Over 1,5/2,5, backup og login skal fungere uændret. Responsive visninger testes på mobil/desktop.

**Fase 2 – verificeret automatisering:** hver ønsket liga får dokumenteret provider-ID, antal kampe, oddsmarkeder, kvote, tilladelser og opdateringsfrekvens. Automatisk opdatering testes uden at overskrive manuelle data. Kampstatus og fejlsituationer håndteres.

**Fase 3 – analyse og historik:** separate fodbold-/håndboldmodeller, kalibrering, snapshot-publicering, verificeret settlement, ROI/hit rate og audit trail. Test fixtures inkluderer FT, udsat, aflyst, push, manglende odds og navnekollisioner.

**Fase 4 – betaling:** 1–2 gratis analyser/dag som mulig produktregel; Premium og pris kræver beslutning. Entitlements og betalingswebhooks server-side. Ingen adgangskontrol kun i browser.

**Release:** CI, sikkerhed, datalicenser, historik/migration, mobiltest og ejerens review skal være godkendt før merge til `main`.
