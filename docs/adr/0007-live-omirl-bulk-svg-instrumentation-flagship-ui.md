# ADR-0007: Ingestione Massiva Bulk REST OMIRL (199 Sensori Reali Liguri) e UI Strumentale "Biglietto da Visita" (Compact HUD, Mappa Full-Canvas Vettoriale & Quadranti SVG)

- **Stato:** Accettato (`Accepted`)
- **Priorità:** P0 — Critica (Qualità Dati & Esperienza Utente "Flagship")
- **Data:** 2026-11-09
- **Autori:** Daniele (`@Noobucodonosor`) & Antigravity AI

---

## 1. Contesto e Problema

Per rendere **MedioMeteo Genova** un autentico "biglietto da visita" d'eccellenza sia sul piano dei dati sia sul piano del design UX/UI, l'audit sul prodotto ha evidenziato due aree decisive di salto qualitativo:

1. **Dati Osservativi OMIRL al 100% Reali su Tutta la Rete Provinciale (Zero Valori Stimati quando il Sensore Esiste):**
   - L'API REST ufficiale di Regione Liguria (`https://omirl.regione.liguria.it/Omirl/rest/stations/{Tipo}`) restituisce in tempo reale l'intero parco sensori regionale con un singolo JSON per tipologia:
     - `Vento` (58 stazioni regionali, di cui **23 nella Provincia di Genova** con velocità reale in `km/h` in `value` e direzione in gradi in `increment`: `GEPOA` Porto Antico, `CFUNZ` Centro Funzionale, `RIGHI` Castellaccio, `GECER` Certosa, `STILA` Sant'Ilario, `AREPO` Arenzano Porto, `PTURC` Passo del Turchino, `MOPEN` Monte Pennello, `FFRES` Fontana Fresca, `CAMOG` Camogli, `MTPOR` Monte Portofino, `SMARG` Santa Margherita, `LAVPO` Lavagna Porto, `TOGAR` Torriglia, `TANOR` Ronco Scrivia, `MTECA` Monte Cappellino, `MTMEZ` Santo Stefano d'Aveto, ecc.);
     - `Termo` (**75 termometri reali** nella Provincia di Genova);
     - `Pluvio` (**77 pluviometri reali** nella Provincia di Genova);
     - `Idro` (**24 idrometri fluviali reali** sui torrenti genovesi: `FIRPO` Bisagno Firpo, `GEMOL` Bisagno Molassana, `LAPRS` Bisagno La Presa, `GEFER` Fereggiano, `GERIV` Polcevera Rivarolo, `GEPTX` Polcevera Pontedecimo, `GEGEI` Geirato, `VAREN` Varenna Granara, `GSTUR` Sturla, `PANES` Entella Panesi, `CARPB` Lavagna Ponte Birago, `CAMPL` Stura Campo Ligure, `VOBBI` Vobbietta, `MONTG` Scrivia Montoggio, `ROVPT` Trebbia Rovegno, `CABAN` Aveto Cabanne, `SLPSS` Petronio Sestri Levante);
     - `Boa` (**Boa Ondametrica Capo Mele** `BOACM` come sentinella reale del moto ondoso di Libeccio sul Mar Ligure) + `webcam` (`PANES` Entella Panesi con frame fotografico reale ospitato su `https://omirl.regione.liguria.it/{imgPath}`).
   - Interrogando in parallelo questi 6 endpoint bulk (con cache in-memory/SQLite di 120 secondi e filtro di freschezza su `refDate` per scartare sensori fuori servizio come `CHIRI` fermo al 2023), ogni stazione sulla mappa e nella Scheda `1. 📡 ADESSO` mostra **esclusivamente la misura fisica reale al minuto**.

2. **Architettura Visiva & Strumentale da "Sala Operativa / Strumento Nautico Flagship":**
   - **Eliminazione del "muro di testo e bottoni" superiore:** Sostituzione dei 4 blocchi impilati con una **Topbar + HUD Telemetry Strip unificata** che mostra istantaneamente (anche mentre si esplora la Mappa Live!) i 5 indicatori vitali del punto attivo: `🌡️ Temp & Percepita`, `💨 Vento (kt + km/h + Freccia Direzione + Nome Ligure)`, `🌊 Onda Hs / Hmax @ Tp + Risacca`, `🌧️ Pioggia 1h / Cumulata 24h`, `🧭 Pressione hPa + Consenso 5 Modelli`.
   - **Mappa Full-Canvas con Overlay Glassmorphism e Pin Vettoriali:** I controlli dei layer (`🌧️ Radar`, `💨 Vento OMIRL Reale`, `🌊 Idrometri Reali`, `🏛️ Località`, `📷 Webcam`, `⚓ AMP`) e il player temporale del radar devono fluttuare sopra la mappa in pannelli semitrasparenti, mentre i sensori del vento mostrano **frecce vettoriali orientate secondo i gradi reali misurati (`wind_dir_deg`)**.
   - **Quadranti Strumentali SVG Dinamici (`Compass & Bay Surge Radar` + `River Gauge Bars`):**
     - Un vero **Quadrante Nautico SVG** che disegna la Rosa dei Venti Ligure, il vettore del vento reale, il vettore dello Swell marino e il **cono geometrico di apertura della cala (`bay_open_deg`)**, rendendo immediatamente visibile l'angolo di impatto della risacca.
     - Barre idrometriche graduate per i 24 idrometri reali con indicatore grafico rispetto alle soglie di guardia/allarme.
     - Integrazione diretta del **Grafico Ufficiale Real-Time OMIRL** (`/Omirl/rest/charts/{shortCode}/{Sensor}`) o link diretto al sensore al click su qualsiasi stazione reale.

