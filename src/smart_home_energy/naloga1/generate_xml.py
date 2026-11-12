"""
Pridobi podatke o porabi, cenah in vremenu iz raw datotek, odstrani nepotrebne atribute, združi porabo v urne postavke, pretvori cene v EUR/kWh in ustvari XML datoteke
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "data" / "data-sources" / "raw"
OUTPUT_DIR = Path(__file__).resolve().parent / "data"


def _hour_key(value: str) -> tuple[str, str]:
    timestamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return timestamp.strftime("%Y-%m-%d"), timestamp.strftime("%H:00")


def _read_consumption(path: Path) -> dict[tuple[str, str], float | None]:
    intervals: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not {"Timestamp", "Energy_A_plus"}.issubset(reader.fieldnames):
            raise ValueError("poraba.csv mora vsebovati stolpca Timestamp in Energy_A_plus.")

        for row in reader:
            timestamp = datetime.fromisoformat(row["Timestamp"].strip().replace("Z", "+00:00"))
            if timestamp.minute not in {0, 15, 30, 45} or timestamp.second != 0:
                raise ValueError(f"Nepričakovan interval porabe: {row['Timestamp']}")
            key = (timestamp.strftime("%Y-%m-%d"), timestamp.strftime("%H:00"))
            intervals[key].append((timestamp.minute, float(row["Energy_A_plus"])))

    expected_minutes = {0, 15, 30, 45}
    hourly: dict[tuple[str, str], float | None] = {}
    for key, readings in intervals.items():
        minutes = [minute for minute, _ in readings]
        if len(minutes) != len(set(minutes)):
            raise ValueError(f"Podvojena 15-minutna meritev za uro {key[0]} {key[1]}.")
        hourly[key] = (
            sum(value for _, value in readings)
            if len(readings) == 4 and set(minutes) == expected_minutes
            else None
        )
    return hourly


def _read_prices(path: Path) -> dict[tuple[str, str], float]:
    source = json.loads(path.read_text(encoding="utf-8-sig"))
    records = source.get("records") if isinstance(source, dict) else None
    if not isinstance(records, list):
        raise ValueError("cene.json nima seznama records.")

    prices: dict[tuple[str, str], float] = {}
    for record in records:
        key = _hour_key(record["datetime"])
        value = float(record["value"])
        unit = record.get("unit")
        if unit == "EUR/MWh":
            value /= 1000
        elif unit != "EUR/kWh":
            raise ValueError(f"Nepodprta enota cene za {key}: {unit!r}")
        if key in prices:
            raise ValueError(f"Podvojena urna cena za {key}.")
        prices[key] = value
    return prices


def _read_weather(path: Path) -> dict[tuple[str, str], float]:
    source = json.loads(path.read_text(encoding="utf-8-sig"))
    hourly = source.get("hourly", {})
    times = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])
    if not times or len(times) != len(temperatures):
        raise ValueError("vreme.json nima usklajenih urnih časov in temperatur.")

    weather: dict[tuple[str, str], float] = {}
    for timestamp, temperature in zip(times, temperatures, strict=True):
        key = _hour_key(timestamp)
        if temperature is None:
            raise ValueError(f"Manjka temperatura za {key}.")
        if key in weather:
            raise ValueError(f"Podvojena urna temperatura za {key}.")
        weather[key] = float(temperature)
    return weather


def _write_xml(path: Path, root: ET.Element) -> None:
    ET.indent(root, space="    ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def generate_xml_files() -> int:
    consumption = _read_consumption(RAW_DIR / "poraba.csv")
    prices = _read_prices(RAW_DIR / "cene.json")
    weather = _read_weather(RAW_DIR / "vreme.json")

    keys = set(consumption)
    if keys != set(prices) or keys != set(weather):
        missing_price = len(keys - set(prices))
        missing_weather = len(keys - set(weather))
        extra_price = len(set(prices) - keys)
        extra_weather = len(set(weather) - keys)
        raise ValueError(
            "Viri nimajo enakih urnih časov: "
            f"manjkajoče cene={missing_price}, manjkajoče vreme={missing_weather}, "
            f"odvečne cene={extra_price}, odvečno vreme={extra_weather}."
        )

    ordered_keys = sorted(keys)
    if not ordered_keys:
        raise ValueError("V izvornih datotekah ni meritev.")

    consumption_root = ET.Element("porabe")
    prices_root = ET.Element("cene")
    weather_root = ET.Element("vremena")
    for index, key in enumerate(ordered_keys, start=1):
        day, hour = key
        price_id = f"C{index}"
        weather_id = f"V{index}"
        measurement_id = f"P{index}"

        measurement = ET.SubElement(
            consumption_root,
            "meritev",
            {"id": measurement_id, "vremeId": weather_id, "cenaId": price_id},
        )
        ET.SubElement(measurement, "datum").text = day
        ET.SubElement(measurement, "ura").text = hour
        value = consumption[key]
        ET.SubElement(measurement, "porabaKWh").text = f"{value:.3f}" if value is not None else None

        price = ET.SubElement(prices_root, "cena", {"id": price_id})
        ET.SubElement(price, "datum").text = day
        ET.SubElement(price, "ura").text = hour
        ET.SubElement(price, "cenaEURKWh").text = f"{prices[key]:.5f}"

        temperature = ET.SubElement(weather_root, "vreme", {"id": weather_id})
        ET.SubElement(temperature, "datum").text = day
        ET.SubElement(temperature, "ura").text = hour
        ET.SubElement(temperature, "temperatura").text = f"{weather[key]:.1f}"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_xml(OUTPUT_DIR / "poraba.xml", consumption_root)
    _write_xml(OUTPUT_DIR / "cene.xml", prices_root)
    _write_xml(OUTPUT_DIR / "vreme.xml", weather_root)
    return len(ordered_keys)


def main() -> None:
    count = generate_xml_files()
    print(f"Ustvarjeni so XML-ji za {count} usklajenih ur.")
    missing = sum(
        value is None
        for value in _read_consumption(RAW_DIR / "poraba.csv").values()
    )
    if missing:
        print(f"Opozorilo: {missing} uri nimata vseh štirih 15-minutnih meritev; poraba je prazna.")


if __name__ == "__main__":
    main()
