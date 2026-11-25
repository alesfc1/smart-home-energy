import sqlite3
from pathlib import Path

DATABASE_DIR = Path(__file__).resolve().parent
DB_PATH = DATABASE_DIR / "smart-home-energy.db"


def create_database():
    """Ustvari tabele za aktualne cene in urne meritve"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recent_prices (
                date TEXT PRIMARY KEY,
                price REAL NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS hourly_measurements (
                timestamp TEXT PRIMARY KEY,
                consumption_kwh REAL,
                price_eur_kwh REAL,
                temperature REAL
            )
        """)

    print("Podatkovna baza je pripravljena.")


if __name__ == "__main__":
    create_database()
