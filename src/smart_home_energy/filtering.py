"""Create filtered_preprocessed versions of the raw project data sources."""

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DIR = PROJECT_ROOT / "data" / "data-sources" / "raw"
FILTERED_DIR_2025 = PROJECT_ROOT / "data" / "data-sources" / "filtered_preprocessed" / "2025"


def filter_prices() -> None:
    source = json.loads((RAW_DIR / "cene.json").read_text(encoding="utf-8-sig"))
    records = []
    for record in source["records"]:
        filtered_record = {
            key: value
            for key, value in record.items()
            if key not in {"zone", "createdAt", "updatedAt", "source"}
        }
        if filtered_record.get("unit") == "EUR/MWh":
            filtered_record["value"] /= 1000
            filtered_record["unit"] = "EUR/kWh"
        records.append(filtered_record)

    (FILTERED_DIR_2025 / "cene.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def filter_consumption() -> None:
    input_path = RAW_DIR / "poraba.csv"
    output_path = FILTERED_DIR_2025 / "poraba.csv"

    with input_path.open(newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None or "Timestamp" not in reader.fieldnames:
            raise ValueError("poraba.csv must contain a Timestamp column")

        with output_path.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                timestamp = row["Timestamp"]
                if len(timestamp) >= 16 and timestamp[14:16] == "00":
                    writer.writerow(row)


def filter_weather() -> None:
    source = json.loads((RAW_DIR / "vreme.json").read_text(encoding="utf-8-sig"))
    hourly = source["hourly"]

    filtered = {
        "time": hourly["time"],
        "temperature_2m": hourly["temperature_2m"],
    }
    (FILTERED_DIR_2025 / "vreme.json").write_text(
        json.dumps(filtered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    FILTERED_DIR_2025.mkdir(parents=True, exist_ok=True)
    filter_prices()
    filter_consumption()
    filter_weather()


if __name__ == "__main__":
    main()
