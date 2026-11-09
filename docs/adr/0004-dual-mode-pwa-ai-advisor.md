# ADR-0004: Web App PWA Dual-Mode (Terra/Mare), Mappa Radar/Nautica Interattiva e AI Meteo Advisor (Google Gemini)

- **Stato:** Proposto (`Proposed`)
- **Priorità:** P1 — Alta
- **Data:** 2026-11-09
- **Autori:** Daniele (`@Noobucodonosor`) & Antigravity AI
- **Fonti:** UX/UI operativa per sale meteo e strumentazione di bordo + Google Gemini API (`google-genai`)

---

## 1. Contesto e Problema

Un utente a terra (sotto la pioggia a Genova o in partenza per l'entroterra) e un utente in mare (in pozzetto su una barca a vela a Portofino o in uscita dalla Diga Foranea di Genova) hanno bisogno di un'interfaccia immediata, leggibile anche sotto il sole o di notte, che mostri subito:
1. **Cosa sta succedendo adesso e nei prossimi 180 minuti (Nowcast Radar + Timeline 15 min)**;
2. **Cosa succederà nelle prossime 24h-7 giorni con il confronto tra modelli (AROME vs ICON-D2 vs ECMWF)**;
3. **Una sintesi esperta in linguaggio naturale** che spieghi *perché* il tempo sta cambiando (es. *"Attenzione: attivazione della convergenza tra Tramontana Scura in uscita dalla Val Polcevera e Scirocco sul Levante; previsto rinforzo improvviso a 28 nodi fuori dalla Diga Foranea e rovesci intensi sul Bisagno"*).

---

## 2. Decisione Architetturale

### 2.1. Interfaccia Web App Responsive & PWA Dual-Mode (`frontend/`)
Costruiamo una Single Page Application / PWA ad alte prestazioni:
- **Switch Istantaneo `MODALITÀ TERRA` vs `MODALITÀ MARE`:**
  - In **Modalità TERRA**: focus su intensità pioggia (`mm/h`), radar precipitazioni, cumulate idrogeologiche sui torrenti (Bisagno, Polcevera, Entella), vento in `km/h`, avvisi viabilità (es. Sopraelevata / Autostrade liguri), temperatura percepita, umidità, CAPE e stato Allerta ARPAL.
  - In **Modalità MARE**: focus nautico con vento e raffiche in **nodi (`kt`)** e **Scala Beaufort**, altezza onda significativa ($H_s$) e massima ($H_{max}$) in **metri**, **periodo d'onda ($T_p$ in secondi)**, direzione onda/swell con bussola vettoriale, **Scala Douglas**, temperatura dell'acqua (SST), pressione barometrica ($\text{hPa}$ con freccia di tendenza 3h) e semaforo operativo per **Vela/Diporto**, **Pesca**, **Kayak/SUP** e **Sicurezza Ormeggi**.
- **Mappa Interattiva Multi-Layer (Leaflet + Radar Nowcasting + Marker Distretti Terra/Boe Mare):**
  - Layer Radar Precipitazioni live animato (ultime 2h + nowcast radar RainViewer).
  - Marker cliccabili per tutti i distretti Terra e i settori Mare della Provincia di Genova, con possibilità di cliccare **qualsiasi punto sulla mappa** (in mare o nell'entroterra) per ottenere il Nowcast + Forecast puntuale di quelle coordinate esatte.
- **Grafici Multi-Modello Interattivi (Chart.js):**
  - Confronto visivo diretto tra **Consensus MedioMeteo**, **AROME (1.3 km)**, **ICON-D2 (2.2 km)** ed **ECMWF (9 km)** per capire subito se i modelli sono concordi o se c'è incertezza.

### 2.2. AI Meteo & Marine Advisor (`backend/engine/ai_advisor.py`)
- Integrazione del pacchetto ufficiale **`google-genai`** (modello `gemini-2.5-flash`) alimentato con il JSON strutturato del motore fisico (dati osservati, convergenza ligure, spread tra AROME/ICON-D2/ECMWF, stato del mare e allerte).
- **Prompt Specializzato Meteo-Marino Ligure:** Gemini agisce come **Previsore Meteo-Marino Senior esperto di Genova e del Mar Ligure**, generando due sezioni distinte:
  1. **Analisi Sinottica & Nowcast Locale** (con focus su Tramontana Scura, Scirocco, Libeccio, temporali V-shaped).
  2. **Briefing Operativo Terra & Mare** (consigli pratici per chi si muove a Genova/vallate e per chi naviga tra Arenzano, Porto di Genova, Golfo Paradiso, Portofino e Tigullio).
- **Fallback Deterministico Esperto:** Se `GEMINI_API_KEY` non è impostata nel file `.env` o la chiamata AI non è disponibile, un generatore sinottico deterministico basato su regole meteorologiche liguri produce comunque un bollettino tecnico completo e strutturato al 100%.

---

## 3. Conseguenze

- **Positive:**
  - Esperienza d'uso di livello professionale ("Sala Operativa Meteo-Marina") accessibile da smartphone, tablet di bordo o desktop.
  - Funzionamento garantito sia con `GEMINI_API_KEY` attiva sia in modalità autonoma deterministica.
- **Trade-off / Vincoli:**
  - I bollettini AI vengono messi in cache SQLite per 15 minuti per distretto/modalità così da garantire risposte istantanee e contenere i costi API.

---

## 4. Task Operativi Collegati (con Definition of Done)

- [ ] **TASK-AI-01**: **Implementazione AI Meteo-Marine Advisor con Google Gemini (`google-genai`) e motore sinottico deterministico di fallback**
  - *File coinvolti*: `backend/engine/ai_advisor.py`, `backend/main.py`, `tests/test_ai_advisor.py`
  - *Acceptance Criteria*:
    - Genera bollettini strutturati Terra e Mare specifici per la Provincia di Genova e il Golfo Ligure.
    - Usa `google-genai` quando `GEMINI_API_KEY` è configurata e passa automaticamente al generatore esperto deterministico in assenza di chiave o errore rete.
  - *Verification Step*: `pytest tests/test_ai_advisor.py -v`
- [ ] **TASK-UI-01**: **Sviluppo Web App Responsive + PWA Dual-Mode (Terra/Mare) con Mappa Radar/Nautica Leaflet, Meteogrammi Multi-Modello e Pannello Allerte/Consigli**
  - *File coinvolti*: `frontend/index.html`, `frontend/styles.css`, `frontend/app.js`, `frontend/manifest.json`, `frontend/sw.js`, `tests/test_api_e2e.py`
  - *Acceptance Criteria*:
    - Switch fluido tra Modalità Terra (`km/h`, `mm/h`, rischio idrogeologico vallate) e Modalità Mare (`nodi`, `Beaufort`, `Douglas`, periodo d'onda `s`, `H_s`/`H_max`, consigli navigazione).
    - Mappa interattiva centrata su Genova e Golfo Ligure con overlay Radar live e click su qualsiasi punto a terra o in mare.
    - Superamento di tutti i test E2E e del controllo `pre_release_check.py`.
  - *Verification Step*: `pytest -v && python3 ~/.gemini/config/skills/adr-github-methodology/scripts/pre_release_check.py`
