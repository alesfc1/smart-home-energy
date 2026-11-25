"""Strežnik energetske analize prek Windows poimenovane cevi."""

import logging
import os
from multiprocessing.connection import Listener

from smart_home_energy.naloga5.data_service import (
    DataUnavailableError,
    get_consumption,
    validate_period,
)
from smart_home_energy.naloga7.pipe_protocol import PIPE_ADDRESS, PIPE_AUTHKEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def create_analysis(period: str, top_n: int) -> dict:
    validate_period(period)
    if not 1 <= top_n <= 50:
        raise ValueError("Število ur mora biti med 1 in 50.")

    records = get_consumption(period)
    if not records:
        raise DataUnavailableError("Za izbrano obdobje ni podatkov.")

    consumption_rows = [
        row for row in records if row["porabaKWh"] is not None
    ]
    if not consumption_rows:
        raise DataUnavailableError("Za izbrano obdobje ni podatkov o porabi.")

    priced_rows = [
        row for row in consumption_rows if row["cenaEURKWh"] is not None
    ]
    highest_cost_hours = sorted(
        priced_rows,
        key=lambda row: row["porabaKWh"] * row["cenaEURKWh"],
        reverse=True,
    )[:top_n]

    return {
        "highest_cost_hours": [
            {
                "date": row["datum"],
                "hour": row["ura"],
                "consumption_kwh": row["porabaKWh"],
                "price_eur_kwh": row["cenaEURKWh"],
                "temperature_c": row["temperatura"],
                "estimated_cost_eur": round(
                    row["porabaKWh"] * row["cenaEURKWh"], 4
                ),
            }
            for row in highest_cost_hours
        ],
    }


def handle_request(request) -> dict:
    if not isinstance(request, dict) or request.get("version") != 1:
        raise ValueError("Neveljavna zahteva po poimenovani cevi.")
    if request.get("operation") != "energy_analysis":
        raise ValueError("Neznana operacija.")
    return create_analysis(request.get("period", ""), request.get("top_n", 10))


def serve() -> None:
    if os.name != "nt":
        raise RuntimeError("Ta izvedba uporablja Windows poimenovano cev (AF_PIPE).")

    logger.info("Strežnik poimenovane cevi posluša na %s", PIPE_ADDRESS)
    with Listener(PIPE_ADDRESS, family="AF_PIPE", authkey=PIPE_AUTHKEY) as listener:
        while True:
            try:
                with listener.accept() as connection:
                    try:
                        data = handle_request(connection.recv())
                        connection.send({"version": 1, "ok": True, "data": data})
                    except (ValueError, DataUnavailableError) as error:
                        connection.send({"version": 1, "ok": False, "error": str(error)})
                    except Exception:
                        logger.exception("Napaka pri obdelavi zahteve po cevi.")
                        connection.send({
                            "version": 1,
                            "ok": False,
                            "error": "Pri pripravi energetske analize je prišlo do napake.",
                        })
            except (EOFError, OSError):
                logger.exception("Napaka pri sprejemu povezave po cevi.")


if __name__ == "__main__":
    try:
        serve()
    except KeyboardInterrupt:
        logger.info("Strežnik poimenovane cevi se ustavlja.")
