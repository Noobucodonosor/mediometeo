# ADR-0003: Motore di Fusione Multi-Modello (Ensemble LAM) e Nowcasting Terra/Mare

- **Stato:** Accettato (`Accepted`)
- **Priorità:** P1 — Alta
- **Data:** 2026-11-09
- **Autori:** Daniele (`@Noobucodonosor`) & Antigravity AI
- **Fonti:** Fisica dell'atmosfera ligure (convergenza AROME/ICON-D2), idrologia ARPAL/OMIRL e oceanografia operativa Mar Ligure

---

## 1. Contesto e Problema

Per offrire **"il meglio"** su Genova sia a terra sia in mare, non basta leggere un singolo modello meteorologico:
- **Su Genova e vallate (0-36h):** Il modello francese **Météo-France AROME (risoluzione 1.3 km)** e il tedesco **DWD ICON-D2 (2.2 km)** sono gli unici modelli non-idrostatici a scala convettiva in grado di risolvere i temporali autorigeneranti V-shaped sul Mar Ligure e la linea di convergenza tra Tramontana Scura (che esce da Val Polcevera) e Scirocco (che risale dal Golfo Paradiso/Tigullio).
- **Sul Medio Termine (3-7 giorni):** Il modello europeo **ECMWF IFS (9 km)** offre la migliore affidabilità sinottica sul posizionamento della *Genova Low*.
- **In Mare (Golfo di Genova e Mar Ligure):** Serve combinare il modello d'onda (altezza significativa $H_s$, altezza d'onda da vento $H_{wind}$, swell primario $H_{swell}$, periodo d'onda $T_p$, direzione) con il vento reale a 10m e le raffiche in nodi, calcolando un **Indice di Navigabilità e Sicurezza in Mare** (distinguendo tra onda lunga di Libeccio con periodo $>7-8\text{ s}$ e onda corta ripida e frangente da Tramontana/Grecale con periodo $3-5\text{ s}$).
- **Nel Nowcasting (0-3 ore):** Serve integrare l'ultimo frame radar precipitativo (RainViewer / mosaico radar DPC Monte Settepani), i dati osservati dalle stazioni/boe liguri, la tendenza barometrica ($\Delta P / 3\text{h}$) e il profilo a 15 minuti.

---

## 2. Decisione Architetturale

Realizziamo un motore a due stadi in `backend/engine/`:

### 2.1. Algoritmo di Fusione Multi-Modello ("Ligurian Weighted Ensemble")
Per ogni punto/distretto della Provincia di Genova, il backend interroga in parallelo:
1. **AROME HD (1.3 km)** — Peso `0.45` nelle prime 36h per precipitazioni, raffiche di vento e convergenza locale.
2. **ICON-D2 / ICON-EU (2.2 km)** — Peso `0.35` nelle prime 48h per precipitazioni convettive, CAPE e vento orografico.
3. **ECMWF IFS (9 km)** — Peso `0.20` nelle prime 48h e peso `0.70` oltre le 48h (giorni 3-7).
4. **GFS + Provider Commerciali opzionali** (Tomorrow.io / WeatherAPI / Stormglass se presenti in `.env`) — Peso dinamico di calibrazione e calcolo dello **spread di incertezza** (`confidence_score` da 0 a 100%).

> **Regola Conservativa di Sicurezza (Peak Preservation):**
> Per le **raffiche di vento** e i **picchi di precipitazione estrema** su Genova, oltre alla media pesata viene calcolato il `max_model_warning`: se AROME o ICON-D2 vede un picco di pioggia $>30\text{ mm/h}$ o raffiche $>35\text{ kt}$ che il modello globale liscia via, il sistema mantiene in evidenza il picco del modello ad altissima risoluzione (LAM) per non sottostimare mai un evento estremo locale.

### 2.2. Diagnostica Meteo-Marina Specifica per Genova (`ligurian_diagnostics.py`)
Il motore calcola automaticamente indicatori specialistici per Genova:
1. **Rilevatore di Convergenza Ligure (Tramontana Scura vs Scirocco):**
   Analizza il gradiente termico e di direzione del vento tra il settore di Ponente/Val Polcevera ($330^\circ-020^\circ$, aria più fredda) e il settore di Levante/Golfo ($120^\circ-170^\circ$, aria mite e umida). Se attivo, innalza l'allerta di **Temporale Autorigenerante Stazionario**.
