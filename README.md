# MedioMeteo Genova

Piattaforma full-stack di **Nowcasting (0–3h)** e **Forecasting (7 giorni)** ad alta risoluzione per la **Città Metropolitana di Genova (67 comuni, Terra)** e il **Golfo Ligure (Mare)**, sviluppata con metodologia **ADR-Driven**.

## Funzionalità Principali
- **Copertura geografica granulare:** 67 comuni della provincia di Genova, 25 quartieri cittadini e rade costiere.
- **Ingestione dati reali OMIRL & ARPAL:** 199 sensori reali liguri (stazioni meteo, idrometri, webcam) + modelli LAM ad alta risoluzione (AROME 1.3 km, ICON-D2 2 km, ECMWF, Open-Meteo Marine).
- **Modalità Dual-Mode (Terra / Mare):**
  - *Terra:* pioggia mm/h, vallate, criticità idrogeologiche e viabilità.
  - *Mare:* fisica costiera (nodi, onda $H_s$/$H_{\max}$, periodo, risacca, maree, correnti), calcolatore rotta ETA e modalità compact HUD (`/orologio`).
- **Resilienza & Sicurezza:** gestione API key via `.env`, circuit breaker sui connettori esterni, cache SQLite con TTL e test automatici (`pytest`).

## Stack Tecnologico
- **Backend:** Python, FastAPI, SQLite, Async HTTP connectors, `pytest`
- **Frontend:** Progressive Web App (PWA) responsive, mappe interattive e quadranti SVG vettoriali
- **Architettura & Governance:** 10 Architecture Decision Records in [`docs/adr/README.md`](./docs/adr/README.md)

## Avvio Locale
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
```
