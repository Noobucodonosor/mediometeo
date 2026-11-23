# ADR-0012: CI/CD Pipeline, Deterministic Contract Testing & Browser Gate

- **Stato:** Proposto (`Proposed`)
- **Priorità:** P1 — Alta
- **Data:** 2026-11-21
- **Autori:** `@Noobucodonosor`, Antigravity
- **Fonti:** Audit multifocale read-only (2026-11-21), `tests/test_api_e2e.py`, `Dockerfile`, `.github/`

---

## 1. Contesto e Problema

Il repository non dispone ancora di una pipeline CI/CD (`.github/workflows/` è assente) e la suite `tests/test_api_e2e.py` esegue chiamate di rete live verso Open-Meteo, MET.no, ARPAL e OMIRL:
- In caso di degradazione di un provider esterno, i fallback sintetici possono far passare i test mascherando rotture dei parser reali.
- Il `Dockerfile` usa `python:3.12-slim` mentre `requirements.txt` fissa versioni generate in un ambiente locale Python 3.14, senza verifica automatizzata di build.
- I test frontend verificano solo sottostringhe HTML tramite `TestClient(app)` senza eseguire `frontend/app.js` o `frontend/orologio.html` in un browser.

---

## 2. Decisione Architetturale

1. **CI Pipeline Automatizzata (`TASK-CICD-01`):**
   - Creare `.github/workflows/ci.yml` su push/PR verso `main` con:
     1. Esecuzione `pre_release_check.py` (verifica assenza segreti e conformità repo).
     2. Esecuzione `pytest -m "not live"` in ambiente completamente offline.
     3. Verifica build container `docker build .` su `python:3.12-slim`.
2. **Contract Testing Deterministico Offline (`TASK-QA-01`):**
   - Introdurre fixture JSON/HTML reali storicizzate in `tests/fixtures/` per Open-Meteo, MET Norway, OMIRL e ARPAL.
   - Separare i test contract deterministici (default in CI) dai test di integrazione live (`@pytest.mark.live`) eseguibili on-demand.
   - Integrare uno smoke check headless browser (opzionale in CI / gate pre-release) per intercettare errori JS console su `index.html` e `orologio.html`.

---

## 3. Conseguenze

- **Positive:** regressioni su parser, timezone, sicurezza e compatibilità `requirements.txt` su `python:3.12-slim` vengono intercettate prima del merge.
- **Trade-off / Vincoli:** le fixture in `tests/fixtures/` devono essere aggiornate quando i payload upstream (OMIRL/ARPAL/Open-Meteo) cambiano formato.

---

## 4. Task Operativi Collegati (con Definition of Done)

- [x] **TASK-CICD-01**: **GitHub Actions CI Pipeline (`pytest` offline, `pre_release_check.py`, `docker build`)**
  - *File coinvolti*: `.github/workflows/ci.yml`, `requirements.txt`, `Dockerfile`
  - *Acceptance Criteria*: workflow verde su PR/push; `docker build` completa su `python:3.12-slim`; `pre_release_check.py` eseguito ad ogni run.
  - *Verification Step*: `python3 ~/.gemini/config/skills/adr-github-methodology/scripts/pre_release_check.py && docker build -t mediometeo:ci .`
- [x] **TASK-QA-01**: **Deterministic Offline Contract Tests & Separazione Live Suite (`@pytest.mark.live`)**
  - *File coinvolti*: `pyproject.toml` / `pytest.ini`, `tests/fixtures/*`, `tests/test_api_e2e.py`, `tests/`
  - *Acceptance Criteria*: `.venv/bin/pytest -m "not live"` passa al 100% senza accesso internet e senza dipendere da cache SQLite preesistente.
  - *Verification Step*: `.venv/bin/pytest -v -m "not live"`
