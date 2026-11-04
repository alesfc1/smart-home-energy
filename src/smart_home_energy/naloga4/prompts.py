"""Priprava prompta za LLM glede na izbrano obdobje in cilj analize. Filtrira obdobje in agregira meritve na različne načine"""

from collections import defaultdict
from datetime import date
import json


def create_prompt(period: str, goal: str, measurements: list[dict]) -> str:
    """Izbere obdobje, pripravi agregate iz meritev Naloge 1 in poda urne meritve."""
    if period == "2025":
        start, end = date(2025, 1, 1), date(2026, 1, 1)
    else:
        year, month = (int(value) for value in period.split("-"))
        start = date(year, month, 1)
        end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)

    selected = [
        row for row in measurements
        if row.get("datum") and start <= date.fromisoformat(row["datum"]) < end
    ]
    if not selected:
        raise ValueError(f"Za obdobje {period} ni meritev.")

    consumption = [r["porabaKWh"] for r in selected if r.get("porabaKWh") is not None]
    prices = [r["cenaEURKWh"] for r in selected if r.get("cenaEURKWh") is not None]
    temperatures = [r["temperatura"] for r in selected if r.get("temperatura") is not None]
    daily = defaultdict(float)
    for row in selected:
        if row.get("porabaKWh") is not None:
            daily[row["datum"]] += row["porabaKWh"]

    total = sum(consumption)
    cost = sum(
        r["porabaKWh"] * r["cenaEURKWh"] for r in selected
        if r.get("porabaKWh") is not None and r.get("cenaEURKWh") is not None
    )
    hourly = [
        [
            row.get("datum"),
            row.get("ura"),
            round(row["porabaKWh"], 3) if row.get("porabaKWh") is not None else None,
            round(row["cenaEURKWh"], 5) if row.get("cenaEURKWh") is not None else None,
            round(row["temperatura"], 1) if row.get("temperatura") is not None else None,
        ]
        for row in selected
    ]

    context = {
        "obdobje": period,
        "stevilo_meritev": len(selected),
        "poraba_kWh": {
            "skupaj": round(total, 3),
            "povprecje_na_meritev": round(total / len(consumption), 5) if consumption else None,
            "najvisja_meritev": round(max(consumption), 3) if consumption else None,
        },
        "cena_EUR_na_kWh": {
            "povprecje": round(sum(prices) / len(prices), 5) if prices else None,
            "minimum": round(min(prices), 5) if prices else None,
            "maksimum": round(max(prices), 5) if prices else None,
        },
        "ocenjeni_strosek_EUR": round(cost, 2),
        "temperatura_C": {
            "povprecje": round(sum(temperatures) / len(temperatures), 1) if temperatures else None,
            "minimum": round(min(temperatures), 1) if temperatures else None,
            "maksimum": round(max(temperatures), 1) if temperatures else None,
        },
        "dnevna_poraba_kWh": {day: round(value, 3) for day, value in sorted(daily.items())},
        "urne_meritve": {
            "stolpci": ["datum", "ura", "poraba_kWh", "cena_EUR_na_kWh", "temperatura_C"],
            "vrednosti": hourly,
        },
    }
    return f"""Si slovenski energetski svetovalec. Analiziraj dejanske urne meritve gospodinjstva.
Poraba je v kWh, cena v EUR/kWh, temperatura v °C. Ocenjeni strošek je vsota
porabe, pomnožene s pripadajočo ceno.

Izbrano obdobje: {period}
Cilj uporabnika: {goal}
Podatki: {json.dumps(context, ensure_ascii=False)}

Vrni izključno veljaven JSON oblike:
{{"summary":"...","consumption_analysis":"...","weather_impact":"...",
"recommendations":[{{"title":"...","description":"...","priority":"low|medium|high"}}],
"conclusion":"..."}}
Piši v slovenščini. Ne izmišljaj si podatkov. Če
ugotovitev ni mogoča to jasno povej. Priporočila prilagodi cilju.
"""
