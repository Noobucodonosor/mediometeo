# ADR-0002: Sicurezza, Gestione API Keys, Resilienza Anti-Blackout e Disclaimer Incolumità

- **Stato:** Accettato (`Accepted`)
- **Priorità:** P0 — Critica
- **Data:** 2026-11-09
- **Autori:** Daniele (`@Noobucodonosor`) & Antigravity AI
- **Fonti:** Standard di sicurezza `adr-github-methodology` + Requisiti di alta affidabilità per sistemi di monitoraggio meteo-marino

---

## 1. Contesto e Problema

Un sistema di **Nowcasting e Forecasting per Terra e Mare** presenta due superfici critiche di rischio:
1. **Sicurezza Informatica e Protezione API Keys Commerciali:** L'integrazione di Google Gemini (`GEMINI_API_KEY`) e provider meteo commerciali (`TOMORROW_API_KEY`, `STORMGLASS_API_KEY`, `WEATHERAPI_KEY`, `WINDY_API_KEY`) espone al rischio di leak di credenziali nel codice client o esaurimento quota per abusi / scraping.
2. **Continuità Operativa durante Eventi Estremi (Allerta Rossa / Mareggiata):** Durante un'alluvione lampo a Genova o una burrasca sul Mar Ligure, singole API esterne possono andare in timeout o restituire errori HTTP 5xx. Il sistema **non deve mai andare in crash** o mostrare schermate vuote quando gli utenti a terra o in mare cercano informazioni urgenti. Inoltre, deve sempre esporre chiaramente la **freschezza del dato (`data_age_seconds`)** e il **disclaimer ufficiale** che rimanda alla Protezione Civile / ARPAL e alla Guardia Costiera (1530).

---

## 2. Decisione Architetturale

1. **Zero Secret Exposure sul Frontend:**
   - Tutte le chiavi API risiedono esclusivamente nel file `.env` lato server e vengono caricate tramite `backend/config.py`.
   - Il frontend interroga unicamente il backend locale (`/api/v1/...`), senza mai ricevere chiavi di terze parti.
2. **Architettura "Graceful Degradation" & Stale-While-Revalidate:**
   - Ogni connettore meteo esterno ha un timeout rigido (`6.0 secondi`) e gestione eccezioni isolata: se un provider fallisce o una chiave commerciale non è configurata in `.env`, il motore prosegue con i provider attivi (Open-Meteo Multi-Model, ARPAL/OMIRL, RainViewer, Meteomar).
   - Se tutte le reti esterne sono temporaneamente irraggiungibili, il backend serve l'ultimo snapshot valido dalla cache SQLite marcandolo con `is_stale: true` e `stale_warning: "Dati in cache — connessione live temporaneamente degradata"`.
3. **Validazione Input & Coordinate Geografiche (Geofencing Ligure):**
   - Le richieste per coordinate libere (`lat, lon`) sono validate rigorosamente dentro il bounding box del dominio Ligure/Genovese (`lat: 43.50..45.00`, `lon: 7.50..10.20`) per prevenire abusi del proxy API su scala globale.
4. **Tracciabilità Freschezza Dati e Disclaimer di Sicurezza in Mare/Terra:**
   - Ogni risposta API include `generated_at`, `sources_active`, `sources_degraded` e `safety_disclaimer` (con riferimenti ufficiali Allerta Liguria e Guardia Costiera 1530).

---

## 3. Conseguenze

- **Positive:**
  - L'applicazione funziona al 100% anche con zero chiavi commerciali configurate (usando lo stack scientifico Open-Meteo LAM + Radar + Stazioni/Boe Liguria) e si arricchisce automaticamente appena si inseriscono le chiavi in `.env`.
  - Protezione totale contro il leak di segreti verificata da `pre_release_check.py`.
- **Trade-off / Vincoli:**
  - Le richieste fuori dal dominio geografico della Liguria/Alto Tirreno vengono rifiutate con HTTP `422 Unprocessable Entity`.

---

## 4. Task Operativi Collegati (con Definition of Done)

- [x] **TASK-SEC-01**: **Hardening configurazione `.env`, geofencing coordinate Liguria, circuit-breaker con fallback cache e validazione `pre_release_check.py`**
  - *File coinvolti*: `backend/config.py`, `backend/security.py`, `.env.example`, `tests/test_security_resilience.py`
  - *Acceptance Criteria*:
    - Nessuna chiave API presente nel codice sorgente o esposta dagli endpoint API.
    - Richieste con coordinate fuori dal dominio Ligure restituiscono HTTP 422.
    - In caso di errore simulato di un provider esterno, l'API risponde comunque con HTTP 200 usando i provider superstiti o il fallback cache marcato `is_stale`.
  - *Verification Step*: `pytest tests/test_security_resilience.py -v && python3 ~/.gemini/config/skills/adr-github-methodology/scripts/pre_release_check.py`
