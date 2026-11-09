# ADR-0001: Architettura Core, Zonizzazione Provincia di Genova (Terra/Mare) e Stack Tecnologico

- **Stato:** Accettato (`Accepted`)
- **Priorità:** P1 — Alta (Baseline Architetturale)
- **Data:** 2026-11-09
- **Autori:** Daniele (`@Noobucodonosor`) & Antigravity AI
- **Fonti:** Requisiti di progetto MedioMeteo Genova (Forecast + Nowcast ad alta risoluzione per Terra e Mare)

---

## 1. Contesto e Problema

La **Provincia di Genova** e il prospiciente **Golfo Ligure** presentano una delle configurazioni meteo-marine più complesse del Mediterraneo:
1. **Orografia estrema a pochissimi chilometri dal mare:** L'Appennino Ligure sale oltre i 1000-1800 m a ridosso della linea di costa, innescando fenomeni di sbarramento orografico, *Genova Low* (ciclogenesi secondaria sottovento alle Alpi) e la celebre **convergenza tra Tramontana Scura** (che trabocca dai passi dei Giovi/Turchino lungo Val Polcevera e Val Bisagno) e **Scirocco/Ostro** caldo-umido dal Mar Ligure.
2. **Esigenze distinte ma interconnesse per Terra e Mare:**
   - **Chi è a Terra** necessita di: nowcasting precipitativo su base 5-15 minuti (intensità mm/h, stazionarietà dei temporali V-shaped), rischio idrogeologico per vallata, raffiche di vento di caduta (burrasca di Tramontana/Grecale), visibilità in valico e stato di Allerta ARPAL (Zona B e Zona C/D/E).
   - **Chi è in Mare** (diportisti, pescatori, operatori portuali, sport acquatici) necessita di: vento medio e raffica in **nodi (kt)** e **scala Beaufort**, direzione/altezza d'onda significativa ($H_s$) e onda massima ($H_{max}$), **periodo di picco ($T_p$)** e direzione dello *swell* (Libeccio lungo vs onda corta da vento locale di Tramontana), temperatura superficiale del mare (SST) e avvisi di burrasca **Meteomar**.

I portali meteo generalisti falliscono sistematicamente su Genova perché usano modelli globali a bassa risoluzione (>9-25 km) che non "vedono" i crinali liguri né la linea di convergenza.

---

## 2. Decisione Architetturale

Adottiamo un'architettura modulare **FastAPI (Backend Asincrono) + SQLite Cache + PWA Dual-Mode (Frontend)**:

### 2.1. Zonizzazione Micro-Climatica e Marittima della Provincia di Genova
Il sistema struttura nativamente la Provincia di Genova in **distretti operativi preconfigurati** (oltre a supportare qualsiasi coordinata GPS libera `lat, lon`):

**Distretti TERRA (con riferimento Zone di Allerta ARPAL B, C, D, E):**
- `GE-CENTRO-PONENTE`: Genova Centro, Porto Antico, Sampierdarena, Pegli, Voltri (Zona B)
- `GE-VAL-POLCEVERA`: Rivarolo, Bolzaneto, Pontedecimo, Passo dei Giovi (Zona B — corridoio Tramontana Scura)
- `GE-VAL-BISAGNO`: Marassi, Staglieno, Molassana, Struppa, Bargagli (Zona B — bacino critico idrogeologico)
- `GE-LEVANTE`: Nervi, Golfo Paradiso (Recco, Camogli), Tigullio (Rapallo, Santa Margherita, Portofino, Chiavari, Sestri Levante) (Zona B / Zona C)
- `GE-ENTROTERRA`: Valle Scrivia (Busalla, Ronco), Val Trebbia (Torriglia), Val d'Aveto (Santo Stefano d'Aveto), Valle Stura (Campo Ligure, Masone) (Zone D / E / C)

**Distretti MARE (Costa e Largo del Golfo di Genova):**
- `MARE-PORTO-DIGA`: Avamporto di Genova, Diga Foranea, Canale di Calma di Prà (`0-2 NM` dalla costa)
- `MARE-GOLFO-PONENTE`: Arenzano – Voltri – Capo Mele (`0-6 NM`)
- `MARE-GOLFO-PARADISO-PORTOFINO`: Nervi – Camogli – Punta Chiappa – Promontorio di Portofino (`0-6 NM`)
- `MARE-TIGULLIO`: Golfo del Tigullio – Sestri Levante – Punta Manara (`0-6 NM`)
- `MARE-LARGO-LIGURE`: Alto Mar Ligure / Al largo di Genova (`>12 NM`, area Boa ODAS / corridoio Corsica)

### 2.2. Stack Tecnologico e Modello Dati
1. **Backend (`backend/`)**:
   - Python 3.11+, `FastAPI`, `httpx` per chiamate concorrenti non bloccanti (`asyncio.gather`) verso tutte le sorgenti dati.
   - Database `SQLite` locale (`data/mediometeo.sqlite`, escluso da Git) per caching intelligente con TTL differenziato:
     - **Nowcast & Radar/Stazioni/Boe:** TTL `3 minuti` (aggiornamento ad alta frequenza).
     - **Forecast LAM Multi-Modello:** TTL `30 minuti`.
     - **Bollettini AI & Allerte:** TTL `15 minuti`.
2. **API RESTful principali**:
   - `GET /api/v1/districts` — Elenco distretti Terra e Mare della Provincia di Genova con metadati e soglie.
   - `GET /api/v1/nowcast?district=<id>&lat=<lat>&lon=<lon>` — Stato osservato real-time + proiezione 0-180 minuti (pioggia, radar, vento, onde, pressione).
   - `GET /api/v1/forecast?district=<id>&mode=land|sea` — Previsione oraria e 7 giorni multi-modello pesata con bande di confidenza.
   - `GET /api/v1/alerts` — Allerte ARPAL Liguria + Avvisi di Burrasca Meteomar + Indice di Rischio Calcolato Terra/Mare.
   - `GET /api/v1/ai-bulletin?district=<id>&mode=land|sea` — Bollettino sinottico esperto generato da Gemini (con fallback deterministico).

---

## 3. Conseguenze

- **Positive:**
  - Copertura granulare dell'intera Città Metropolitana di Genova (dal largo del Mar Ligure fino ai 1800 m della Val d'Aveto).
  - Tempi di risposta API `< 150ms` grazie alla cache SQLite con refresh asincrono.
  - Zero dipendenza da pesanti database esterni in fase di avvio: il progetto parte con un singolo comando.
- **Trade-off / Vincoli:**
  - Richiede una normalizzazione rigorosa delle unità di misura (`km/h` e `mm/h` per la modalità Terra; `nodi (kt)`, `Beaufort`, `metri` e `secondi` di periodo d'onda per la modalità Mare).

---

## 4. Task Operativi Collegati (con Definition of Done)

- [ ] **TASK-CORE-01**: **Setup struttura progetto Python/FastAPI, configurazione distretti Genova Terra/Mare e database cache SQLite**
  - *File coinvolti*: `requirements.txt`, `.env.example`, `backend/__init__.py`, `backend/config.py`, `backend/districts.py`, `backend/cache.py`, `backend/main.py`
  - *Acceptance Criteria*:
    - Tutti i distretti Terra e Mare della Provincia di Genova sono censiti con coordinate, batimetria/altitudine e zona di allerta ARPAL.
    - Il database SQLite gestisce il salvataggio e il recupero con TTL senza errori.
    - L'endpoint `GET /api/v1/health` e `GET /api/v1/districts` rispondono con HTTP 200.
  - *Verification Step*: `pytest tests/test_core_districts.py -v`
