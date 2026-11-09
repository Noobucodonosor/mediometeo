# ADR-0005: Catalogo Geografico Granulare (67 Comuni + 25 Quartieri + Rade), Rete Osservativa Reale OMIRL (Sensori, Idrometri, Webcam) e Bollettini Ufficiali ARPAL

- **Stato:** Accettato (`Accepted`)
- **Priorità:** P1 — Alta
- **Data:** 2026-11-09
- **Autori:** Daniele (`@Noobucodonosor`) & Antigravity AI
- **Fonti:** Allineamento `/grill-me` (Decisioni #1, #4, #5, #6, #9, #10, #11) + Report Archeologia Forense (`ORO-1`, `ORO-2`, `ORO-8`)

---

## 1. Contesto e Problema

Dal processo di allineamento bottom-up (`/grill-me`) e dall'indagine archeologica sui cantieri precedenti (`meteo`, `supermeteo`, `genova`) sono emersi quattro requisiti architetturali non negoziabili:
1. **Granularità Territoriale Totale sulla Provincia di Genova:** L'utente deve poter cercare, filtrare e cliccare su mappa **tutti i 67 Comuni della Città Metropolitana di Genova**, i **25 Quartieri/Municipi di Genova città** (Voltri, Pra', Pegli, Sestri Ponente, Cornigliano, Sampierdarena, Rivarolo, Bolzaneto, Pontedecimo, Castelletto, Centro Storico/Porto Antico, Carignano, Foce, Albaro, San Fruttuoso, Marassi, Staglieno, Molassana, Struppa, San Martino, Quarto, Quinto, Nervi, ecc.), oltre alle **Rade, Porti, Capi e Cale costiere** e ai **Valichi Appenninici**.
2. **Separazione Netta tra "Osservato Adesso (Verità Strumentale)" e "Previsione Modelli":** I dati rilevati dai sensori fisici non devono mai essere confusi o mescolati silenziosamente con i modelli matematici.
3. **Integrazione Diretta delle API REST JSON di OMIRL Regione Liguria + Webcam Live:** Invece di fare scraping HTML fragile o cablare una sola stazione, il backend deve interrogare le API REST ufficiali di `omirl.regione.liguria.it` (`/Omirl/rest/stations/{Tipo}`) per **Pluviometri, Anemometri, Termometri, Idrometri dei Torrenti** (Bisagno, Polcevera, Entella, Lavagna, Stura, Scrivia, Trebbia, Aveto), **Boe Ondametriche** e **Webcam Live**, mostrando sempre nome stazione, distanza in km dal punto selezionato e minuto esatto del rilievo.
4. **Confronto 5 Modelli Ora-per-Ora + Bollettini Ufficiali ARPAL:** Oltre a `AROME 1.3km`, `ICON-D2 2km`, `ECMWF IFS 9km` e `GFS`, va integrato anche **MET Norway (`api.met.no`)** come quinto membro di confronto indipendente, insieme al parser deterministico `extractVarData` per i bollettini ufficiali **ARPAL Liguria** (`bollettino-liguria.html` e `bollettino-mare.html`).

---

## 2. Decisione Architetturale

1. **Catalogo Geografico Unificato (`backend/locations.py`)**:
   - Censimento strutturato di **oltre 110 località selezionabili** nella Provincia di Genova:
     - **67 Comuni** ufficiali della Città Metropolitana di Genova (con coordinate verificate, altitudine, bacino/vallata e zona ARPAL);
     - **25 Quartieri urbani di Genova**;
     - **20 Rade, Porti, Cale e Capi marittimi** (con angolo di apertura della cala `bay_open_deg` per il calcolo fisico della risacca e dello swell);
     - **Valichi Appenninici chiave** (Passo dei Giovi, Passo del Turchino, Passo della Scoffera, Passo del Bocco, Passo della Forcella).
   - Esposizione tramite `GET /api/v1/locations` con ricerca testuale istantanea, filtro per categoria/vallata e ricerca geodetica Haversine per coordinate GPS o click su mappa.

2. **Connettore REST Nativo OMIRL & ARPAL (`backend/engine/omirl_arpal.py`)**:
   - Interrogazione asincrona con circuit-breaker degli endpoint REST JSON di OMIRL Regione Liguria:
     - Sensori real-time (`Vento`, `Pluvio`, `Termo`, `Idro`, `Boa`, `Igro`, `Press`) filtrati sul dominio della Provincia di Genova e ordinati per distanza Haversine dal punto attivo;
     - Catalogo **Webcam Live (`webcam`)** con immagine in tempo reale per il Nowcast visivo ("Occhio sul Territorio e sul Mare");
     - Serie storica ultime 3 ore (`/Omirl/rest/charts/{shortCode}/{Tipo}`) per il calcolo del trend reale misurato.
   - Parser brace-matcher deterministico (`extract_var_data`) per estrarre l'oggetto JSON `var data = {...}` incorporato nelle pagine ufficiali ARPAL (`bollettino-liguria.html` e `bollettino-mare.html`).
   - Integrazione del 5° modello **MET Norway (`api.met.no/weatherapi/locationforecast/2.0/compact`)** nel motore di confronto ora-per-ora.

---

## 3. Conseguenze

- **Positive:**
  - Copertura capillare di ogni singolo comune, quartiere, torrente e cala della Provincia di Genova.
  - Verità strumentale (stazioni, idrometri, boe, webcam) completamente distinta dalle previsioni modellistiche.
- **Trade-off / Vincoli:**
  - I dati OMIRL e ARPAL vengono cachati in SQLite con TTL breve (3 min per stazioni/webcam, 15 min per bollettini ARPAL) e dotati di fallback strutturato sulle stazioni di riferimento genovesi qualora il portale regionale avesse latenze.

---

## 4. Task Operativi Collegati (con Definition of Done)

- [x] **TASK-GEO-01**: **Implementazione catalogo geografico completo della Provincia di Genova (67 Comuni + 25 Quartieri di Genova + 20 Rade/Porti/Capi + Valichi) e ricerca geodetica**
  - *File coinvolti*: `backend/locations.py`, `backend/main.py`, `tests/test_locations_catalog.py`
  - *Acceptance Criteria*:
    - Tutti i 67 Comuni della Città Metropolitana di Genova, i 25 Quartieri di Genova e i 20 punti costieri/rade sono interrogabili via `/api/v1/locations`.
    - Ogni rada/cala include l'angolo di esposizione (`bay_open_deg`) e il ridosso per i calcoli fisici marini.
  - *Verification Step*: `.venv/bin/pytest tests/test_locations_catalog.py -v`
- [x] **TASK-OBS-01**: **Implementazione connettore nativo OMIRL (Stazioni, Idrometri Torrenti, Boe, Webcam Live), Parser Bollettini Ufficiali ARPAL e 5° modello MET Norway**
  - *File coinvolti*: `backend/engine/omirl_arpal.py`, `backend/engine/connectors.py`, `backend/engine/ensemble.py`, `tests/test_omirl_arpal.py`
  - *Acceptance Criteria*:
    - Separazione netta nel payload API tra `observations_live` (sensori OMIRL con distanza km e timestamp + webcam vicine) e `forecast_models` (`AROME`, `ICON-D2`, `ECMWF`, `GFS`, `MET.no`).
    - Il parser `extract_var_data` estrae correttamente i bollettini ARPAL Terra e Mare.
  - *Verification Step*: `.venv/bin/pytest tests/test_omirl_arpal.py -v`
