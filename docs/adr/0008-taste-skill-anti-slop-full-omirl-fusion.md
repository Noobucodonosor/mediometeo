# ADR-0008: Fusione Multi-Sensore Completa OMIRL, Refactoring Anti-Slop (`taste-skill 2.5.1`) e Upgrade Smartwatch HUD (`/orologio`)

- **Stato:** Accettato (`Accepted`)
- **Priorità:** P1 — Alta (Completezza Rete Osservativa, Qualità Strumentale UI & Strumentazione Polso)
- **Data:** 2026-11-16
- **Autori:** Daniele (`@Noobucodonosor`) & Antigravity AI
- **Fonti:** Audit UI/UX `design-taste-frontend` (`taste-skill 2.5.1`), API Bulk REST OMIRL Regione Liguria, [`ADR-0007`](./0007-live-omirl-bulk-svg-instrumentation-flagship-ui.md)

---

## 1. Contesto e Problema

Dopo il rilascio dell'ingestione bulk OMIRL e della sala operativa in [`ADR-0007`](./0007-live-omirl-bulk-svg-instrumentation-flagship-ui.md), l'analisi tecnica sul sistema ha individuato tre gap principali da colmare:

1. **Sottoutilizzo delle reti `Termo` e `Pluvio` in `fetch_omirl_live_observations`:**
   - La rete OMIRL nella Provincia di Genova espone non solo 23 stazioni `Vento`, ma anche ~75 termometri (`Termo`) e ~77 pluviometri (`Pluvio`). Limitando `weather_stations` ai soli anemometri, circa 70+ stazioni termo-pluviometriche restavano invisibili sulla mappa e nei pannelli locali.
   - Inoltre, `buoys_live` non esponeva coordinate (`lat`, `lon`), `increment_m` né il riferimento diretto `marine_wave_buoy` per Capo Mele (`BOACM`), e `/api/v1/omirl-chart` restituiva esclusivamente `series` grezzo senza i campi normalizzati attesi dal client (`available`, `unit`, `min_value`, `max_value`, `recent_24_points`).
2. **Residui di "AI-slop" visivo ed emoji decorative nell'interfaccia PWA:**
   - L'uso estensivo di emoji decorative in topbar, Telemetry HUD, schede, card e marker Leaflet abbassava la leggibilità strumentale e violava le linee guida `taste-skill 2.5.1` (`design-taste-frontend`) su gerarchia tipografica (`>= 13px` in Sentence case), target tattili mobile (`>= 44px`), coerenza cromatica (`blue-black-cornflower` senza accenti viola/lavanda) e visualizzazione grafica inline delle serie storiche 24h delle centraline OMIRL.
3. **Vista Smartwatch `/orologio` con coordinate marine statiche e priva di bussola vettoriale:**
   - La vista polso interrogava `/api/v1/marine` puntando staticamente su San Fruttuoso anziché risolvere le coordinate del waypoint di destinazione selezionato, mancava dei controlli rapidi di velocità di crociera e durata dell'uscita e non integrava una bussola nautica SVG vettoriale per vento e moto ondoso.

---

## 2. Decisione Architetturale

