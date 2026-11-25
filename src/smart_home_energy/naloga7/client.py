"""Odjemalec FastAPI za strežnik poimenovane cevi."""

from multiprocessing.connection import Client, wait
from time import sleep

from smart_home_energy.naloga7.pipe_protocol import (
    PIPE_ADDRESS,
    PIPE_AUTHKEY,
    PIPE_CONNECT_ATTEMPTS,
    PIPE_CONNECT_RETRY_DELAY_SECONDS,
    PIPE_RESPONSE_TIMEOUT_SECONDS,
)


class PipeUnavailableError(RuntimeError):
    """Strežnik poimenovane cevi ni dosegljiv ali ni pravočasno odgovoril."""


def request_analysis(period: str, top_n: int) -> dict:
    """Pošlje zahtevo strežniku in vrne analizo ali razumljivo napako."""
    connection = None
    last_error = None
    for attempt in range(PIPE_CONNECT_ATTEMPTS):
        try:
            connection = Client(
                PIPE_ADDRESS,
                family="AF_PIPE",
                authkey=PIPE_AUTHKEY,
            )
            break
        except (OSError, EOFError) as error:
            last_error = error
            if attempt + 1 < PIPE_CONNECT_ATTEMPTS:
                sleep(PIPE_CONNECT_RETRY_DELAY_SECONDS)

    if connection is None:
        raise PipeUnavailableError(
            "Energetski strežnik ne deluje. Zaženi ga v drugem terminalu in poskusi znova."
        ) from last_error

    try:
        connection.send({
            "version": 1,
            "operation": "energy_analysis",
            "period": period,
            "top_n": top_n,
        })
        if not wait([connection], timeout=PIPE_RESPONSE_TIMEOUT_SECONDS):
            raise PipeUnavailableError(
                "Energetski strežnik se ni odzval pravočasno. Poskusi znova."
            )
        response = connection.recv()
    except (OSError, EOFError) as error:
        raise PipeUnavailableError(
            "Povezava z energetskim strežnikom se je prekinila. Poskusi znova."
        ) from error
    finally:
        connection.close()

    if not isinstance(response, dict) or response.get("version") != 1:
        raise PipeUnavailableError("Strežnik je vrnil neveljaven odgovor.")
    if not response.get("ok"):
        raise ValueError(response.get("error", "Analize ni bilo mogoče izvesti."))
    return response["data"]
