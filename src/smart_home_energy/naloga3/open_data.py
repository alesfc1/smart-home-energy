from __future__ import annotations
from typing import Any
import pandas as pd
from pyaxis import pyaxis
from functools import lru_cache

# Poraba električne energije (kWh) v gospodinjstvih in pri poslovnih subjektih po vrsti odjemalca, kohezijski in statistične regije, Slovenija, letno
PX_URL = (
    "https://pxweb.stat.si/SiStatData/Resources/PX/Databases/Data/1817607S.PX"
)

MUNICIPALITY_COLUMN = "OBČINE"
CONSUMER_TYPE_COLUMN = "VRSTA ODJEMALCA"
MONTH_COLUMN = "MESEC"
VALUE_COLUMN = "DATA"

@lru_cache(maxsize=1)
def load_open_data() -> pd.DataFrame:
    result = pyaxis.parse(
        PX_URL,
        encoding="windows-1250"
    )

    data = result["DATA"].copy()

    required_columns = {
        MUNICIPALITY_COLUMN,
        CONSUMER_TYPE_COLUMN,
        MONTH_COLUMN,
        VALUE_COLUMN,
    }

    # Preverimo, ali so vsi zahtevani stolpci za vizualizacijo prisotni v podatkih
    missing_columns = required_columns.difference(data.columns)
    if missing_columns:
        raise ValueError(
            "V pridobljenih podatkih manjkajo stolpci: "
            + ", ".join(sorted(missing_columns))
        )


    data[VALUE_COLUMN] = pd.to_numeric(
        data[VALUE_COLUMN],
        errors="coerce",
    )

    # Odstranimo vrstice, ki nimajo podatkov
    data = data.dropna(
        subset=[
            MUNICIPALITY_COLUMN,
            CONSUMER_TYPE_COLUMN,
            MONTH_COLUMN,
            VALUE_COLUMN,
        ]
    )

    # Izluščimo leto in mesec. Začasna oznaka v imenu meseca
    # (na primer "2026M09 (začasni podatki)") je zato podprta.
    data["LETO"] = (
        data[MONTH_COLUMN]
        .astype(str)
        .str.extract(r"^(\d{4})")[0]
        .astype("Int64")
    )

    data["MESEC_STEVILKA"] = (
        data[MONTH_COLUMN]
        .astype(str)
        .str.extract(r"M(\d{2})")[0]
        .astype("Int64")
    )

    # Ustvarimo datum za pravilno časovno razvrščanje in filtriranje.
    data["MESEC_DATUM"] = pd.to_datetime(
        data["LETO"].astype(str)
        + "-"
        + data["MESEC_STEVILKA"].astype(str)
        + "-01",
        errors="coerce",
    )

    # Neveljavne oznake mesecev ne smejo priti do grafa.
    data = data.dropna(subset=["MESEC_DATUM"])

    # Ustvarimo stolpec za oznake na osi grafa.
    data["MESEC_GRAF"] = data["MESEC_DATUM"].dt.strftime("%Y-%m")

    return data.reset_index(drop=True)


# Filtrira podatke in jih združi po mesecih
def filter_and_aggregate_data(
    data: pd.DataFrame,
    municipality: str | None = None,
    consumer_type: str | None = None,
    start_month: str | None = None,
    end_month: str | None = None,
) -> pd.DataFrame:

    filtered = data.copy()

    if start_month and end_month and start_month > end_month:
        raise ValueError("Začetni mesec ne sme biti poznejši od končnega.")

    # Če je občina izbrana, obdržimo samo njene podatke
    if municipality:
        filtered = filtered[
            filtered[MUNICIPALITY_COLUMN] == municipality
        ]

    # Če je izbrana vrsta odjemalca, obdržimo samo to vrsto.
    if consumer_type:
        filtered = filtered[
            filtered[CONSUMER_TYPE_COLUMN] == consumer_type
            ]

    # Filtriranje od začetnega meseca naprej.
    if start_month:
        start_date = _parse_month(start_month)

        filtered = filtered[
            filtered["MESEC_DATUM"] >= start_date
        ]

    # Filtriranje do končnega meseca
    if end_month:
        end_date = _parse_month(end_month) + pd.offsets.MonthEnd(1)

        filtered = filtered[
            filtered["MESEC_DATUM"] <= end_date
        ]

    # Podatke združimo po mesecu
    aggregated = (
        filtered
        .groupby(
            [
                MUNICIPALITY_COLUMN,
                CONSUMER_TYPE_COLUMN,
                "MESEC_DATUM",
                "MESEC_GRAF",
            ],
            as_index=False,
        )[VALUE_COLUMN]
        .sum()
        .sort_values("MESEC_DATUM")
    )

    # Vrnemo urejene in indeksirane podatke.
    return aggregated.reset_index(drop=True)


# Pretvori filter v obliko YYYY-MM v prvi dan meseca
def _parse_month(value: str) -> pd.Timestamp:
    try:
        return pd.to_datetime(f"{value}-01", format="%Y-%m-%d")
    except ValueError as error:
        raise ValueError(
            f"Neveljaven mesec '{value}'. Pričakovana oblika je YYYY-MM."
        ) from error


# Pripravi podatke v obliki JSON, ki jo lahko uporabi Chart.js
def get_chart_data(
    municipality: str | None = None,
    consumer_type: str | None = "Gospodinjstva",
    start_month: str | None = None,
    end_month: str | None = None,
) -> list[dict[str, Any]]:

    data = load_open_data()

    # Uporaba izbranih filtrov in izvedemo agregacijo
    filtered_data = filter_and_aggregate_data(
        data=data,
        municipality=municipality,
        consumer_type=consumer_type,
        start_month=start_month,
        end_month=end_month,
    )

    # Za Chart.JS
    records: list[dict[str, Any]] = []

    # Pretvorba v preprost slovar
    for row in filtered_data.to_dict(orient="records"):
        records.append(
            {
                "municipality": row[MUNICIPALITY_COLUMN],
                "consumer_type": row[CONSUMER_TYPE_COLUMN],
                "month": row["MESEC_GRAF"],
                "value": float(row[VALUE_COLUMN]),
            }
        )

    return records


# Vrne vrednosti, ki jih lahko uporabimo v filtrih pri vizualizaciji
def get_filter_options() -> dict[str, list[str]]:
    data = load_open_data()

    # Pripravimo seznam mesecev v obliki YYYY-MM
    months = (
        data["MESEC_DATUM"]
        .dropna()
        .sort_values()
        .dt.strftime("%Y-%m")
        .drop_duplicates()
        .tolist()
    )

    # Pripravimo seznam občin
    municipalities = sorted(
        data[MUNICIPALITY_COLUMN]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    # Pripravimo seznam vrst odjemalcev.
    consumer_types = sorted(
        data[CONSUMER_TYPE_COLUMN]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    return {
        "municipalities": municipalities,
        "consumer_types": consumer_types,
        "months": months,
    }