"""Catalogo Geografico Granulare della Provincia di Genova (ADR-0005 / TASK-GEO-01).

Include:
- Tutti i 67 Comuni della Città Metropolitana di Genova (coordinate, altitudine, vallata/bacino, zona ARPAL)
- I 25 Quartieri / Municipi urbani di Genova
- Le 20 Rade, Porti, Cale e Capi marittimi (con angolo di apertura della cala `bay_open_deg` per il calcolo fisico della risacca)
- I 6 Valichi Appenninici chiave (Giovi, Turchino, Scoffera, Bocco, Forcella, Faiallo)
- Poligoni ufficiali dell'Area Marina Protetta (AMP) di Portofino (Zone A, B, C con limiti di velocità in nodi)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Literal


LocationType = Literal["comune", "quartiere", "rada_porto", "valico"]


@dataclass(frozen=True)
class GeoLocation:
    id: str
    name: str
    loc_type: LocationType
    category: Literal["land", "sea"]
    valley_or_sector: str
    lat: float
    lon: float
    sea_lat: float
    sea_lon: float
    elevation_m: int
    arpal_zone: str
    district_id: str
    bay_open_deg: int | None = None  # Angolo bussola verso cui è aperta la cala/rada (per calcolo risacca)
    shelter_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _slug(prefix: str, name: str) -> str:
    clean = (
        name.upper()
        .replace("'", "-")
        .replace("À", "A")
        .replace("È", "E")
        .replace("É", "E")
        .replace("Ì", "I")
        .replace("Ò", "O")
        .replace("Ù", "U")
        .replace(" ", "-")
        .replace(".", "")
        .replace("/", "-")
    )
    while "--" in clean:
        clean = clean.replace("--", "-")
    return f"{prefix}-{clean.strip('-')}"


# 1. I 67 Comuni ufficiali della Città Metropolitana di Genova
_RAW_COMUNI_67: list[tuple[str, float, float, int, str, str, str]] = [
    # (Nome, Lat, Lon, Elev_m, Vallata/Settore, Zona ARPAL, District_ID)
    ("Genova", 44.4072, 8.9339, 20, "Genova Capoluogo", "Zona B", "GE-CENTRO-PONENTE"),
    ("Arenzano", 44.4035, 8.6827, 6, "Riviera di Ponente", "Zona B", "GE-CENTRO-PONENTE"),
    ("Cogoleto", 44.3896, 8.6462, 4, "Riviera di Ponente", "Zona B", "GE-CENTRO-PONENTE"),
    ("Mele", 44.4455, 8.7479, 125, "Ponente / Val Leira", "Zona B", "GE-CENTRO-PONENTE"),
    ("Campo Ligure", 44.5381, 8.6978, 342, "Valle Stura", "Zona D", "GE-ENTROTERRA"),
    ("Masone", 44.5036, 8.7120, 406, "Valle Stura", "Zona D", "GE-ENTROTERRA"),
    ("Rossiglione", 44.5667, 8.6667, 300, "Valle Stura", "Zona D", "GE-ENTROTERRA"),
    ("Tiglieto", 44.5250, 8.6198, 500, "Valle Stura / Orba", "Zona D", "GE-ENTROTERRA"),
    ("Campomorone", 44.5069, 8.8918, 118, "Val Polcevera", "Zona B", "GE-VAL-POLCEVERA"),
    ("Ceranesi", 44.5084, 8.8840, 80, "Val Polcevera", "Zona B", "GE-VAL-POLCEVERA"),
    ("Mignanego", 44.5278, 8.9152, 150, "Val Polcevera / Giovi", "Zona B", "GE-VAL-POLCEVERA"),
    ("Sant'Olcese", 44.4834, 8.9352, 300, "Val Polcevera", "Zona B", "GE-VAL-POLCEVERA"),
    ("Serra Riccò", 44.5078, 8.9360, 187, "Val Polcevera", "Zona B", "GE-VAL-POLCEVERA"),
    ("Busalla", 44.5710, 8.9453, 358, "Valle Scrivia", "Zona E", "GE-ENTROTERRA"),
    ("Casella", 44.5348, 8.9989, 410, "Valle Scrivia", "Zona E", "GE-ENTROTERRA"),
    ("Crocefieschi", 44.5846, 9.0235, 742, "Valle Scrivia", "Zona E", "GE-ENTROTERRA"),
    ("Isola del Cantone", 44.6461, 8.9569, 296, "Valle Scrivia", "Zona E", "GE-ENTROTERRA"),
    ("Montoggio", 44.5151, 9.0436, 438, "Alta Valle Scrivia", "Zona E", "GE-ENTROTERRA"),
    ("Ronco Scrivia", 44.6082, 8.9552, 334, "Valle Scrivia", "Zona E", "GE-ENTROTERRA"),
    ("Savignone", 44.5639, 8.9887, 500, "Valle Scrivia", "Zona E", "GE-ENTROTERRA"),
    ("Valbrevenna", 44.5606, 9.0916, 533, "Valle Scrivia / Antola", "Zona E", "GE-ENTROTERRA"),
    ("Vobbia", 44.5994, 9.0400, 477, "Valle Scrivia", "Zona E", "GE-ENTROTERRA"),
    ("Bargagli", 44.4445, 9.0886, 341, "Alta Val Bisagno", "Zona B", "GE-VAL-BISAGNO"),
    ("Davagna", 44.4669, 9.0899, 516, "Alta Val Bisagno", "Zona B", "GE-VAL-BISAGNO"),
    ("Lumarzo", 44.4435, 9.1372, 325, "Val Fontanabuona", "Zona C", "GE-ENTROTERRA"),
    ("Fascia", 44.5659, 9.2376, 900, "Alta Val Trebbia", "Zona E", "GE-ENTROTERRA"),
    ("Fontanigorda", 44.5466, 9.3047, 800, "Val Trebbia", "Zona E", "GE-ENTROTERRA"),
    ("Gorreto", 44.6061, 9.2924, 533, "Val Trebbia", "Zona E", "GE-ENTROTERRA"),
    ("Montebruno", 44.5260, 9.2490, 655, "Val Trebbia", "Zona E", "GE-ENTROTERRA"),
    ("Propata", 44.5647, 9.1849, 990, "Val Trebbia / Brugneto", "Zona E", "GE-ENTROTERRA"),
    ("Rondanina", 44.5624, 9.2177, 981, "Val Trebbia", "Zona E", "GE-ENTROTERRA"),
    ("Rovegno", 44.5759, 9.2788, 658, "Val Trebbia", "Zona E", "GE-ENTROTERRA"),
    ("Torriglia", 44.5187, 9.1580, 769, "Val Trebbia / Scoffera", "Zona E", "GE-ENTROTERRA"),
    ("Bogliasco", 44.3782, 9.0698, 25, "Golfo Paradiso", "Zona B", "GE-LEVANTE"),
    ("Pieve Ligure", 44.3748, 9.0866, 168, "Golfo Paradiso", "Zona B", "GE-LEVANTE"),
    ("Sori", 44.3727, 9.1042, 14, "Golfo Paradiso", "Zona B", "GE-LEVANTE"),
    ("Avegno", 44.3823, 9.1587, 34, "Golfo Paradiso / Val Recco", "Zona B", "GE-LEVANTE"),
    ("Recco", 44.3621, 9.1435, 5, "Golfo Paradiso", "Zona B", "GE-LEVANTE"),
    ("Uscio", 44.4132, 9.1630, 361, "Golfo Paradiso / Colle Caprile", "Zona B", "GE-LEVANTE"),
    ("Camogli", 44.3484, 9.1558, 32, "Golfo Paradiso / Monte Portofino", "Zona B", "GE-LEVANTE"),
    ("Portofino", 44.3042, 9.2072, 18, "Promontorio di Portofino", "Zona C", "GE-LEVANTE"),
    ("Santa Margherita Ligure", 44.3349, 9.2101, 13, "Golfo del Tigullio", "Zona C", "GE-LEVANTE"),
    ("Rapallo", 44.3500, 9.2333, 9, "Golfo del Tigullio", "Zona C", "GE-LEVANTE"),
    ("Zoagli", 44.3370, 9.2671, 17, "Golfo del Tigullio", "Zona C", "GE-LEVANTE"),
    ("Chiavari", 44.3164, 9.3237, 5, "Golfo del Tigullio / Entella", "Zona C", "GE-LEVANTE"),
    ("Lavagna", 44.3122, 9.3417, 6, "Golfo del Tigullio / Entella", "Zona C", "GE-LEVANTE"),
    ("Cogorno", 44.3331, 9.3725, 38, "Bassa Val Fontanabuona / Entella", "Zona C", "GE-LEVANTE"),
    ("Carasco", 44.3517, 9.3441, 26, "Confluenza Entella / Sturla / Lavagna", "Zona C", "GE-LEVANTE"),
    ("Leivi", 44.3457, 9.3190, 118, "Colline del Tigullio", "Zona C", "GE-LEVANTE"),
    ("San Colombano Certenoli", 44.3718, 9.3116, 40, "Val Fontanabuona", "Zona C", "GE-ENTROTERRA"),
    ("Coreglia Ligure", 44.3919, 9.2675, 65, "Val Fontanabuona", "Zona C", "GE-ENTROTERRA"),
    ("Cicagna", 44.4085, 9.2363, 88, "Val Fontanabuona", "Zona C", "GE-ENTROTERRA"),
    ("Orero", 44.4068, 9.2742, 438, "Val Fontanabuona", "Zona C", "GE-ENTROTERRA"),
    ("Lorsica", 44.4295, 9.2679, 383, "Val Fontanabuona", "Zona C", "GE-ENTROTERRA"),
    ("Favale di Malvaro", 44.4520, 9.2579, 320, "Val Fontanabuona", "Zona C", "GE-ENTROTERRA"),
    ("Moconesi", 44.4198, 9.2124, 129, "Val Fontanabuona", "Zona C", "GE-ENTROTERRA"),
    ("Tribogna", 44.4164, 9.1959, 330, "Val Fontanabuona", "Zona C", "GE-ENTROTERRA"),
    ("Neirone", 44.4543, 9.1909, 350, "Val Fontanabuona", "Zona C", "GE-ENTROTERRA"),
    ("Mezzanego", 44.3837, 9.3773, 83, "Valle Sturla", "Zona C", "GE-ENTROTERRA"),
    ("Borzonasca", 44.4221, 9.3871, 167, "Valle Sturla / Aveto", "Zona C", "GE-ENTROTERRA"),
    ("Rezzoaglio", 44.5263, 9.3867, 700, "Val d'Aveto", "Zona E", "GE-ENTROTERRA"),
    ("Santo Stefano d'Aveto", 44.5477, 9.4507, 1012, "Alta Val d'Aveto", "Zona E", "GE-ENTROTERRA"),
    ("Ne", 44.3445, 9.3986, 68, "Val Graveglia", "Zona C", "GE-ENTROTERRA"),
    ("Sestri Levante", 44.2733, 9.3932, 10, "Tigullio Orientale", "Zona C", "GE-LEVANTE"),
    ("Casarza Ligure", 44.2747, 9.4534, 34, "Val Petronio", "Zona C", "GE-LEVANTE"),
    ("Castiglione Chiavarese", 44.2745, 9.5136, 271, "Val Petronio", "Zona C", "GE-ENTROTERRA"),
    ("Moneglia", 44.2386, 9.4903, 4, "Riviera di Levante", "Zona C", "GE-LEVANTE"),
]

# 2. I 25 Quartieri / Unità Urbanistiche principali di Genova
_RAW_QUARTIERI_25: list[tuple[str, float, float, int, str, str]] = [
    ("Genova Voltri", 44.4285, 8.7530, 8, "Municipio VII Ponente", "GE-CENTRO-PONENTE"),
    ("Genova Pra'", 44.4260, 8.7885, 6, "Municipio VII Ponente", "GE-CENTRO-PONENTE"),
    ("Genova Pegli", 44.4258, 8.8152, 10, "Municipio VII Ponente", "GE-CENTRO-PONENTE"),
    ("Genova Multedo", 44.4250, 8.8330, 8, "Municipio VII Ponente", "GE-CENTRO-PONENTE"),
    ("Genova Sestri Ponente", 44.4239, 8.8505, 12, "Municipio VI Medio Ponente", "GE-CENTRO-PONENTE"),
    ("Genova Cornigliano", 44.4150, 8.8710, 10, "Municipio VI Medio Ponente", "GE-CENTRO-PONENTE"),
    ("Genova Sampierdarena", 44.4125, 8.8980, 12, "Municipio II Centro Ovest", "GE-CENTRO-PONENTE"),
    ("Genova San Teodoro / Dinegro", 44.4165, 8.9095, 45, "Municipio II Centro Ovest", "GE-CENTRO-PONENTE"),
    ("Genova Rivarolo / Certosa", 44.4420, 8.8950, 38, "Municipio V Valpolcevera", "GE-VAL-POLCEVERA"),
    ("Genova Bolzaneto", 44.4605, 8.8995, 52, "Municipio V Valpolcevera", "GE-VAL-POLCEVERA"),
    ("Genova Pontedecimo", 44.4960, 8.9035, 92, "Municipio V Valpolcevera", "GE-VAL-POLCEVERA"),
    ("Genova Porto Antico / Maddalena", 44.4095, 8.9280, 5, "Municipio I Centro Est", "GE-CENTRO-PONENTE"),
    ("Genova Castelletto / Righi", 44.4220, 8.9345, 145, "Municipio I Centro Est", "GE-CENTRO-PONENTE"),
    ("Genova Carignano", 44.3995, 8.9365, 35, "Municipio I Centro Est", "GE-CENTRO-PONENTE"),
    ("Genova Brignole / San Vincenzo", 44.4070, 8.9465, 15, "Municipio I Centro Est", "GE-VAL-BISAGNO"),
    ("Genova Foce", 44.3965, 8.9510, 6, "Municipio VIII Medio Levante", "GE-VAL-BISAGNO"),
    ("Genova Albaro / Boccadasse", 44.3915, 8.9720, 22, "Municipio VIII Medio Levante", "GE-LEVANTE"),
    ("Genova San Fruttuoso / Quezzi", 44.4180, 8.9610, 65, "Municipio III Bassa Val Bisagno", "GE-VAL-BISAGNO"),
    ("Genova Marassi", 44.4195, 8.9535, 28, "Municipio III Bassa Val Bisagno", "GE-VAL-BISAGNO"),
    ("Genova Staglieno", 44.4320, 8.9555, 45, "Municipio IV Media Val Bisagno", "GE-VAL-BISAGNO"),
    ("Genova Molassana", 44.4465, 8.9830, 68, "Municipio IV Media Val Bisagno", "GE-VAL-BISAGNO"),
    ("Genova Struppa / Prato", 44.4525, 9.0150, 95, "Municipio IV Media Val Bisagno", "GE-VAL-BISAGNO"),
    ("Genova San Martino / Borgoratti", 44.4075, 8.9780, 70, "Municipio IX Levante", "GE-LEVANTE"),
    ("Genova Sturla / Quarto dei Mille", 44.3905, 8.9945, 18, "Municipio IX Levante", "GE-LEVANTE"),
    ("Genova Quinto / Nervi / Sant'Ilario", 44.3820, 9.0410, 25, "Municipio IX Levante", "GE-LEVANTE"),
]

# 3. Le 20 Rade, Porti, Cale e Capi marittimi del Golfo di Genova (con bay_open_deg per calcolo risacca)
_RAW_RADE_PORTI_20: list[tuple[str, float, float, int, str, str, int, str]] = [
    # (Nome, Lat, Lon, Depth_m, Settore, District_ID, bay_open_deg, Note Ridosso/Traversia)
    ("Porto di Arenzano & Marina", 44.3990, 8.6850, -12, "Golfo di Genova Ponente", "MARE-GOLFO-PONENTE", 145, "Ridossato da N/NW; traversia da Scirocco (SE). Getto catabatico violento dal Turchino."),
    ("Canale di Calma di Pra' & Rada di Voltri", 44.4180, 8.7750, -18, "Golfo di Genova Ponente", "MARE-GOLFO-PONENTE", 180, "Acque protette dalla diga di Pra', ma soggette a forti raffiche di Tramontana/Maestrale."),
    ("Avamporto di Genova & Diga Foranea Levante", 44.3890, 8.9180, -28, "Porto di Genova", "MARE-PORTO-DIGA", 205, "Traversia da Libeccio lungo; onda incrociata di riflessione contro la Diga Foranea."),
    ("Marina Fiera di Genova / Porto Antico", 44.3985, 8.9320, -14, "Porto di Genova", "MARE-PORTO-DIGA", 195, "Ormeggio sicuro; attenzione alle raffiche di caduta >35 kt di Tramontana Scura in manovra."),
    ("Cala di Boccadasse & Capo Santa Chiara", 44.3885, 8.9735, -10, "Genova Levante Costiero", "MARE-PORTO-DIGA", 195, "Cala stretta esposta a Ostro e Libeccio; frangenti immediati a riva con onda >0.8m."),
    ("Porticciolo di Nervi & Scogliera", 44.3805, 9.0350, -15, "Genova Levante Costiero", "MARE-GOLFO-PARADISO-PORTOFINO", 205, "Esposto a mareggiate di Libeccio e Ostro; fondale roccioso che innalza rapidamente l'onda."),
    ("Rada di Sori & Bogliasco", 44.3680, 9.0950, -22, "Golfo Paradiso", "MARE-GOLFO-PARADISO-PORTOFINO", 210, "Aperto a S/SW; riparato dai venti settentrionali."),
    ("Porto di Camogli", 44.3490, 9.1510, -16, "Golfo Paradiso", "MARE-GOLFO-PARADISO-PORTOFINO", 235, "Traversia da Libeccio e Ponente; ingresso impegnativo con mare formato da SW."),
    ("Punta Chiappa & Secca dell'Isuela (AMP Zona B)", 44.3215, 9.1455, -45, "Promontorio di Portofino Ovest", "MARE-GOLFO-PARADISO-PORTOFINO", 245, "Capo esposto senza ridosso: forti correnti di promontorio e onda incrociata da SW/NW. Max 5 kt in Zona B."),
    ("Cala dell'Oro (AMP Zona A — Riserva Integrale)", 44.3160, 9.1620, -35, "Promontorio di Portofino", "MARE-GOLFO-PARADISO-PORTOFINO", 200, "DIVIETO ASSOLUTO di navigazione, accesso e ancoraggio (Zona A Riserva Integrale)."),
    ("Baia di San Fruttuoso di Capodimonte (AMP Zona B)", 44.3150, 9.1750, -20, "Promontorio di Portofino Sud", "MARE-GOLFO-PARADISO-PORTOFINO", 200, "Cala incassata aperta a 200° (SSO): lo swell lungo da S/SW genera forte risacca amplificata dall'alta marea. Max 5 kt."),
    ("Faro di Portofino / Punta del Capo", 44.2985, 9.2185, -55, "Promontorio di Portofino Est", "MARE-GOLFO-PARADISO-PORTOFINO", 160, "Punto di convergenza tra il moto ondoso del Golfo Paradiso e quello del Tigullio; accelerazione vento (+8 kt)."),
    ("Baia e Porto di Portofino", 44.3030, 9.2110, -14, "Golfo del Tigullio", "MARE-TIGULLIO", 120, "Eccellente ridosso da N/NW/SW; entra risacca fastidiosa solo con Scirocco/Levante (110°-140°) e periodo lungo."),
    ("Baia di Paraggi (AMP Zona C)", 44.3105, 9.2125, -12, "Golfo del Tigullio", "MARE-TIGULLIO", 145, "Riparata da N/W, ma aperta a Scirocco e allo swell di Libeccio rifratto dal Capo di Portofino."),
    ("Porto e Rada di Santa Margherita Ligure", 44.3295, 9.2165, -16, "Golfo del Tigullio", "MARE-TIGULLIO", 135, "Protetta da Ovest dal Monte di Portofino; esposta a Scirocco e risacca da Sud."),
    ("Rada e Porto Carlo Riva di Rapallo", 44.3450, 9.2340, -12, "Golfo del Tigullio", "MARE-TIGULLIO", 165, "In fondo al golfo: soggetta a risacca con Ostro/Scirocco e a raffiche catabatiche dalle valli."),
    ("Scogliera di Zoagli", 44.3335, 9.2660, -25, "Golfo del Tigullio", "MARE-TIGULLIO", 205, "Costa alta esposta frontalmente a Libeccio e Mezzogiorno."),
    ("Marina di Chiavari & Porto di Lavagna", 44.3100, 9.3300, -15, "Golfo del Tigullio", "MARE-TIGULLIO", 215, "Attenzione ai frangenti su fondale sabbioso all'imboccatura con mare molto mosso da SW."),
    ("Baia del Silenzio & Baia delle Favole (Sestri Levante)", 44.2690, 9.3910, -14, "Tigullio Orientale / Punta Manara", "MARE-TIGULLIO", 230, "Baia delle Favole aperta a Libeccio (230°); Baia del Silenzio più protetta ma soggetta a risacca da SE/S."),
    ("Alto Mar Ligure / Boa Capo Mele - Genova Largo (>12 NM)", 44.1500, 8.9500, -820, "Mare Aperto Ligure", "MARE-LARGO-LIGURE", 225, "Acque profonde senza ridosso: fetch completo da SW (Golfo del Leone) con onde massime fino a 1.65x Hs."),
]

# 4. I 6 Valichi Appenninici e Autostradali
_RAW_VALICHI_6: list[tuple[str, float, float, int, str, str]] = [
    ("Passo dei Giovi & Tratto A7 Busalla", 44.5495, 8.9325, 472, "Valico Appenninico (Val Polcevera / Scrivia)", "GE-VAL-POLCEVERA"),
    ("Passo del Turchino & Tratto A26 Masone", 44.4785, 8.7320, 532, "Valico Appenninico (Ponente / Valle Stura)", "GE-ENTROTERRA"),
    ("Passo del Faiallo", 44.4720, 8.6650, 1044, "Crinale Beigua / Stura", "GE-ENTROTERRA"),
    ("Passo della Scoffera", 44.4745, 9.0920, 674, "Valico Appenninico (Val Bisagno / Val Trebbia)", "GE-VAL-BISAGNO"),
    ("Passo della Forcella & Monte Ramaceto", 44.4580, 9.3420, 875, "Valico Appenninico (Valle Sturla / Val d'Aveto)", "GE-ENTROTERRA"),
    ("Passo del Bocco", 44.4150, 9.4420, 956, "Valico Appenninico (Valle Sturla / Vara)", "GE-ENTROTERRA"),
]


# Poligoni ufficiali dell'Area Marina Protetta (AMP) di Portofino (ORO-6 da /Users/dany/meteo)
AMP_PORTOFINO_ZONES: list[dict[str, Any]] = [
    {
        "id": "AMP-ZONA-A",
        "name": "AMP Portofino — Zona A (Riserva Integrale - Cala dell'Oro)",
        "color": "#ef4444",
        "max_speed_knots": 0,
        "rules": "DIVIETO ASSOLUTO di navigazione, accesso, ancoraggio, pesca e balneazione.",
        "coords": [
            [44.3155, 9.1720],
            [44.3175, 9.1680],
            [44.3210, 9.1690],
            [44.3210, 9.1740],
            [44.3180, 9.1760],
        ],
    },
    {
        "id": "AMP-ZONA-B",
        "name": "AMP Portofino — Zona B (Riserva Generale: Punta Chiappa – San Fruttuoso – Faro)",
        "color": "#f59e0b",
        "max_speed_knots": 5,
        "rules": "Velocità massima 5 nodi. Vietato l'ancoraggio libero (solo gavitelli autorizzati).",
        "coords": [
            [44.3050, 9.1950],
            [44.3100, 9.1850],
            [44.3155, 9.1720],
            [44.3210, 9.1690],
            [44.3280, 9.1620],
            [44.3350, 9.1600],
            [44.3380, 9.1620],
            [44.3380, 9.1700],
            [44.3350, 9.1680],
            [44.3280, 9.1700],
            [44.3210, 9.1800],
            [44.3155, 9.1850],
            [44.3100, 9.1950],
            [44.3050, 9.2000],
        ],
    },
    {
        "id": "AMP-ZONA-C",
        "name": "AMP Portofino — Zona C (Riserva Parziale: Camogli / Paraggi / Santa Margherita)",
        "color": "#10b981",
        "max_speed_knots": 7,
        "rules": "Navigazione consentita a velocità ridotta (max 7-10 nodi sottocosta). Rispettare le boe dei bagnanti.",
        "coords": [
            [44.3000, 9.2050],
            [44.3050, 9.1950],
            [44.3050, 9.2000],
            [44.3100, 9.1950],
            [44.3155, 9.1850],
            [44.3210, 9.1800],
            [44.3280, 9.1700],
            [44.3350, 9.1680],
            [44.3380, 9.1700],
            [44.3400, 9.1750],
            [44.3400, 9.1900],
            [44.3380, 9.2000],
            [44.3350, 9.2050],
            [44.3300, 9.2100],
            [44.3200, 9.2150],
            [44.3100, 9.2180],
            [44.3000, 9.2150],
        ],
    },
]


def _nearest_sea_point(lat: float, lon: float) -> tuple[float, float]:
    """Associa a qualsiasi punto terrestre la coordinata marina antistante nel Golfo di Genova."""
    if lon < 8.82:
        return 44.3750, max(8.6400, min(8.8200, lon))
    if lon < 9.04:
        return 44.3780, lon
    if lon < 9.22:
        return 44.2980, lon
    return 44.2550, min(9.4900, lon)


def _build_catalog() -> dict[str, GeoLocation]:
    catalog: dict[str, GeoLocation] = {}

    for name, lat, lon, elev, valley, arpal, dist_id in _RAW_COMUNI_67:
        loc_id = _slug("COM", name)
        s_lat, s_lon = _nearest_sea_point(lat, lon)
        catalog[loc_id] = GeoLocation(
            id=loc_id,
            name=name,
            loc_type="comune",
            category="land",
            valley_or_sector=valley,
            lat=lat,
            lon=lon,
            sea_lat=s_lat,
            sea_lon=s_lon,
            elevation_m=elev,
            arpal_zone=arpal,
            district_id=dist_id,
            bay_open_deg=195 if elev < 40 else None,
            shelter_notes=f"Comune della Città Metropolitana di Genova ({valley}, {elev} m s.l.m.)",
        )

    for name, lat, lon, elev, muni, dist_id in _RAW_QUARTIERI_25:
        loc_id = _slug("QRT", name)
        s_lat, s_lon = _nearest_sea_point(lat, lon)
        catalog[loc_id] = GeoLocation(
            id=loc_id,
            name=name,
            loc_type="quartiere",
            category="land",
            valley_or_sector=muni,
            lat=lat,
            lon=lon,
            sea_lat=s_lat,
            sea_lon=s_lon,
            elevation_m=elev,
            arpal_zone="Zona B (Genova Urbana)",
            district_id=dist_id,
            bay_open_deg=195,
            shelter_notes=f"Quartiere urbano di Genova ({muni})",
        )

    for name, lat, lon, depth_m, sector, dist_id, bay_deg, notes in _RAW_RADE_PORTI_20:
        loc_id = _slug("SEA", name)
        catalog[loc_id] = GeoLocation(
            id=loc_id,
            name=name,
            loc_type="rada_porto",
            category="sea",
            valley_or_sector=sector,
            lat=lat,
            lon=lon,
            sea_lat=lat,
            sea_lon=lon,
            elevation_m=depth_m,
            arpal_zone="Meteomar Mar Ligure — Settore Genova/Tigullio",
            district_id=dist_id,
            bay_open_deg=bay_deg,
            shelter_notes=notes,
        )

    for name, lat, lon, elev, sector, dist_id in _RAW_VALICHI_6:
        loc_id = _slug("VAL", name)
        s_lat, s_lon = _nearest_sea_point(lat, lon)
        catalog[loc_id] = GeoLocation(
            id=loc_id,
            name=name,
            loc_type="valico",
            category="land",
            valley_or_sector=sector,
            lat=lat,
            lon=lon,
            sea_lat=s_lat,
            sea_lon=s_lon,
            elevation_m=elev,
            arpal_zone="Zone B/D/E (Valichi Appenninici)",
            district_id=dist_id,
            bay_open_deg=None,
            shelter_notes=f"Valico appenninico a {elev} m s.l.m. — critico per vento di caduta, gelicidio e nebbia da stau.",
        )

    return catalog


LOCATIONS_CATALOG: dict[str, GeoLocation] = _build_catalog()


def get_location(loc_id: str) -> GeoLocation | None:
    """Restituisce una località per ID (o per compatibilità con i 10 district ID)."""
    upper = loc_id.upper()
    if upper in LOCATIONS_CATALOG:
        return LOCATIONS_CATALOG[upper]
    # Mappatura di compatibilità se viene passato un district_id
    fallback_map = {
        "GE-CENTRO-PONENTE": "COM-GENOVA",
        "GE-VAL-POLCEVERA": "QRT-GENOVA-BOLZANETO",
        "GE-VAL-BISAGNO": "QRT-GENOVA-MARASSI",
        "GE-LEVANTE": "COM-RAPALLO",
        "GE-ENTROTERRA": "COM-TORRIGLIA",
        "MARE-PORTO-DIGA": "SEA-AVAMPORTO-DI-GENOVA-&-DIGA-FORANEA-LEVANTE",
        "MARE-GOLFO-PONENTE": "SEA-PORTO-DI-ARENZANO-&-MARINA",
        "MARE-GOLFO-PARADISO-PORTOFINO": "SEA-BAIA-DI-SAN-FRUTTUOSO-DI-CAPODIMONTE-(AMP-ZONA-B)",
        "MARE-TIGULLIO": "SEA-BAIA-E-PORTO-DI-PORTOFINO",
        "MARE-LARGO-LIGURE": "SEA-ALTO-MAR-LIGURE---BOA-CAPO-MELE---GENOVA-LARGO-(>12-NM)",
    }
    mapped = fallback_map.get(upper)
    if mapped and mapped in LOCATIONS_CATALOG:
        return LOCATIONS_CATALOG[mapped]
    return None


def search_locations(
    q: str | None = None,
    loc_type: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Filtra il catalogo delle località per testo, tipo ('comune','quartiere','rada_porto','valico') o categoria."""
    items = list(LOCATIONS_CATALOG.values())
    if loc_type:
        items = [loc for loc in items if loc.loc_type == loc_type]
    if category in ("land", "sea"):
        items = [loc for loc in items if loc.category == category]
    if q and q.strip():
        needle = q.strip().lower()
        items = [
            loc
            for loc in items
            if needle in loc.name.lower() or needle in loc.valley_or_sector.lower()
        ]
    return [loc.to_dict() for loc in items]


def find_nearest_location(
    lat: float, lon: float, preferred_category: str | None = None
) -> GeoLocation:
    """Trova la località (Comune, Quartiere, Rada o Valico) più vicina a (lat, lon)."""
    candidates = list(LOCATIONS_CATALOG.values())
    if preferred_category in ("land", "sea"):
        candidates = [c for c in candidates if c.category == preferred_category]

    def dist_km(loc: GeoLocation) -> float:
        r = 6371.0
        p1, p2 = math.radians(lat), math.radians(loc.lat)
        dp = math.radians(loc.lat - lat)
        dl = math.radians(loc.lon - lon)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return min(candidates, key=dist_km)
