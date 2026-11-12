import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from smart_home_energy.naloga3.open_data import (
    get_chart_data,
    get_filter_options,
)
from pydantic import BaseModel
from smart_home_energy.naloga4.prompts import create_prompt
from smart_home_energy.naloga4.llm_service import analyze_energy
from smart_home_energy.naloga5 import energy_pb2, energy_pb2_grpc
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


def grpc_stub():
    """Odpre gRPC kanal in vrne klienta storitve."""
    import grpc

    channel = grpc.insecure_channel("127.0.0.1:50051")
    return channel, energy_pb2_grpc.EnergyServiceStub(channel)


def grpc_http_error(error):
    """Pretvori gRPC napako v ustrezen HTTP odgovor."""
    import grpc

    if error.code() == grpc.StatusCode.NOT_FOUND:
        status = 404
    elif error.code() == grpc.StatusCode.INVALID_ARGUMENT:
        status = 400
    else:
        status = 502
    return HTTPException(status_code=status, detail=error.details())


@app.get("/grpc", include_in_schema=False)
def grpc_page() -> FileResponse:
    """Vrne stran za prikaz podatkov, pridobljenih prek gRPC."""
    return FileResponse(PROJECT_DIR / "naloga5" / "energy.html")


@app.get("/api/grpc/consumption")
def grpc_consumption(period: str = Query(pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$")):
    import grpc

    channel, stub = grpc_stub()
    try:
        response = stub.GetConsumption(energy_pb2.PeriodRequest(period=period), timeout=10)
        return [{
            "date": item.date,
            "hour": item.hour,
            "consumption_kwh": item.consumption_kwh if item.has_consumption else None,
            "temperature": item.temperature if item.has_temperature else None,
            "price_eur_kwh": item.price_eur_kwh if item.has_price else None,
        } for item in response.measurements]
    except grpc.RpcError as error:
        raise grpc_http_error(error) from error
    finally:
        channel.close()


@app.get("/api/grpc/statistics")
def grpc_statistics(period: str = Query(pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$")):
    import grpc

    channel, stub = grpc_stub()
    try:
        response = stub.GetEnergyStatistics(energy_pb2.PeriodRequest(period=period), timeout=10)
        fields = (
            "measurement_count", "total_consumption_kwh", "average_consumption_kwh",
            "max_consumption_kwh", "min_consumption_kwh", "estimated_cost_eur",
        )
        return {field: getattr(response, field) for field in fields}
    except grpc.RpcError as error:
        raise grpc_http_error(error) from error
    finally:
        channel.close()


@app.get("/api/grpc/cheapest")
def grpc_cheapest(
    period: str = Query(pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$"),
    limit: int = Query(default=5, ge=1, le=100),
):
    import grpc

    channel, stub = grpc_stub()
    try:
        response = stub.GetCheapestHours(
            energy_pb2.CheapestHoursRequest(period=period, limit=limit), timeout=10
        )
        return [
            {"date": item.date, "hour": item.hour, "price_eur_kwh": item.price_eur_kwh}
            for item in response.hours
        ]
    except grpc.RpcError as error:
        raise grpc_http_error(error) from error
    finally:
        channel.close()


@app.get("/api/grpc/stream")
def grpc_price_stream(
    period: str = Query(pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$"),
    interval_ms: int = Query(default=100, ge=0, le=5000),
):
    import grpc

    def events():
        channel, stub = grpc_stub()
        try:
            request = energy_pb2.PriceStreamRequest(period=period, interval_ms=interval_ms)
            for item in stub.StreamElectricityPrices(request, timeout=120):
                payload = {
                    "date": item.date,
                    "hour": item.hour,
                    "price_eur_kwh": item.price_eur_kwh,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except grpc.RpcError as error:
            payload = {"message": error.details() or "Napaka gRPC."}
            yield f"event: error\ndata: {json.dumps(payload)}\n\n"
        finally:
            channel.close()

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })



