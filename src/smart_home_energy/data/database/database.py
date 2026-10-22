import sqlite3
from pathlib import Path

DATABASE_DIR = Path(__file__).resolve().parent
DB_PATH = DATABASE_DIR / "smart-home-energy.db"

def create_database():

    # Povezava z bazo
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recent_prices (
                date TEXT PRIMARY KEY,
                price REAL NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

    print(f"Podatkovna baza je pripravljena")


if __name__ == "__main__":
    create_database()
