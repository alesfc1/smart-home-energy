from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from smart_home_energy.naloga3.open_data import (
    get_chart_data,
    get_filter_options,
)

app = FastAPI()
STATIC_DIR = Path(__file__).resolve().parent / "naloga3" / "static"


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Vrne spletni vmesnik za vizualizacijo."""
    return FileResponse(STATIC_DIR / "poraba_gospodinjstev.html")


@app.get("/api/metadata")
def metadata():
    return get_filter_options()


@app.get("/api/consumption")
def consumption(
    municipality: str | None = None,
    consumer_type: str = "Gospodinjstva",
    start_month: str | None = None,
    end_month: str | None = None,
):
    try:
        return get_chart_data(
            municipality=municipality,
            consumer_type=consumer_type,
            start_month=start_month,
            end_month=end_month,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error