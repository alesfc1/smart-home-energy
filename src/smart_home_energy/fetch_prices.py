import os
import csv
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

API_KEY = os.getenv("ELECTRICITY_MAPS_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "Nastavi okoljsko spremenljivko ELECTRICITY_MAPS_API_KEY."
    )

BASE_URL = (
    "https://api.electricitymaps.com/v4/"
    "price-day-ahead/past-range"
)

ZONE = "SI"
LAT = 46.5558
LON = 15.6459
YEAR = 2025
CHUNK_DAYS = 10

OUTPUT_DIR = (
    Path(__file__).resolve().parent
    / "data"
    / "data-sources"
    / "raw"
)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JSON_FILE = OUTPUT_DIR / "cene.json"
CSV_FILE = OUTPUT_DIR / "prices_2025.csv"

session = requests.Session()
session.headers.update({
    "auth-token": API_KEY,
    "Accept": "application/json",
})


def fetch_chunk(start_date, end_date):
    """Pridobi cene za eno časovno obdobje."""
    params = {
        "start": f"{start_date.isoformat()}T00:00:00Z",
        "end": f"{end_date.isoformat()}T24:00:00Z",
        "zone": ZONE,
        "temporalGranularity": "hourly",
        "lat": LAT,
        "lon": LON,
    }

    for attempt in range(5):
        try:
            response = session.get(
                BASE_URL,
                params=params,
                timeout=60,
            )

            if response.status_code == 429:
                wait = int(response.headers.get("Retry-After", 30))
                print(f"Preveč zahtev. Čakam {wait} s ...")
                time.sleep(wait)
                continue

            if response.status_code >= 500:
                response.raise_for_status()

            response.raise_for_status()
            return response.json()

        except (requests.RequestException, ValueError) as exc:
            if attempt == 4:
                raise RuntimeError(
                    f"Napaka za obdobje {start_date}–{end_date}: {exc}"
                ) from exc

            wait = 2 ** attempt
            print(f"Napaka: {exc}. Ponovni poskus čez {wait} s.")
            time.sleep(wait)

    raise RuntimeError(
        f"Pridobivanje ni uspelo: {start_date}–{end_date}"
    )


def extract_records(payload):
    """Iz odgovora pridobi seznam zapisov, če ga odgovor vsebuje."""
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("data", "prices", "history"):
            if isinstance(payload.get(key), list):
                return payload[key]

    return []


def main():
    current = date(YEAR, 1, 1)
    last_day = date(YEAR, 12, 31)

    all_records = []
    raw_responses = []
    failed_ranges = []

    while current <= last_day:
        end_date = min(
            current + timedelta(days=CHUNK_DAYS - 1),
            last_day,
        )

        print(f"Pridobivam {current} – {end_date} ...")

        try:
            payload = fetch_chunk(current, end_date)
            records = extract_records(payload)

            raw_responses.append({
                "start": str(current),
                "end": str(end_date),
                "response": payload,
            })

            all_records.extend(records)
            print(f"  Prejetih zapisov: {len(records)}")

        except Exception as exc:
            print(f"  NEUSPEH: {exc}")
            failed_ranges.append({
                "start": str(current),
                "end": str(end_date),
                "error": str(exc),
            })

        # Kratek premor med zahtevami.
        time.sleep(1)
        current = end_date + timedelta(days=1)

    # Odstrani morebitne podvojene zapise glede na čas.
    unique_records = {}
    for record in all_records:
        if isinstance(record, dict):
            timestamp = (
                record.get("datetime")
                or record.get("timestamp")
                or record.get("start")
            )

            if timestamp is not None:
                unique_records[timestamp] = record
            else:
                unique_records[
                    f"no_timestamp_{len(unique_records)}"
                ] = record

    records = sorted(
        unique_records.values(),
        key=lambda item: str(
            item.get("datetime")
            or item.get("timestamp")
            or item.get("start")
            or ""
        ),
    )

    # Shrani surove odgovore in združene zapise.
    result = {
        "year": YEAR,
        "zone": ZONE,
        "records": records,
        "failed_ranges": failed_ranges,
        "raw_responses": raw_responses,
    }

    JSON_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # CSV za enostaven uvoz v druge programe.
    if records:
        columns = sorted({
            key
            for record in records
            for key in record.keys()
        })

        with CSV_FILE.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(records)

    print("\nKončano.")
    print(f"Unikatnih zapisov: {len(records)}")
    print(f"Neuspešnih obdobij: {len(failed_ranges)}")
    print(f"JSON: {JSON_FILE}")

    if records:
        print(f"CSV: {CSV_FILE}")

    if failed_ranges:
        print("Nekatera obdobja niso bila pridobljena.")
        print("Oglej si polje failed_ranges v JSON datoteki.")


if __name__ == "__main__":
    main()