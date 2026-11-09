# ADR-0006: Fisica Costiera Pura (Zero Semafori in Mare, Risacca, Maree, Correnti), Architettura UX "Map-First" a 6 Schede Chiuse e Calcolatore Rotta ETA / Smartwatch

- **Stato:** Accettato (`Accepted`)
- **Priorità:** P1 — Alta
- **Data:** 2026-11-09
- **Autori:** Daniele (`@Noobucodonosor`) & Antigravity AI
- **Fonti:** Allineamento `/grill-me` (Decisioni #2, #3, #7, #8, #12, #13, #14, #15) + Report Archeologia Forense (`ORO-3`, `ORO-4`, `ORO-5`, `ORO-6`)

---

## 1. Contesto e Problema

Dall'intervista `/grill-me` sono emerse regole di dominio e di interfaccia nette che distinguono `MedioMeteo Genova` da qualsiasi altra web app meteo:
1. **Asimmetria Filosofica Voluta tra MARE e TERRA:**
   - **In Modalità MARE ("Zero Semafori Consiglio"):** Chi va per mare non vuole semafori soggettivi ("esci / non uscire") che decidono al posto suo senza conoscere barca ed equipaggio. Vuole **tutti i parametri fisici puri al massimo dettaglio**: vento in `kt`, `km/h` e `m/s`, raffiche, Beaufort, altezza d'onda significativa ($H_s$), onda massima ($H_{max}$), onda da vento ($H_{wind}$) separata dallo swell ($H_{swell}$), periodo di picco ($T_p$), lunghezza d'onda ($L$), ripidità ($H/L$ in %), grado Douglas, **curva di marea (`HIGH`/`LOW` da `sea_level_height_msl`)**, **indice fisico di risacca/rifrazione nelle cale** (in metri equivalenti a riva e angolo d'impatto), **corrente superficiale in nodi**, visibilità in **Miglia Nautiche (NM)** e il testo integrale ufficiale **Meteomar / ARPAL Mare**.
   - **In Modalità TERRA ("Fisica + Indicatori Operativi Urbani/Vallivi"):** A terra, oltre ai dati fisici puri (pioggia, temperatura percepita Humidex/Windchill, punto di rugiada, UV, radiazione, inversione termica/Maccaja), l'utente **vuole anche gli indicatori calcolati dall'app** per rischio sottopassi/allagamenti, livelli idrometrici dei torrenti, raffiche su Sopraelevata Aldo Moro / Ponte San Giorgio / Viadotti A7-A10-A12-A26 e stato dei valichi appenninici (rischio gelicidio, neve, nebbia).
2. **Architettura UX a 6 Schede Chiuse con `3. 🗺️ MAPPA LIVE` Aperta di Default e Transizione Istantanea a `1. 📡 ADESSO`:**
   - L'interfaccia deve mostrare **una sola scheda attiva alla volta** (zero pagina infinita caotica) articolata in **6 Schede Chiuse**:
     1. `1. 📡 ADESSO (Sensori Reali OMIRL, Idrometri & Webcam Live)`
     2. `2. ⏱️ NOWCAST 0-3h & FISICA (Terra o Mare)`
     3. `3. 🗺️ MAPPA LIVE (Radar Player, Sensori, Webcam, 67 Comuni, 25 Quartieri, Rade & AMP)` — **Scheda aperta di default all'ingresso!**
     4. `4. 📊 FORECAST & MODELLI (Grafici + Tabella Comparativa Ora-per-Ora AROME / ICON-D2 / ECMWF / GFS / MET.no + 7 Giorni)`
     5. `5. 🧭 ROTTA, ETA & SMARTWATCH (Calcolatore Nautico su Grafo Costiero Golfo di Genova / AMP)`
     6. `6. 📜 BOLLETTINI (ARPAL Ufficiale, Meteomar & Analisi Sinottica AI Pura)`
   - **Comportamento al Click su Mappa:** Quando l'utente nella Scheda 3 (`🗺️ MAPPA LIVE`) clicca un Comune, un Quartiere, una Rada, un Sensore o un punto qualsiasi sulla mappa, l'app seleziona quella località e **passa automaticamente alla Scheda 1 (`1. 📡 ADESSO`)**, mostrando immediatamente i sensori reali più vicini, le webcam e lo stato attuale di quel punto.
3. **Calcolatore Pubblico di Rotta Costiera / ETA & Vista Smartwatch (`/orologio`):**
   - Grafo nautico costiero su tutto il Golfo di Genova (Arenzano, Voltri, Genova Porto Antico, Boccadasse, Nervi, Recco, Camogli, Punta Chiappa, San Fruttuoso, Portofino, Paraggi, Santa Margherita, Rapallo, Zoagli, Chiavari, Sestri Levante) che non taglia mai i promontori via terra, rispetta i limiti di velocità dell'AMP Portofino (Zona A vietata, Zona B max 5 kt, Zona C max 7-10 kt), calcola miglia nautiche, nodi richiesti, soste bagno, orario limite di rientro (*Turnaround Time*), confronto meteo Andata vs Ritorno e vista compatta da polso (`/orologio`).

---

## 2. Decisione Architetturale

1. **Motore Fisico Costiero Puro (`backend/engine/marine.py` & `backend/engine/coastal_route.py`)**:
   - Rimozione di qualsiasi "semaforo consiglio" soggettivo (`activities_safety` green/yellow/red) dal payload e dalla UI della modalità Mare.
   - Aggiunta dell'estrattore maree `extract_tides_from_sea_level()`, del calcolo fisico di rifrazione/risacca `compute_bay_surge_physics()` (basato sull'angolo tra `swell_dir_deg` e `bay_open_deg`, amplificato da `swell_period_s` e dalla fase di marea) e della corrente superficiale (`ocean_current_velocity_knots`, `ocean_current_dir_deg` + corrente di promontorio).
   - Endpoint `GET /api/v1/route-eta` per il calcolo di rotta costiera su grafo di Dijkstra marittimo tra qualsiasi coppia/sequenza di approdi del Golfo di Genova, con profilo meteo-marino di andata vs ritorno.
2. **Frontend Single-Tab "Map-First" (`frontend/index.html`, `frontend/app.js`, `frontend/styles.css`) + Vista Smartwatch (`/orologio`)**:
   - Barra a 6 Schede Chiuse mutuamente esclusive con `tab-map` attiva all'avvio.
   - Al click su un marker o punto della mappa, selezione istantanea del punto e switch automatico a `tab-now` (`1. 📡 ADESSO`).
   - Endpoint dedicato `/orologio` (e modalità compatta integrata nella Scheda 5) ottimizzato per schermi da polso (Smartwatch 200×260px+) con bussola, ETA, nodi richiesti, onda $H_s/T_p$ e vento reale.

---

## 3. Conseguenze

- **Positive:**
  - Rispetto rigoroso della filosofia "Fisica pura in Mare / Fisica + Indicatori operativi a Terra".
  - Zero sovraccarico visivo grazie alle 6 Schede Chiuse con ingresso immediato sulla Mappa Live.

---

## 4. Task Operativi Collegati (con Definition of Done)

- [x] **TASK-PHY-01**: **Rifattorizzazione motore Marino (Zero Semafori, Spettro Onda Completo, Maree, Risacca Fisica di Rade/Cale, Correnti, Visibilità NM) e Calcolatore Rotta Costiera / ETA (`coastal_route.py`)**
  - *File coinvolti*: `backend/engine/marine.py`, `backend/engine/coastal_route.py`, `backend/engine/ai_advisor.py`, `backend/main.py`, `tests/test_coastal_physics_route.py`
  - *Acceptance Criteria*:
    - Il motore marino restituisce tutti i parametri fisici puri (kt, km/h, m/s, Hs, Hmax, Hwind, Hswell, Tp, L, ripidità %, Douglas, Beaufort, maree HIGH/LOW, risacca fisica in metri e corrente in nodi) senza semafori-consiglio soggettivi.
    - Il grafo costiero calcola distanze in NM senza tagliare il Promontorio di Portofino, rispetta i limiti AMP e confronta le condizioni fisiche Andata vs Ritorno.
  - *Verification Step*: `.venv/bin/pytest tests/test_coastal_physics_route.py -v`
- [x] **TASK-UX-01**: **Sviluppo Frontend a 6 Schede Chiuse ("Map-First" con switch automatico a `1. 📡 ADESSO`), Player Radar, Webcam Live, Ispettore 5 Modelli Ora-per-Ora e Vista Smartwatch (`/orologio`)**
  - *File coinvolti*: `frontend/index.html`, `frontend/styles.css`, `frontend/app.js`, `frontend/orologio.html`, `tests/test_api_e2e.py`
  - *Acceptance Criteria*:
    - All'apertura del sito è attiva esclusivamente la Scheda `3. 🗺️ MAPPA LIVE`; cliccando un punto/comune/rada sulla mappa si passa automaticamente alla Scheda `1. 📡 ADESSO`.
    - Tutte le 6 schede chiuse e la vista `/orologio` sono funzionanti e testate end-to-end.
  - *Verification Step*: `.venv/bin/pytest -v && python3 ~/.gemini/config/skills/adr-github-methodology/scripts/pre_release_check.py`