---

## 2. Decisione Architetturale

1. **Motore Bulk Live OMIRL (`backend/engine/omirl_arpal.py`)**:
   - Implementazione di `fetch_omirl_bulk_all_sensors(client)` che scarica in parallelo `Vento`, `Termo`, `Pluvio`, `Idro`, `Boa` e `webcam` da `omirl.regione.liguria.it/Omirl/rest/stations/{Tipo}`, applica un controllo di validità temporale su `refDate` (ultime 48h), fonde per `shortCode`/coordinate i sensori multi-parametro e restituisce le stazioni reali misurate con flag `is_live_rest = True` e URL immagine reale per le webcam OMIRL (`https://omirl.regione.liguria.it/{imgPath}`).
   - Nuovo endpoint `GET /api/v1/omirl-chart?code={shortCode}&sensor={Vento|Pluvio|Termo|Idro}` per ispezionare la serie storica reale delle ultime 24h misurata da una specifica centralina OMIRL.

2. **Redesign UX/UI "Flagship Telemetry & SVG Instrumentation" (`frontend/index.html`, `frontend/styles.css`, `frontend/app.js`)**:
   - **Compact Telemetry HUD Strip**: barra strumentale ad alto contrasto sempre visibile sotto la topbar.
   - **Mappa Full-Viewport con Controlli Flottanti & Frecce Vettoriali del Vento Reale**.
   - **Widget SVG Rosa dei Venti Ligure + Cono Apertura Cala (`bay_open_deg`) + Vettori Vento/Onda**.
   - **Modal / Ispettore Serie Storica Centralina OMIRL** e barre graduate per i livelli idrometrici dei torrenti.

---

## 3. Task Operativi Collegati (con Definition of Done)

- [x] **TASK-DATA-02**: **Ingestione Massiva Bulk REST OMIRL (23 Anemometri, 75 Termometri, 77 Pluviometri, 24 Idrometri Reali, Boa Capo Mele e Webcam OMIRL con filtro freschezza `refDate`) + Endpoint Serie Storica Centralina (`/api/v1/omirl-chart`)**
  - *File coinvolti*: `backend/engine/omirl_arpal.py`, `backend/main.py`, `tests/test_omirl_arpal.py`
  - *Acceptance Criteria*:
    - Il connettore interroga in parallelo tutti i 6 endpoint `/Omirl/rest/stations/{Vento,Termo,Pluvio,Idro,Boa,webcam}`, scarta i sensori obsoleti (`refDate` > 48h) e popola `observations_live` con le vere letture al minuto della rete regionale.
    - L'endpoint `/api/v1/omirl-chart` restituisce la serie storica reale di qualsiasi centralina OMIRL selezionata.
  - *Verification Step*: `.venv/bin/pytest tests/test_omirl_arpal.py -v`

- [x] **TASK-UX-02**: **Redesign "Biglietto da Visita": Telemetry HUD Strip Sempre Visibile, Mappa Full-Canvas con Overlay Flottanti & Frecce Vento, Quadrante SVG Rosa dei Venti / Cono Risacca Cala e Barre Idrometriche**
  - *File coinvolti*: `frontend/index.html`, `frontend/styles.css`, `frontend/app.js`, `tests/test_api_e2e.py`
  - *Acceptance Criteria*:
    - Header compatto + Telemetry HUD Strip sempre visibile con i 5 KPI vitali (`Temp`, `Vento kt/kmh`, `Onda Hs/Hmax @ Tp`, `Pioggia`, `Pressione`).
    - Mappa Live con controlli layer e player radar flottanti dentro il canvas e frecce orientate del vento reale.
    - Quadrante grafico SVG per Rosa dei Venti + Cono di apertura della cala (`bay_open_deg`) + barre graduate per gli idrometri dei torrenti.
  - *Verification Step*: `.venv/bin/pytest -v && python3 ~/.gemini/config/skills/adr-github-methodology/scripts/pre_release_check.py`
