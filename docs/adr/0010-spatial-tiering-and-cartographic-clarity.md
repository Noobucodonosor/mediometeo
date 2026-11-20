# ADR-0010: Spatial Tiering & Cartographic Clarity per la Rete OMIRL (199 Sensori)

- **Stato:** Proposed
- **Data:** 2026-11-20
- **Autori:** Daniele Bertuccio, Antigravity
- **Issue Collegate:** [#23](https://github.com/Noobucodonosor/mediometeo/issues/23), [#24](https://github.com/Noobucodonosor/mediometeo/issues/24)

---

## 1. Contesto e Problema

Al caricamento iniziale della mappa (zoom regionale Golfo Ligure / Città Metropolitana di Genova), `/api/v1/observations` restituisce tutti i 199 sensori OMIRL senza gerarchia spaziale e `frontend/app.js` li renderizza tutti come etichette testuali simultanee. Il risultato è un muro di badge sovrapposti che degrada leggibilità ed estetica.

## 2. Decisione Architetturale

1. **Backend (`TASK-MM-BE-01`, #23):**
   - Introdurre `display_tier` (`1` = ~14 stazioni cardine + idrometri principali + boa; `2` = rete intermedia; `3` = tutti i 199 sensori) e `severity` (`normal | watch | alert`) in `backend/engine/omirl_arpal.py` e `/api/v1/observations`.
   - I sensori in stato `watch` o `alert` ricevono promozione automatica a qualsiasi livello di zoom.
2. **Frontend (`TASK-MM-FE-01`, #24):**
   - Rendering zoom-aware su Leaflet: a zoom iniziale solo `tier 1` e `watch/alert` mostrano etichette numeriche; gli altri sensori sono micro-dot compatti (4–6 px) cliccabili.
   - `tier 2` emerge da zoom ≥ 11, `tier 3` da zoom ≥ 13.
   - Toolbar layer compatta e traslucida + desaturazione leggera della basemap per far risaltare i dati reali.

## 3. Conseguenze

- Tutti i 199 sensori restano accessibili senza perdere precisione scientifica, ma l'impatto visivo al primo caricamento diventa pulito e leggibile su desktop e mobile.
- Retrocompatibilità garantita sui test `pytest` esistenti (campi additivi nel payload JSON).