1. **Fusione Multi-Sensore Completa OMIRL & Normalizzazione Chart (`TASK-DATA-03` — `backend/engine/omirl_arpal.py`, `backend/main.py`):**
   - **Full Multi-Sensor Fusion (`Vento` + `Termo` + `Pluvio`):**
     - Ogni stazione `Vento` nel bounding box della Provincia di Genova (`44.10 <= lat <= 44.72` e `8.55 <= lon <= 9.56`) traccia i flag granulari `has_live_wind: True`, `has_live_temp: code in termo_by_code`, `has_live_rain: code in pluvio_by_code`.
     - Tutte le restanti stazioni fresche `Termo` e `Pluvio` nel medesimo bounding box (il cui `shortCode` non è già presente in `seen_wind_codes`) vengono aggiunte a `weather_stations` con `sensor: "Termo/Pluvio"`, `has_live_wind: False`, `has_live_temp: bool`, `has_live_rain: bool`, `is_live_rest: True` e fallback al vento misurato dalla stazione `Vento` più vicina (o al vento sinottico di base), portando il parco stazioni esposto a **~90+ centraline reali**.
   - **Boa Ondametrica Capo Mele (`marine_wave_buoy`):**
     - Ogni elemento in `buoys_live` espone `"lat": float(b_item.get("lat") or 43.918)`, `"lon": float(b_item.get("lon") or 8.185)` e `"increment_m": round(float(b_item.get("increment") or 0.0), 2)`.
     - Il payload di `fetch_omirl_live_observations` espone `"marine_wave_buoy": buoys_live[0] if buoys_live else None` e `"total_weather_stations": len(weather_stations)` dentro `live_sensors_count`.
   - **Risposta Normalizzata `/api/v1/omirl-chart`:**
     - `fetch_omirl_station_chart` mantiene `series` (`series_out`) ed estrae `primary_pts = series_out[0]["points"] if series_out else []`, calcolando `available` (`bool(primary_pts)`), `unit` (`{"Vento": "km/h", "Termo": "°C", "Pluvio": "mm", "Idro": "m"}`), `min_value`, `max_value` e `recent_24_points` (`[{"timestamp": p["time_label"], "value": p["value"]}]` sugli ultimi 24 punti).
   - **Invalidazione Cache SQLite:**
     - Il prefisso chiave in `backend/main.py` viene incrementato da `pkg:v2.2:` a `pkg:v2.5:`.

2. **Refactoring Anti-Slop `taste-skill 2.5.1` (`TASK-UX-03` — `frontend/index.html`, `frontend/styles.css`, `frontend/app.js`, `frontend/sw.js`):**
   - Rimozione totale delle emoji decorative da topbar, Telemetry HUD, 6 tab, card e marker Leaflet, sostituite da glifi SVG vettoriali tecnici e badge geometrici/monospazio (`CM`, `QT`, `RD`, `VL`, frecce vento orientate su `(windDeg + 90) % 360`, `IDRO`, `BOA Hs`).
   - Applicazione della palette `blue-black-cornflower`, tipografia `IBM Plex Sans` + `IBM Plex Mono` con `tabular-nums`, etichette in Sentence case `>= 13px` (`0.8125rem`), zero tonalità viola/lavanda e touch target `>= 38px` su desktop / `>= 44px` su mobile (`@media (max-width: 640px)`).
   - Upgrade di `window.inspectOmirlStationChart` per consumare `recent_24_points` e `series?.[0]?.points` renderizzando una **sparkline SVG 24h inline** (`viewBox="0 0 220 48"`) dentro `.omirl-sparkline-box`.
   - Cache PWA aggiornata a `mediometeo-genova-v2.5` con asset `?v=2.5` (mantenendo il riferimento legacy per compatibilità test).

3. **Upgrade Smartwatch HUD `/orologio` (`TASK-WATCH-01` — `frontend/orologio.html`, `tests/test_api_e2e.py`):**
   - Adozione di `blue-black-cornflower` (`#0a0d14` background, `#131824` surface, `#e9edf3` ink, `#8891a1` muted, `#5ab9fc` accent), `IBM Plex Sans` / `IBM Plex Mono`, `tabular-nums`, radius netti `4px/6px` e rimozione delle emoji decorative mantenendo `"MEDIOMETEO HUD"` e `<meta name="color-scheme" content="dark light">`.
   - Introduzione dei controlli numerici `id="watch-speed"` (Crociera kt) e `id="watch-duration"` (Durata min) passati a `/api/v1/route-eta` e lookup dinamico delle coordinate marine del waypoint di destinazione (`watchWaypoints`) per `/api/v1/marine?lat=...&lon=...`.
   - Integrazione della bussola nautica SVG inline `id="watch-svg-compass"` (`viewBox="0 0 180 180"`) con aggiornamento dinamico del vettore vento (`#10b981`) e del vettore onda/swell (`#5ab9fc`).

---

## 3. Conseguenze

- **Positive:**
  - Copertura osservativa provinciale aumentata da ~23 anemometri a **~90+ stazioni reali** integrate sulla mappa e nelle schede locali, distinguendo chiaramente le misure fisiche dirette (`has_live_wind`, `has_live_temp`, `has_live_rain`).
  - Contratto `/api/v1/omirl-chart` auto-sufficiente e privo di disallineamenti tra backend e sparkline UI.
  - Interfaccia Web/PWA e Smartwatch HUD ad altissima leggibilità strumentale, priva di rumore visivo, accessibile su polso e mobile.
