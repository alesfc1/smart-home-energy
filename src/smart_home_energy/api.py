from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from smart_home_energy.naloga3.open_data import (
    get_chart_data,
    get_filter_options,
)
from pydantic import BaseModel
from smart_home_energy.naloga4.prompts import create_prompt
from smart_home_energy.naloga4.llm_service import analyze_energy
from smart_home_energy.naloga1.main import (
    read_vreme,
    read_cene,
    read_poraba,
    zdruzi_podatke,
)

app = FastAPI()
PROJECT_DIR = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_DIR / "naloga3"


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Vrne stran za vizualizacijo porabe gospodinjstev po občinah iz odprtih podatkov."""
    return FileResponse(STATIC_DIR / "poraba_gospodinjstev.html")


@app.get("/llm", include_in_schema=False)
def llm_page() -> FileResponse:
    """Vrne stran za analizo porabe s pomočjo LLM."""
    return FileResponse(PROJECT_DIR / "naloga4" / "llm.html")


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


class AnalysisRequest(BaseModel):
    period: str
    goal: str


@app.post("/api/ai-analysis")
def ai_analysis(request: AnalysisRequest):
    if request.period not in {"2025", *(f"2025-{month:02d}" for month in range(1, 13))}:
        raise HTTPException(status_code=400, detail="Izberi veljavno obdobje leta 2025.")
    if request.goal not in {
        "Zmanjšanje stroškov", "Zmanjšanje porabe", "Analiza vpliva vremena"
    }:
        raise HTTPException(status_code=400, detail="Izberi veljaven cilj analize.")

    try:
        data_dir = PROJECT_DIR / "naloga1" / "data"
        measurements = zdruzi_podatke(
            read_vreme(data_dir / "vreme.xml"),
            read_cene(data_dir / "cene.xml"),
            read_poraba(data_dir / "poraba.xml"),
        )
        prompt = create_prompt(request.period, request.goal, measurements)
        return analyze_energy(prompt)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail=f"Analize ni bilo mogoče pripraviti: {error}") from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Ponudnik LLM ni vrnil veljavne analize: {error}") from error
