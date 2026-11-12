from pathlib import Path

from smart_home_energy.naloga1.main import (
    read_vreme,
    read_cene,
    read_poraba,
    zdruzi_podatke,
)


# Pot do obstoječih XML datotek
DATA_DIR = (
    Path(__file__).resolve().parents[1]
    / "naloga1"
    / "data"
)


class DataUnavailableError(ValueError):
    """Raised when a valid period has no usable source data."""


def validate_period(period: str) -> None:
    """Preveri zapis obdobja: YYYY ali YYYY-MM."""

    import re

    if not re.fullmatch(
        r"\d{4}(-(?:0[1-9]|1[0-2]))?",
        period
    ):
        raise ValueError(
            "Obdobje mora biti v obliki 2025 ali 2025-01."
        )


def load_data():
    """Prebere XML datoteke in združi podatke."""

    vremena = read_vreme(DATA_DIR / "vreme.xml")
    cene = read_cene(DATA_DIR / "cene.xml")
    porabe = read_poraba(DATA_DIR / "poraba.xml")

    return zdruzi_podatke(vremena, cene, porabe)


def load_prices():
    """Prebere urne cene elektrike."""

    return read_cene(DATA_DIR / "cene.xml")


def filter_period(records: list, period: str) -> list:
    """Filtrira zapise glede na leto ali mesec."""

    validate_period(period)

    return [
        record
        for record in records
        if record.get("datum", "").startswith(period)
    ]


def get_consumption(period: str) -> list:
    """Vrne porabo elektrike za izbrano obdobje."""

    records = load_data()
    records = filter_period(records, period)

    return records


def get_statistics(period: str) -> dict:
    """Izračuna statistiko porabe in stroškov."""

    records = get_consumption(period)

    if not records:
        raise DataUnavailableError(
            "Za izbrano obdobje ni podatkov."
        )

    consumptions = [
        record["porabaKWh"]
        for record in records
        if record["porabaKWh"] is not None
    ]

    if not consumptions:
        raise DataUnavailableError(
            "Za izbrano obdobje ni podatkov o porabi."
        )

    # Skupna poraba
    total_consumption = sum(consumptions)

    # Skupni stroški
    total_cost = sum(
        record["porabaKWh"] * record["cenaEURKWh"]
        for record in records
        if record["porabaKWh"] is not None
        and record["cenaEURKWh"] is not None
    )

    return {
        "measurement_count": len(consumptions),
        "total_consumption_kwh": total_consumption,
        "average_consumption_kwh": (
            total_consumption / len(consumptions)
        ),
        "max_consumption_kwh": max(consumptions),
        "min_consumption_kwh": min(consumptions),
        "estimated_cost_eur": total_cost,
    }


def get_cheapest_hours(
    period: str,
    limit: int = 5
) -> list:
    """Vrne ure z najnižjo ceno elektrike."""

    if limit < 1 or limit > 100:
        raise ValueError(
            "Število rezultatov mora biti med 1 in 100."
        )

    prices = load_prices()
    prices = filter_period(prices, period)

    prices = [
        record
        for record in prices
        if record["cenaEURKWh"] is not None
    ]

    if not prices:
        raise DataUnavailableError(
            "Za izbrano obdobje ni podatkov o cenah."
        )

    prices.sort(
        key=lambda record: record["cenaEURKWh"]
    )

    return prices[:limit]


def get_all_prices(period: str) -> list:
    """Vrne vse urne cene za streaming."""

    prices = load_prices()
    prices = filter_period(prices, period)

    prices = [
        record
        for record in prices
        if record["cenaEURKWh"] is not None
    ]

    prices.sort(
        key=lambda record: (
            record["datum"],
            record["ura"]
        )
    )

    if not prices:
        raise DataUnavailableError(
            "Za izbrano obdobje ni podatkov o cenah."
        )

    return prices