- **Trade-off / Vincoli:**
  - La presenza di ~90+ marker sulla mappa richiede badge compatti e differenziati visivamente tra anemometri (`has_live_wind: true`) e stazioni termo-pluviometriche (`has_live_wind: false`) per evitare sovraffollamento visivo.
  - Il cambio di prefisso cache a `pkg:v2.5:` invalida le chiavi cache precedenti al primo avvio garantendo l'immediata disponibilità dei nuovi campi.

---

## 4. Task Operativi Collegati (con Definition of Done)

- [x] **TASK-DATA-03** (`#13`): **Fusione Multi-Sensore Completa OMIRL (`Vento` + `Termo` + `Pluvio` ~90+ stazioni), Boa Capo Mele (`marine_wave_buoy`) e `/api/v1/omirl-chart` Normalizzato**
  - *File coinvolti*: `docs/adr/0008-taste-skill-anti-slop-full-omirl-fusion.md`, `docs/adr/README.md`, `backend/engine/omirl_arpal.py`, `backend/main.py`, `tests/test_omirl_arpal.py`
  - *Acceptance Criteria*:
    - `fetch_omirl_live_observations` traccia `has_live_wind`, `has_live_temp`, `has_live_rain` su tutte le stazioni `Vento` e fonde le stazioni `Termo`/`Pluvio` del bounding box genovese (`sensor: "Termo/Pluvio"`, `has_live_wind: False`, `is_live_rest: True`).
    - `buoys_live` include `lat` (`43.918`), `lon` (`8.185`), `increment_m` e il payload espone `marine_wave_buoy` e `live_sensors_count.total_weather_stations`.
    - `fetch_omirl_station_chart` include `available`, `unit`, `min_value`, `max_value`, `recent_24_points` e `series`.
    - Prefisso cache aggiornato a `pkg:v2.5:` in `backend/main.py`.
  - *Verification Step*: `.venv/bin/pytest tests/test_omirl_arpal.py -v`

- [ ] **TASK-UX-03** (`#14`): **Refactoring Anti-Slop `taste-skill 2.5.1` (`design-taste-frontend`) su UI, Mappa e Sparkline 24h OMIRL**
  - *File coinvolti*: `frontend/index.html`, `frontend/styles.css`, `frontend/app.js`, `frontend/sw.js`
  - *Acceptance Criteria*:
    - Zero emoji decorative in HTML, CSS e JS dinamico/Leaflet; uso esclusivo di SVG tecnici e badge geometrici/monospazio.
    - Tipografia `>= 13px` in Sentence case, `IBM Plex Sans`/`IBM Plex Mono`, `tabular-nums`, zero viola/lavanda, controlli `>= 38px` desktop / `>= 44px` mobile.
    - `inspectOmirlStationChart` renderizza sparkline SVG inline (`viewBox="0 0 220 48"`) dentro `.omirl-sparkline-box`; SW aggiornato a `mediometeo-genova-v2.5`.
  - *Verification Step*: `node --check frontend/app.js && .venv/bin/pytest tests/test_api_e2e.py -v`

- [ ] **TASK-WATCH-01** (`#15`): **Upgrade Smartwatch HUD (`/orologio`) con Palette `blue-black-cornflower`, Controlli Crociera Dinamici e Bussola SVG**
  - *File coinvolti*: `frontend/orologio.html`, `tests/test_api_e2e.py`
  - *Acceptance Criteria*:
    - `frontend/orologio.html` utilizza `IBM Plex Sans`/`IBM Plex Mono`, palette `#0a0d14`/`#131824`/`#5ab9fc`, zero emoji decorative, mantenendo `"MEDIOMETEO HUD"` e `meta name="color-scheme"`.
    - Presenti `watch-speed`, `watch-duration` e `watch-svg-compass` con fetch dinamico delle coordinate marine del waypoint di destinazione.
    - `tests/test_api_e2e.py` valida i nuovi elementi HUD, la versione SW e `live_sensors_count` / `all_weather_stations`.
  - *Verification Step*: `.venv/bin/pytest tests/test_api_e2e.py -v`
