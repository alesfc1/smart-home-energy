"""Parser cen iz tabele history-table na https://euenergy.live/slovenia"""

from __future__ import annotations

import json
import sqlite3
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


SLOVENIA_TIMEZONE = ZoneInfo("Europe/Ljubljana")
URL = "https://euenergy.live/slovenia"

OUTPUT_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "database"
    / "smart-home-energy.db"
)


def parse_price(value: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
    if match is None:
        return None

    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def parse_date(value: str) -> str | None:
    match = re.search(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", value)
    if match is None:
        return None

    try:
        return datetime.strptime(
            match.group(1),
            "%Y-%m-%d",
        ).date().isoformat()
    except ValueError:
        return None


def find_history_table(driver: webdriver.Chrome):
    selectors = (
        "table.prices_table.history-table",
        ".prices_table.history-table",
        "table.prices_table",
        "table.history-table",
    )

    for selector in selectors:
        tables = driver.find_elements(By.CSS_SELECTOR, selector)
        if tables:
            return tables[0]

    raise RuntimeError(
        "Tabele z razredoma 'prices_table history-table' ni bilo mogoče najti."
    )


def scrape_prices() -> list[dict[str, object]]:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 30)
        table = wait.until(find_history_table)

        rows = table.find_elements(By.CSS_SELECTOR, "tr")

        expected_dates = {
            (date.today() + timedelta(days=1)).isoformat(),
            date.today().isoformat(),
        }
        records: list[dict[str, object]] = []
        data_rows: list[tuple[str, list[str], str]] = []

        for row in rows:
            cells = row.find_elements(By.CSS_SELECTOR, "th, td")
            cell_texts = [" ".join(cell.text.split()) for cell in cells]
            row_text = " ".join(cell_texts)

            if not row_text or "Date" in row_text:
                continue

            parsed_date = parse_date(row_text)
            if parsed_date is None or parsed_date not in expected_dates:
                continue
            data_rows.append((parsed_date, cell_texts, row_text))

        for parsed_date, cell_texts, row_text in data_rows[:2]:
            price = None
            for cell_text in cell_texts:
                if "€/kWh" in cell_text or "EUR/kWh" in cell_text:
                    price = parse_price(cell_text)
                    break

            if price is None:
                matches = re.findall(r"(?<![\d])0[.,]\d+", row_text)
                if matches:
                    price = parse_price(matches[-1])

            if price is None:
                raise RuntimeError(
                    f"Cene v vrstici ni bilo mogoče prebrati: {row_text}"
                )

            records.append(
                {
                    "date": parsed_date,
                    "price": price,
                }
            )

        if len(records) < 2:
            raise RuntimeError(
                f"Najdenih je bilo samo {len(records)} ustreznih vrstic, "
                "pričakovani sta dve."
            )

        return records
    finally:
        driver.quit()


def save_prices(records: list[dict[str, object]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Shranjevanje v JSON
    json_path = OUTPUT_DIR / "parsed_recent_prices.json"
    json_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Shranjevanje v SQLite bazo
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recent_prices(
                    date TEXT PRIMARY KEY,
                    price REAL NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            updated_at = datetime.now(SLOVENIA_TIMEZONE).replace(microsecond=0).isoformat(sep=" ")

            conn.executemany("""
                INSERT INTO recent_prices (date, price, updated_at)
                VALUES (?, ?, ?) 
                ON CONFLICT(date) DO UPDATE SET
                    price = excluded.price,
                    updated_at = excluded.updated_at
            """, [
                (
                    str(record["date"]), float(record["price"]), updated_at,
                )
                for record in records
            ])


    except sqlite3.Error as e:
        print(f"[NAPAKA] Shranjevanje v bazo ni uspelo: {e}")
        raise

    # Izpis v konzolo
    for record in records:
        print(
            f"{record['date']}: "
            f"{record['price']} EUR/kWh"
        )


if __name__ == "__main__":
    save_prices(scrape_prices())