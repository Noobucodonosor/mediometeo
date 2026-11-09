"""Zonizzazione Micro-Climatica e Marittima della Provincia di Genova (ADR-0001)."""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Literal


DistrictCategory = Literal["land", "sea"]


@dataclass(frozen=True)
class District:
    """Rappresenta un distretto operativo Terra o Mare della Provincia di Genova."""

    id: str
    name: str
    short_name: str
    category: DistrictCategory
    lat: float
    lon: float
    sea_lat: float  # Coordinata marina di riferimento per modelli d'onda
    sea_lon: float
    elevation_m: int  # Positivo per altitudine s.l.m., negativo per batimetria media (m)
    arpal_zone: str  # Zona di allerta ARPAL Liguria (B, C, D, E) o Settore Meteomar
    sub_areas: list[str]
    microclimate_notes: str
    critical_hazards: list[str]
    wind_exposure_deg: tuple[int, int]  # Settore di traversia principale (gradi)

    def to_dict(self) -> dict:
        return asdict(self)


DISTRICTS: dict[str, District] = {
    # ==========================================================================
    # DISTRETTI TERRA (Provincia di Genova)
    # ==========================================================================
    "GE-CENTRO-PONENTE": District(
        id="GE-CENTRO-PONENTE",
        name="Genova Centro, Porto Antico & Ponente Urbano",
        short_name="Genova Centro / Ponente",
        category="land",
        lat=44.4072,
        lon=8.9338,
        sea_lat=44.3850,
        sea_lon=8.9200,
        elevation_m=15,
        arpal_zone="Zona B (Genovese Centrale)",
        sub_areas=[
            "Porto Antico",
            "Carignano",
            "Castelletto",
            "Sampierdarena",
            "Cornigliano",
            "Sestri Ponente",
            "Pegli",
            "Pra'",
            "Voltri",
        ],
        microclimate_notes=(
            "Fascia costiera urbanizzata esposta ai flussi di trabocco della Tramontana Scura "
            "da Turchino/Giovi e allo sbarramento umido di Scirocco/Ostro. "
            "Sede tipica della linea di convergenza ligure."
        ),
        critical_hazards=[
            "Rovesci autorigeneranti da convergenza Tramontana-Scirocco",
            "Raffiche di caduta >70 km/h su Sopraelevata e viadotti A10",
            "Allagamenti urbani rapidi nei sottopassi costieri",
        ],
        wind_exposure_deg=(340, 180),
    ),
    "GE-VAL-POLCEVERA": District(
        id="GE-VAL-POLCEVERA",
        name="Val Polcevera & Passo dei Giovi",
        short_name="Val Polcevera",
        category="land",
        lat=44.4685,
        lon=8.8980,
        sea_lat=44.3950,
        sea_lon=8.8800,
        elevation_m=85,
        arpal_zone="Zona B (Bacino Polcevera)",
        sub_areas=[
            "Rivarolo",
            "Certosa",
            "Bolzaneto",
            "San Quirico",
            "Pontedecimo",
            "Campomorone",
            "Mignanego / Passo dei Giovi",
            "Serra Riccò",
            "Sant'Olcese",
        ],
        microclimate_notes=(
            "Principale corridoio d'incanalamento della Tramontana Scura dal catino padano "
            "attraverso la sella dei Giovi (472 m). Forti gradienti termici in inverno "
            "(rischio gelicidio/neve a bassa quota) e innesco convettivo stazionario."
        ),
        critical_hazards=[
            "Incanalamento violento di Tramontana e Grecale lungo l'asta del Polcevera",
            "Piene rapide del Torrente Polcevera, Rio Fegino e affluenti",
            "Crollo termico improvviso e rischio gelicidio (freezing rain) tra Pontedecimo e Giovi",
        ],
        wind_exposure_deg=(345, 35),
    ),
    "GE-VAL-BISAGNO": District(
        id="GE-VAL-BISAGNO",
        name="Val Bisagno & Collina d'Albaro",
        short_name="Val Bisagno",
        category="land",
        lat=44.4320,
        lon=8.9630,
        sea_lat=44.3820,
        sea_lon=8.9500,
        elevation_m=55,
        arpal_zone="Zona B (Bacino Bisagno)",
        sub_areas=[
            "Foce",
            "Brignole",
            "Marassi",
            "Quezzi",
            "Staglieno",
            "Molassana",
            "Struppa",
            "Prato",
            "Bargagli",
            "Davagna",
        ],
        microclimate_notes=(
            "Bacino a risposta idrologica rapidissima (tempo di corrivazione < 2 ore) "
            "direttamente investito dal ramo umido di Scirocco/Ostro in risalita dal Golfo Ligure "
            "contro la dorsale Scoffera-Creto."
        ),
        critical_hazards=[
            "Temporali autorigeneranti V-shaped sul bacino del Bisagno e Fereggiano",
            "Effetto sbarramento orografico con picchi >80-120 mm/3h",
            "Colpi di vento (downburst) e grandine sui versanti di Quezzi e Fontanegli",
        ],
        wind_exposure_deg=(120, 190),
    ),
    "GE-LEVANTE": District(
        id="GE-LEVANTE",
        name="Levante Genovese, Golfo Paradiso & Tigullio",
        short_name="Golfo Paradiso & Tigullio",
        category="land",
        lat=44.3350,
        lon=9.2150,
        sea_lat=44.2900,
        sea_lon=9.2100,
        elevation_m=20,
        arpal_zone="Zona B / Zona C (Levante)",
        sub_areas=[
            "Quinto",
            "Nervi",
            "Bogliasco",
            "Sori",
            "Recco",
            "Camogli",
            "Santa Margherita Ligure",
            "Portofino",
            "Rapallo",
            "Zoagli",
            "Chiavari",
            "Lavagna",
            "Sestri Levante",
        ],
        microclimate_notes=(
            "Riparato dalla Tramontana invernale rispetto a Genova Centro (spesso +4/+6°C più mite), "
            "ma fortemente esposto all'impatto frontale di Scirocco e Libeccio contro il Monte di Portofino "
            "e allo sbocco del bacino dell'Entella."
        ),
        critical_hazards=[
            "Sbarramento orografico sul Promontorio di Portofino e Val Fontanabuona/Entella",
            "Mareggiate distruttive di Libeccio su passeggiata di Nervi, Camogli e Tigullio",
            "Venti di ricaduta (raffiche di caduta dai crinali) tra Recco e Rapallo",
        ],
        wind_exposure_deg=(130, 240),
    ),
    "GE-ENTROTERRA": District(
        id="GE-ENTROTERRA",
        name="Entroterra Genovese (Valli Scrivia, Stura, Trebbia & Aveto)",
        short_name="Entroterra Appenninico",
        category="land",
        lat=44.5420,
        lon=9.1520,
        sea_lat=44.3600,
        sea_lon=9.0500,
        elevation_m=620,
        arpal_zone="Zone D / E / C (Versanti Padani & Appennino)",
        sub_areas=[
            "Campo Ligure & Masone (Valle Stura)",
            "Busalla, Savignone & Ronco Scrivia (Valle Scrivia)",
            "Torriglia & Montebruno (Val Trebbia)",
            "Borzonasca, Rezzoaglio & Santo Stefano d'Aveto (Val d'Aveto)",
            "Monte Antola & Monte Maggiorasca",
        ],
        microclimate_notes=(
            "Clima appenninico con piovosità tra le più alte d'Italia (>2000 mm/anno). "
            "Sede di accumuli pluviometrici estremi con flussi meridionali, nevicate abbondanti "
            "in inverno, nebbie fitte da avvezione sui valichi (A7/A26) e gelate tardive."
        ),
        critical_hazards=[
            "Piogge orografiche persistenti e rischio frane/smottamenti sulla viabilità statale",
            "Nevicate intense e tormenta (blizzard) oltre i 500-900m e sui tratti autostradali A7/A26",
            "Nebbia densa da stau sui valichi e gelate notturne",
        ],
        wind_exposure_deg=(0, 360),
    ),
    # ==========================================================================
    # DISTRETTI MARE (Golfo di Genova & Alto Mar Ligure)
    # ==========================================================================
    "MARE-PORTO-DIGA": District(
        id="MARE-PORTO-DIGA",
        name="Avamporto di Genova, Diga Foranea & Canale di Prà (0-2 NM)",
        short_name="Porto di Genova & Diga",
        category="sea",
        lat=44.3890,
        lon=8.9120,
        sea_lat=44.3800,
        sea_lon=8.9050,
        elevation_m=-28,
        arpal_zone="Meteomar Mar Ligure — Settore Portuale Genova",
        sub_areas=[
            "Imboccatura di Levante (Porto Antico / Fiera)",
            "Diga Foranea Cristoforo Colombo",
            "Bacino di Sampierdarena & Multedo",
            "Canale di Calma di Prà / Terminal PSA",
        ],
        microclimate_notes=(
            "Area soggetta a violente raffiche catabatiche di Tramontana/Grecale in uscita dalle vallate "
            "che generano onda corta e ripida (chop) entro 1 miglio dalla Diga, e a forte risacca "
            "di riflessione con moto ondoso lungo da Sud-Ovest (Libeccio) e Sud-Est (Scirocco)."
        ),
        critical_hazards=[
            "Raffiche improvvise di Tramontana >30-45 kt in uscita dal varco di Ponente e Levante",
            "Onda incrociata di riflessione contro la Diga Foranea con Libeccio lungo",
            "Riduzione improvvisa di visibilità per piovaschi intensi in manovra d'ingresso",
        ],
        wind_exposure_deg=(180, 250),
    ),
    "MARE-GOLFO-PONENTE": District(
        id="MARE-GOLFO-PONENTE",
        name="Golfo di Genova Ponente: Arenzano – Voltri – Multedo (0-6 NM)",
        short_name="Mare Ponente (Arenzano-Voltri)",
        category="sea",
        lat=44.3750,
        lon=8.7450,
        sea_lat=44.3650,
        sea_lon=8.7500,
        elevation_m=-65,
        arpal_zone="Meteomar Mar Ligure — Ponente Genovese",
        sub_areas=[
            "Rada di Voltri",
            "Porto di Arenzano",
            "Cogoleto",
            "Secca di Pegli",
            "Fascia costiera 0-6 miglia Ponente",
        ],
        microclimate_notes=(
            "Settore famoso per il getto furioso di Tramontana/Maestrale che scende dal Passo del Turchino "
            "e dai Piani di Praglia: il vento può passare da 8 a 35 nodi in pochi minuti sottocosta, "
            "alzando mare corto e frangente verso il largo."
        ),
        critical_hazards=[
            "Getto catabatico violento dal Turchino (Tramontana/Maestrale 30-50 kt)",
            "Swell imponente di Libeccio e Mezzogiorno con frangenti sui bassi fondali",
            "Linea di groppo temporalesco lungo il confine di convergenza a largo di Voltri",
        ],
        wind_exposure_deg=(150, 240),
    ),
    "MARE-GOLFO-PARADISO-PORTOFINO": District(
        id="MARE-GOLFO-PARADISO-PORTOFINO",
        name="Golfo Paradiso, Punta Chiappa & AMP Portofino (0-6 NM)",
        short_name="Golfo Paradiso & Portofino",
        category="sea",
        lat=44.3120,
        lon=9.1420,
        sea_lat=44.2950,
        sea_lon=9.1400,
        elevation_m=-80,
        arpal_zone="Meteomar Mar Ligure — Golfo Paradiso / Portofino",
        sub_areas=[
            "Scogliera di Nervi & Bogliasco",
            "Camogli & San Fruttuoso",
            "Punta Chiappa (Meda)",
            "Faro di Portofino (Capo Nord-Est)",
        ],
        microclimate_notes=(
            "Il Promontorio di Portofino crea marcata accelerazione del vento per effetto capo "
            "(Punta Chiappa e Faro di Portofino) e onde rifratte/incrociate molto insidiose per il diporto."
        ),
        critical_hazards=[
            "Effetto Capo (+8/+12 kt di rinforzo vento) e mare incrociato su Punta Chiappa e Faro di Portofino",
            "Esposizione totale a mareggiate di Libeccio (210°-240°) e Scirocco (130°-160°)",
            "Raffiche di caduta ('refoli') nelle rade di San Fruttuoso e Porto Pidocchio",
        ],
        wind_exposure_deg=(135, 250),
    ),
    "MARE-TIGULLIO": District(
        id="MARE-TIGULLIO",
        name="Golfo del Tigullio, Sestri Levante & Punta Manara (0-6 NM)",
        short_name="Golfo del Tigullio",
        category="sea",
        lat=44.2850,
        lon=9.3150,
        sea_lat=44.2650,
        sea_lon=9.3100,
        elevation_m=-55,
        arpal_zone="Meteomar Mar Ligure — Tigullio",
        sub_areas=[
            "Rada di Santa Margherita & Rapallo",
            "Marina di Chiavari & Lavagna",
            "Baia del Silenzio & Baia delle Favole (Sestri Levante)",
            "Punta Manara",
        ],
        microclimate_notes=(
            "La parte occidentale (Santa Margherita/Rapallo) è protetta dal Monte di Portofino con venti da Ovest, "
            "ma diventa una trappola con Scirocco/Ostro e con lo swell lungo di Libeccio che ruota attorno al promontorio."
        ),
        critical_hazards=[
            "Risacca pesante nelle rade di Santa Margherita e Rapallo con Scirocco e Ostro",
            "Frangenti su Punta Manara e all'imboccatura dei porti di Chiavari/Lavagna con mare formato",
            "Brezze termiche pomeridiane rinforzate e temporali costieri autunnali",
        ],
        wind_exposure_deg=(130, 225),
    ),
    "MARE-LARGO-LIGURE": District(
        id="MARE-LARGO-LIGURE",
        name="Alto Mar Ligure al Largo (>12 NM — Direttrice Genova-Corsica)",
        short_name="Largo Mar Ligure (>12 NM)",
        category="sea",
        lat=44.1200,
        lon=8.9500,
        sea_lat=44.1200,
        sea_lon=8.9500,
        elevation_m=-850,
        arpal_zone="Meteomar Mar Ligure Settentrionale — Largo",
        sub_areas=[
            "Centro Golfo di Genova (>12 NM)",
            "Rotta Genova – Capraia / Bastia / Calvi",
            "Santuario dei Cetacei Pelagos (Settore Nord)",
            "Area Boa ODAS Italia",
        ],
        microclimate_notes=(
            "Acque profonde (>800 m) dove il fetch di Libeccio (dal Golfo del Leone/Baleari) "
            "può sviluppare onde significative di 4-6+ metri (onda massima >8-9 m) e burrasche "
            "forza 8-10 Beaufort associate al minimo depressionario del Golfo di Genova (Genova Low)."
        ),
        critical_hazards=[
            "Mare grosso/molto agitato da Libeccio con fetch lungo e onde >4 m",
            "Ciclogenesi rapida (Genova Low) con rotazione improvvisa del vento di 180°",
            "Trombe marine e supercelle marittime tra fine estate e autunno",
        ],
        wind_exposure_deg=(0, 360),
    ),
}


def get_district(district_id: str) -> District | None:
    """Restituisce un distretto per ID (case-insensitive)."""
    return DISTRICTS.get(district_id.upper())


def list_districts(category: str | None = None) -> list[dict]:
    """Restituisce la lista dei distretti opzionalmente filtrata per 'land' o 'sea'."""
    items = list(DISTRICTS.values())
    if category in ("land", "sea"):
        items = [d for d in items if d.category == category]
    return [d.to_dict() for d in items]


def find_nearest_district(
    lat: float, lon: float, preferred_category: str | None = None
) -> District:
    """Trova il distretto preconfigurato più vicino a una coppia (lat, lon)."""
    candidates = list(DISTRICTS.values())
    if preferred_category in ("land", "sea"):
        candidates = [d for d in candidates if d.category == preferred_category]

    def haversine_km(d: District) -> float:
        r = 6371.0
        phi1, phi2 = math.radians(lat), math.radians(d.lat)
        dphi = math.radians(d.lat - lat)
        dlambda = math.radians(d.lon - lon)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return min(candidates, key=haversine_km)
