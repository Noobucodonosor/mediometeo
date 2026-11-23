# ADR-0011: Frontend & API Security Hardening (XSS Escaping, Input Validation, Rate Limiting, Single-Flight & CSP/SRI)

- **Stato:** Proposto (`Proposed`)
- **Priorità:** P0 — Critica
- **Data:** 2026-11-21
- **Autori:** `@Noobucodonosor`, Antigravity
- **Fonti:** Audit multifocale read-only (2026-11-21), `ADR-0002`, `backend/main.py`, `backend/engine/connectors.py`, `frontend/app.js`, `frontend/index.html`

---

## 1. Contesto e Problema

L'audit AppSec & Reliability del 2026-11-21 ha individuato diverse vulnerabilità e gap rispetto ai requisiti di `ADR-0002`:
1. **XSS DOM (`frontend/app.js`):** oltre 20 assegnazioni `.innerHTML` interpolano stringhe provenienti da API esterne (`ARPAL`, `OMIRL`, `Gemini`, `cam.live_image_url`, `location.name`) senza escaping HTML. Inoltre `frontend/index.html` contiene un handler inline `onclick="window.switchTab('tab-mappa')"`.
2. **Path/URL Manipulation & Exception Disclosure (`/api/v1/omirl-chart`):** il parametro `code` è validato solo per lunghezza (`min_length=2, max_length=12`) senza regex alfanumerica, ed eventuali errori espongono `{exc}` grezzo al client (`HTTP 502`).
3. **Trasporto & Browser Hardening:** `CORSMiddleware` è aperto (`allow_origins=["*"]`), gli script/CSS CDN (`Leaflet`, `Chart.js`) non hanno attributi `integrity` (SRI), e mancano header di sicurezza (`CSP`, `X-Content-Type-Options`, `X-Frame-Options`).
4. **Abuso Risorse, Thundering Herd & Bug Cache Key:**
   - `/api/v1/ai-bulletin` (che invoca `GEMINI_API_KEY`) e `?refresh=true` non hanno rate limiting per IP.
   - `b_key` in `/api/v1/ai-bulletin` omette la longitudine (`lon`), causando collisioni di cache.
   - `_load_or_compute_weather_package` e `_OMIRL_BULK_CACHE` mancano di single-flight lock (`asyncio.Lock`).
   - Il Circuit Breaker (`N=3` errori / cooldown `T=5m`) previsto da `ADR-0002` non è implementato in `backend/engine/connectors.py`.

---

## 2. Decisione Architetturale

1. **Frontend XSS & DOM Hardening (`TASK-SEC-02`):**
   - Introdurre un helper `escapeHtml(str)` (o costruzione DOM tramite `textContent` / `createElement`) su tutte le interpolazioni esterne in `frontend/app.js` e validare gli URL immagine (`https://` / `http://`) per le webcam.
   - Rimuovere tutti gli event handler inline (`onclick=...`) da `frontend/index.html` sostituendoli con `addEventListener` in `app.js`.
2. **API Input Validation, SRI & Security Headers (`TASK-SEC-03`):**
   - Applicare regex strict `^[A-Za-z0-9_-]{2,12}$` al parametro `code` di `/api/v1/omirl-chart` e restituire messaggi di errore sanitizzati (loggando il dettaglio internamente).
   - Aggiungere `integrity` (SRI) e `crossorigin="anonymous"` ai tag CDN (`Leaflet`, `Chart.js`) in `frontend/index.html`.
   - Aggiungere middleware FastAPI per `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy` e rendere `CORS` configurabile via `Settings` (default restrittivo in produzione).
3. **Rate Limiting, Single-Flight, Cache Key Fix & Circuit Breaker (`TASK-SEC-04`):**
   - Introdurre rate limiting per IP (es. sliding-window in-memory / `slowapi`) su `/api/v1/ai-bulletin` e sul parametro `?refresh=true`.
   - Includere `lon` nella cache key `b_key` di `/api/v1/ai-bulletin`.
   - Introdurre `asyncio.Lock` per `cache_key` (single-flight) in `_load_or_compute_weather_package` e su `_OMIRL_BULK_CACHE`.
   - Implementare il Circuit Breaker (`N=3` fallimenti consecutivi → apertura `T=5 min`) in `backend/engine/connectors.py` come previsto da `ADR-0002`.

---

## 3. Conseguenze

- **Positive:** eliminazione della superficie XSS DOM, protezione quota `GEMINI_API_KEY`, prevenzione thundering herd e allineamento effettivo a `ADR-0002`.
- **Trade-off / Vincoli:** una `CSP` rigorosa vieta script/handler inline nel frontend; il rate limiting su `?refresh=true` richiede soglie calibrate per non ostacolare il normale cambio località rapido dell'utente.

---

## 4. Task Operativi Collegati (con Definition of Done)

- [x] **TASK-SEC-02**: **Frontend XSS & DOM Hardening (`escapeHtml` e rimozione handler inline)**
  - *File coinvolti*: `frontend/app.js`, `frontend/index.html`, `tests/`
  - *Acceptance Criteria*: nessuna interpolazione non escapata di dati esterni in `.innerHTML`; zero `onclick=` inline in `index.html`; test automatizzati con payload XSS `<script>` / `onerror=`.
  - *Verification Step*: `.venv/bin/pytest -v`
- [x] **TASK-SEC-03**: **API Input Validation (`/api/v1/omirl-chart`), SRI CDN & Security Headers/CORS**
  - *File coinvolti*: `backend/main.py`, `backend/config.py`, `frontend/index.html`, `tests/`
  - *Acceptance Criteria*: `code` rifiuta caratteri speciali (`422`); errori `502` senza stack/eccezione raw; SRI presente sui CDN; header `CSP`, `X-Content-Type-Options`, `X-Frame-Options` verificati via test.
  - *Verification Step*: `.venv/bin/pytest -v`
- [x] **TASK-SEC-04**: **Rate Limiting, Single-Flight Lock, Fix Cache Key `ai-bulletin` & Circuit Breaker**
  - *File coinvolti*: `backend/main.py`, `backend/engine/connectors.py`, `backend/engine/omirl_arpal.py`, `tests/`
  - *Acceptance Criteria*: `b_key` include `lat` e `lon`; richieste concorrenti sulla stessa `cache_key` eseguono un solo fetch upstream; `429` su abuso `/api/v1/ai-bulletin` o `?refresh=true`; circuit breaker apre dopo 3 errori e si richiude dopo cooldown.
  - *Verification Step*: `.venv/bin/pytest -v`
