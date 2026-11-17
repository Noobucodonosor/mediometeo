# ADR-0009: Roadmap Chirurgica UX Comfort & Anti-Slop (`taste-skill 2.5.1`) — 1 Agente Singolo su 1 Pezzo alla Volta

- **Stato:** Proposto (`Proposed` — Roadmap sequenziale pianificata su Milestone GitHub `v3.0`)
- **Priorità:** P0 — Critica (Qualità UX, Comfort Cognitivo & Credibilità Strumentale)
- **Data:** 2026-11-17
- **Autori:** Daniele (`@Noobucodonosor`) & Antigravity AI
- **Fonti:** Audit critico post-`v2.5`, [`design-taste-frontend` (`taste-skill 2.5.1`)](file:///Users/dany/.gemini/config/skills/design-taste-frontend/SKILL.md), [`ADR-0006`](./0006-pure-marine-physics-6tabs-eta-smartwatch.md), [`ADR-0008`](./0008-taste-skill-anti-slop-full-omirl-fusion.md), Milestone GitHub `#1` (`v3.0 — Surgical UX Comfort & Anti-Slop`)

---

## 1. Post-Mortem Onesto di `v2.4` / `v2.5`

Dopo l'introduzione della palette `blue-black-cornflower` e dei font `IBM Plex Sans` / `IBM Plex Mono` (`ADR-0008`), la verifica critica sull'esperienza utente reale ha evidenziato un divario netto tra la vista smartwatch (`/orologio`) e l'applicazione principale:

1. **Perché l'HUD Smartwatch (`/orologio`) funziona:**
   - È compatto, costruito su un singolo livello di contenimento piatto (`1px` hairline), ha zero testo ridondante, ogni numero risponde a una domanda immediata di chi è a bordo e la bussola SVG occupa il centro visivo senza competere con altri pannelli.
2. **Perché il resto dell'app risultava ancora "AI slop" e cognitivamente faticoso:**
   - La skill `taste-skill 2.5.1` era stata applicata **solo a livello cosmetico** (palette, font, rimozione delle emoji sostituite però da una micro-icona SVG 14px davanti a ogni singola label — violando `taste.md` Dealbreaker #1) invece che a livello **strutturale e di gerarchia dell'informazione**:
     - **Ridondanza verticale Shell/HUD/Tab 1:** Topbar con 8 controlli sparsi, tab verbosi e numerati (`1. Adesso — Sensori & cam` — violazione `copy-numbered`), e la scheda `Adesso` che ripeteva in grande Temperatura, Vento e Pressione già presenti 40px sopra nella Telemetry HUD.
     - **Annidamento a 3–4 livelli (`ground -> surface -> card -> inner-box`):** violazione esplicita di `system.md` (massimo 2 livelli di scatole) con oltre 20 sub-card nella sola scheda `Adesso` e badge-slogan decorativi (`Verità osservativa`, `Fisica pura`).
     - **Sovraffollamento cartografico (`#tab-mappa`):** attivando i sensori OMIRL vengono renderizzati insieme ~84 badge meteo + 24 badge `IDRO` + ~30 etichette località + 12 pin webcam (~150 rettangoli sovrapposti su Genova a zoom 10), più un banner didattico sopra la mappa.
     - **Finte grafiche webcam (`#tab-adesso`):** presenza di onde SVG cartoon al posto delle webcam senza feed fotografico diretto — violazione diretta di `taste-skill` House Rule #6 e Never #2.
     - **Muri di testo fuori modalità (`#tab-nowcast`):** modalità `Terra` e `Mare` mostravano simultaneamente 5 + 5 box verbosi con bullet e corsivi fitti, forzando l'utente a cercare la propria modalità.
     - **Sovraccarico tabellare e verbosità (`#tab-modelli`, `#tab-rotta`, `#tab-bollettini`):** tabelle da 11 colonne impilate sotto 2 grafici con unità ripetute in ogni cella; form e risultati Rotta impilati; bollettini testuali lunghi con interlinea stretta e senza selettore giornaliero.
   - Infine, **l'esecuzione parallela via swarm sui file UI frammenta la coerenza visiva**: il craft UX/UI e la disciplina del layout richiedono **1 singolo agente focalizzato su 1 singolo pezzo alla volta**, con verifica visiva reale in browser headless (`shoot.mjs`) prima e dopo ogni commit.

---

## 2. Decisione Architetturale: Regola "1 Agente Singolo × 1 Pezzo Chirurgico"

1. **Divieto di Swarm sul Craft UI:**
   - I task `TASK-UX-04` .. `TASK-UX-10` verranno eseguiti **strictly one issue at a time** da **un solo agente**, su una singola schermata o strato architetturale ben definito.
2. **Design System Rigoroso (`taste-skill 2.5.1` Strutturale):**
   - **Massimo 2 livelli visivi:** fondo primario (`#0a0d14`) + superficie piatta (`#131824`) separata da filetti `1px` (`rgba(233, 237, 243, 0.13)`). Niente card dentro card per elenchi e metriche.
   - **Zero icone davanti alle label e zero badge-slogan decorativi.**
   - **Coerenza assoluta `Terra` / `Mare`:** nessuna schermata mescola in primo piano contenuti dell'altra modalità.
   - **Onestà visiva:** zero grafiche cartoon al posto di foto/webcam mancanti.
3. **Gate Visivo Obbligatorio per Ogni Issue:**
   - Ogni PR/commit collegato alle Issue `#16`–`#22` deve produrre e ispezionare gli screenshot reali di `shoot.mjs` alle tre larghezze `1440x900`, `768x1024` e `390x844` prima di passare all'issue successiva.

---

## 3. Roadmap Sequenziale su GitHub (Milestone `v3.0 — Surgical UX Comfort & Anti-Slop`)

- [x] **TASK-UX-04** (`#16`, P0): **Shell, Topbar, HUD & Navigazione — Pulizia Cognitiva, Ricerca Unificata e Rimozione Ridondanze**
- [ ] **TASK-UX-05** (`#17`, P1): **Schermata Mappa (`#tab-mappa`) — Decluttering Cartografico e Selettore Layer Singolo**
- [ ] **TASK-UX-06** (`#18`, P1): **Schermata Adesso (`#tab-adesso`) — Zero Duplicati HUD, Liste Tabellari `1px` e Rimozione Finte Webcam SVG**
- [ ] **TASK-UX-07** (`#19`, P1): **Schermata Nowcast 3h (`#tab-nowcast`) — Coerenza Modalità Terra/Mare e Righe Strumentali al Posto dei Muri di Testo**
- [ ] **TASK-UX-08** (`#20`, P1): **Schermata Modelli (`#tab-modelli`) — Vista Focalizzata (`Meteogrammi | Confronto 5 Modelli | 7 Giorni`) e Leggibilità Tabellare**
- [ ] **TASK-UX-09** (`#21`, P2): **Schermate Rotta (`#tab-rotta`) & Bollettini (`#tab-bollettini`) — Split Strumentale Rotta e Tipografia Editoriale Bollettini**
- [ ] **TASK-UX-10** (`#22`, P1): **Verifica Visiva Real-Browser (`shoot.mjs` `1440` / `768` / `390`), Audit Copy-Lint e Allineamento Finale `/orologio`**
