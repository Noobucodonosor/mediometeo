# ADR-0013: Esperienza v4.0 Full-Screen Map-First (Windy / Apple Maps) & AI Contestuale (`POST /api/v1/ask`)

- **Stato:** Accettato (`Accepted`)
- **Priorità:** P0 — Critica (Qualità Prodotto & Usabilità)
- **Data:** 2026-11-21
- **Autori:** `@Noobucodonosor`, Antigravity
- **Fonti:** Sessione `/grill-me` (2026-11-21), `backend/main.py`, `backend/engine/ai_advisor.py`, `frontend/`

---

## 1. Contesto e Problema

Nonostante il motore meteorologico/oceanografico (`AROME`, `ICON-D2`, `ECMWF`, `GFS`, `MET Norway`, 199 sensori OMIRL, fisica costiera pura, sicurezza `ADR-0011`) fosse solido e testato, l'interfaccia precedente a 6 tab risultava ancora percepita come una console tecnica densa e non immediata per utenti finali e condivisione rapida.

---

## 2. Decisione Architetturale

1. **Interfaccia Full-Screen Mappa-Prima (`100dvh × 100vw`):**
   - Eliminazione della topbar fissa multi-controllo, della barra a 6 tab e dell'HUD superiore permanente.
   - Una sola pillola di ricerca flottante in alto a sinistra (`118 località + preferiti 1-tap + GPS`).
   - Rail verticale destro compatto stile Windy con **1 solo layer attivo alla volta** (`Vento` | `Radar` | `Onde` | `Stazioni`), più `Rotta`, toggle tema `Chiaro`/`Scuro` e collegamento `/orologio`.
2. **Cartografia Chiara di Default + Rilevamento Automatico Terra/Mare:**
   - Default chiaro `CartoDB Voyager` + layer nautico `OpenSeaMap` + base vettoriale Liguria offline di fallback, con toggle opzionale scuro (`CartoDB Dark Matter`).
   - La modalità `Terra` o `Mare` viene selezionata automaticamente in base al punto cliccato/cercato.
3. **Bottom Sheet a 3 Livelli Progressivi (`peek` / `medium` / `expanded`):**
   - *Peek:* pillola compatta (`Località · Temp · Vento`).
   - *Medium:* sintesi sinottica in 2 frasi + 4 metriche essenziali + timeline oraria scorrevole 24h + campo discreto **`POST /api/v1/ask`**.
   - *Expanded:* confronto 5 modelli + divergenza, meteogrammi Chart.js, stazioni OMIRL con sparkline 24h, idrometri e bollettino ARPAL.
4. **Rotta Costiera Visibile Live sulla Mappa & Deploy 1-Comando:**
   - Il pannello `Rotta` traccia direttamente polilinea, waypoint numerati e distanze sulla mappa con `fitBounds`.
   - Aggiunto script `scripts/deploy_cloudrun.sh` per deploy HTTPS pubblico su Cloud Run.

---

## 3. Conseguenze

- **Positive:** app immediatamente leggibile nei primi 5 secondi su desktop e mobile, zero ridondanze, AI utile e verificabile sul punto selezionato, mantenimento integrale dei contratti API esistenti.
- **Trade-off / Vincoli:** i test E2E frontend (`tests/test_api_e2e.py`) vengono aggiornati alla struttura v4.0.

---

## 4. Task Operativi Collegati

- [x] **TASK-UX-V4-01**: **Endpoint `POST /api/v1/ask` grounded sui dati live & Rate Limiting**
- [x] **TASK-UX-V4-02**: **Riscrittura Clean-Slate Frontend v4.0 Full-Screen Map + Bottom Sheet 3-Stati + Script Cloud Run**