2. **Indice Operativo TERRA (`land_risk`):**
   - Stress Pluviometrico & Idrogeologico (basato su cumulata 1h/3h/12h e soglie dei bacini Bisagno, Polcevera, Entella).
   - Rischio Vento Forte urbano/valichi (soglie limitazioni moto/telonati Sopraelevata Aldo Moro e viadotti A7/A10/A12/A26).
   - Comfort termico, quota neve Appennino (Santo Stefano d'Aveto / Monte Beigua) e visibilità nebbia nei valichi.
3. **Indice Operativo MARE (`sea_state` & `maritime_safety`):**
   - Scala Douglas (Stato del mare da `0 - Calmo` a `8 - Grosso/Tempestoso`) e Scala Beaufort (da `0` a `12`).
   - **Indice di Ripidità d'Onda (Wave Steepness Warning):** Rapporto $H_s / L$: segnala quando onde di soli $1.2-1.8\text{ m}$ con periodo corto ($3.5-4.5\text{ s}$) diventano pericolose e frangenti per imbarcazioni da diporto all'imboccatura del Porto di Genova o davanti al Promontorio di Portofino.
   - Matrice consigli operativi per: **Piccolo Diporto / Vela**, **Pesca Costiera**, **Kayak / SUP / Balneazione**, **Operatività Portuale / Ormeggi**.

---

## 3. Conseguenze

- **Positive:**
  - Previsioni enormemente più accurate sui microclimi genovesi rispetto a qualsiasi app meteo standard single-model.
  - Informazioni immediatamente azionabili sia per il cittadino/escursionista a terra sia per il comandante/diportista in mare.
- **Trade-off / Vincoli:**
  - Richiede il download parallelo di più serie temporali ed elaborazione vettoriale (direzioni medie di vento e onda calcolate tramite componenti trigonometriche $u, v$).

---

## 4. Task Operativi Collegati (con Definition of Done)

- [x] **TASK-ENG-01**: **Implementazione connettori multi-modello (AROME, ICON-D2, ECMWF, GFS), radar nowcasting (RainViewer/OMIRL) e algoritmo di fusione pesata con diagnostica Convergenza Ligure**
  - *File coinvolti*: `backend/engine/connectors.py`, `backend/engine/ensemble.py`, `backend/engine/ligurian_diagnostics.py`, `tests/test_ensemble_nowcast.py`
  - *Acceptance Criteria*:
    - Il motore recupera e fonde correttamente i modelli LAM (AROME, ICON-D2) e globali (ECMWF, GFS).
    - Il calcolo trigonometrico della direzione del vento e il rilevatore di convergenza Tramontana/Scirocco funzionano e superano gli unit test.
    - L'endpoint `/api/v1/nowcast` fornisce timeline a 15 minuti per le prossime 3 ore + tiles radar live.
  - *Verification Step*: `pytest tests/test_ensemble_nowcast.py -v`
- [x] **TASK-MAR-01**: **Implementazione motore Meteo-Marino (Open-Meteo Marine + Meteomar + Stormglass opzionale) con calcolo Douglas, Beaufort, Wave Steepness e sicurezza navigazione**
  - *File coinvolti*: `backend/engine/marine.py`, `backend/engine/alerts.py`, `tests/test_marine_engine.py`
  - *Acceptance Criteria*:
    - Restituisce altezza onda significativa ($H_s$), onda massima stimata ($H_{max} \approx 1.65 \cdot H_s$), swell, periodo ($T_p$), direzione, SST, nodi di vento/raffica, grado Beaufort e grado Douglas.
    - Calcola la matrice di sicurezza per Diporto/Vela, Kayak/Costiero e Ormeggi per tutti i 5 settori marini del Golfo di Genova.
  - *Verification Step*: `pytest tests/test_marine_engine.py -v`
