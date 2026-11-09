# AGENTS.md — Contesto & Linee Guida per Agenti AI e Sviluppatori

> **REGOLA AUREA (MANDATORY):**
> Prima di modificare l'architettura, toccare il modello dati, aggiungere endpoint o sviluppare nuove feature, **DEVI leggere [`docs/adr/README.md`](./docs/adr/README.md)** e gli ADR specifici nella cartella [`docs/adr/`](./docs/adr/).

---

## 1. Panoramica del Progetto

- **Nome Progetto:** `MedioMeteo Genova` (`mediometeo`)
- **Repository:** `Noobucodonosor/mediometeo`
- **Descrizione Sintetica:** Piattaforma ad alta precisione di **Nowcasting (0-3h)** e **Forecasting (fino a 7 giorni)** per la **Provincia di Genova e il Golfo Ligure**, progettata con doppia modalità operativa **Terra** (allerte idrogeologiche, convergenza Tramontana Scura / Scirocco, microclimi vallate e costa) e **Mare** (moto ondoso, periodo d'onda, mareggiata, vento di burrasca, boe al largo e sottocosta).
- **Stack Tecnologico:**
  - **Backend:** Python 3.11+ con **FastAPI**, `httpx` (async), `pydantic`, `apscheduler` (polling asincrono fonti meteo).
  - **Frontend:** **Web App Responsive + PWA** (HTML5, CSS3 Moderno / Glassmorphism Dark UI, JavaScript ES6+, **Leaflet.js** per mappa interattiva radar/stazioni/vento/onde, **Chart.js** per meteogrammi multi-modello).
  - **Database & Cache:** **SQLite** (serie storiche osservazioni stazioni/boe, cache intelligente con TTL differenziato e storico bollettini AI).
  - **Fonti Dati Meteo & Marine:**
    1. **Open-Meteo Multi-Model & Marine API:** `ICON-D2` (2 km), `AROME` (1.3 km — fondamentale per la convergenza ligure), `ECMWF IFS` (9 km), `GFS` + `Open-Meteo Marine` (onde, swell, periodo).
    2. **Dati Osservativi Liguria & Radar Nowcasting:** Rete stazioni e boe regionali (OMIRL / ARPAL / DPC), Radar precipitazioni real-time (RainViewer / mosaico radar Monte Settepani).
    3. **Bollettini Ufficiali:** Allerta Meteo Liguria (ARPAL) e **Meteomar** (Aeronautica Militare — Settore Mar Ligure).
    4. **Provider Commerciali (Plugin con API Key opzionali):** Tomorrow.io, WeatherAPI, Stormglass.io, Windy API (con graceful fallback automatico se la chiave non è presente in `.env`).
  - **AI Engine:** **Google Gemini API (`google-genai`)** per sintesi sinottica locale, spiegazione dei fenomeni tipici genovesi (es. *Genova Low*, convergenza sulla Val Polcevera/Bisagno, rischio mareggiata o burrasca per diportisti) e raccomandazioni operative Terra/Mare.

---

## 2. Mappa dei File Principali

| File / Cartella | Ruolo |
| :--- | :--- |
| [`docs/adr/README.md`](./docs/adr/README.md) | **Indice degli ADR**, diagramma architetturale Mermaid e **Master Task Backlog**. |
| [`docs/adr/0001-core-architecture.md`](./docs/adr/0001-core-architecture.md) | Architettura Core, Zonizzazione Provincia di Genova (Terra/Mare) e Stack Tecnologico. |
| [`docs/adr/0002-security-resilience-apikeys.md`](./docs/adr/0002-security-resilience-apikeys.md) | Sicurezza, gestione API Keys (`.env`), Rate Limiting, Resilienza & Disclaimer Sicurezza Incolumità. |
| [`docs/adr/0003-multi-model-nowcast-forecast-engine.md`](./docs/adr/0003-multi-model-nowcast-forecast-engine.md) | Motore di Fusione Ensemble (AROME + ICON-D2 + ECMWF) e Nowcasting Radar/Stazioni/Boe. |
| [`docs/adr/0004-dual-mode-pwa-ai-advisor.md`](./docs/adr/0004-dual-mode-pwa-ai-advisor.md) | Web App PWA Dual-Mode (Terra/Mare), Mappa Interattiva e Bollettino Smart Google Gemini. |
| `.github/ISSUE_TEMPLATE/` | Template standard per l'apertura di GitHub Issues (`adr_task.yml`, `bug_report.yml`). |
| `backend/main.py` | Entrypoint FastAPI, routing API (`/api/v1/forecast`, `/api/v1/nowcast`, `/api/v1/marine`, `/api/v1/ai-bulletin`) e static serving PWA. |
| `backend/engine/` | Connettori multi-sorgente, algoritmo di consenso/fusione e calcolo indici di rischio Terra/Mare. |
| `frontend/` | Interfaccia Web/PWA (`index.html`, `app.js`, `styles.css`, `manifest.json`, `sw.js`). |
| `tests/` | Suite di test `pytest` per connettori, motore di fusione, sicurezza e API. |

---

## 3. Metodologia di Lavoro (ADR + GitHub Issues)

1. **Ogni decisione architetturale o di sicurezza** è documentata in un file `docs/adr/NNNN-titolo.md`.
2. **Ogni task operativo** ha un codice univoco (`TASK-<MODULO>-XX`) censito sia nell'ADR di origine, sia in `docs/adr/README.md`, sia come **GitHub Issue**.
3. **Priorità Standard:**
   - `P0-critical`: Sicurezza, protezione API keys, resilienza anti-crash durante eventi meteo estremi, disclaimer ufficiali.
   - `P1-high`: Motore core Nowcast/Forecast Terra e Mare, integrazione modelli LAM (AROME/ICON-D2), UI Dual-Mode.
   - `P2-medium`: Connettori commerciali opzionali, AI Advisor Gemini, PWA offline mode e ottimizzazioni.
4. **Sviluppo & Commit Atomici:**
   - Lavora su un `TASK-<MODULO>-XX` alla volta.
   - Esegui sempre il **Verification Step** (test/check) previsto nella GitHub Issue prima di concludere.
   - Usa messaggi di commit che referenziano il Task ID e chiudono automaticamente la Issue su GitHub:
     ```bash
     git commit -m "feat(TASK-XXX-01): descrizione sintetica della modifica (closes #N)"
     ```

---

## 4. Sicurezza & Regole Critiche

- **Mai committare segreti:** Il file `.env` e i database locali (`*.db`, `*.sqlite`) devono restare sempre in `.gitignore`. Ogni sviluppatore usa le proprie chiavi (`GEMINI_API_KEY`, `TOMORROW_API_KEY`, `STORMGLASS_API_KEY`, `WEATHERAPI_KEY`, `WINDY_API_KEY`) in `.env`.
- **Verifica Pre-Release:** Prima di generare pacchetti di deploy o fare push di rilascio, esegui:
  ```bash
  python3 ~/.gemini/config/skills/adr-github-methodology/scripts/pre_release_check.py
  ```

---

## 5. Comandi Rapidi di Sviluppo e Test

```bash
# Avvio ambiente di sviluppo locale
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Esecuzione test end-to-end / unit test
pytest -v

# Lista GitHub Issues attive per priorità
gh issue list --limit 30
```
