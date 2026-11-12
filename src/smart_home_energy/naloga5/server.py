from concurrent import futures
import time
import xml.etree.ElementTree as ET
import grpc

from smart_home_energy.naloga5 import (
    energy_pb2,
    energy_pb2_grpc,
)

from smart_home_energy.naloga5.data_service import (
    DataUnavailableError,
    get_consumption,
    get_statistics,
    get_cheapest_hours,
    get_all_prices,
)


class EnergyService(
    energy_pb2_grpc.EnergyServiceServicer
):

    # 1. Pridobivanje porabe
    def GetConsumption(self, request, context):

        try:
            records = get_consumption(request.period)

            if not records:
                context.abort(
                    grpc.StatusCode.NOT_FOUND,
                    "Za izbrano obdobje ni podatkov."
                )

            measurements = []

            for record in records:

                measurements.append(
                    energy_pb2.ConsumptionPoint(
                        date=record["datum"],
                        hour=record["ura"],
                        consumption_kwh=(
                            record["porabaKWh"] or 0.0
                        ),
                        has_consumption=(
                            record["porabaKWh"] is not None
                        ),
                        temperature=(
                            record["temperatura"] or 0.0
                        ),
                        has_temperature=(
                            record["temperatura"] is not None
                        ),
                        price_eur_kwh=(
                            record["cenaEURKWh"] or 0.0
                        ),
                        has_price=(
                            record["cenaEURKWh"] is not None
                        ),
                    )
                )

            return energy_pb2.ConsumptionResponse(
                measurements=measurements
            )

        except DataUnavailableError as error:
            context.abort(grpc.StatusCode.NOT_FOUND, str(error))
        except ValueError as error:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                str(error)
            )
        except (OSError, ET.ParseError) as error:
            context.abort(grpc.StatusCode.INTERNAL, f"Napaka pri branju podatkov: {error}")

    # 2. Statistika porabe
    def GetEnergyStatistics(self, request, context):

        try:
            stats = get_statistics(request.period)

            return energy_pb2.EnergyStatisticsResponse(
                **stats
            )

        except DataUnavailableError as error:
            context.abort(grpc.StatusCode.NOT_FOUND, str(error))
        except ValueError as error:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                str(error)
            )
        except (OSError, ET.ParseError) as error:
            context.abort(grpc.StatusCode.INTERNAL, f"Napaka pri branju podatkov: {error}")

    # 3. Najcenejše ure elektrike
    def GetCheapestHours(self, request, context):

        try:
            limit = request.limit or 5

            records = get_cheapest_hours(
                request.period,
                limit
            )

            hours = [
                energy_pb2.CheapestHour(
                    date=record["datum"],
                    hour=record["ura"],
                    price_eur_kwh=record["cenaEURKWh"]
                )
                for record in records
            ]

            return energy_pb2.CheapestHoursResponse(
                hours=hours
            )

        except DataUnavailableError as error:
            context.abort(grpc.StatusCode.NOT_FOUND, str(error))
        except ValueError as error:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                str(error)
            )
        except (OSError, ET.ParseError) as error:
            context.abort(grpc.StatusCode.INTERNAL, f"Napaka pri branju podatkov: {error}")

    # 4. Streaming cen elektrike
    def StreamElectricityPrices(
        self,
        request,
        context
    ):

        try:
            records = get_all_prices(request.period)

            # Omejimo zamik med sporočili.
            interval_ms = max(
                0,
                min(request.interval_ms, 5000)
            )

            for record in records:

                if not context.is_active():
                    break

                yield energy_pb2.ElectricityPrice(
                    date=record["datum"],
                    hour=record["ura"],
                    price_eur_kwh=record["cenaEURKWh"]
                )

                if interval_ms > 0:
                    time.sleep(interval_ms / 1000)

        except DataUnavailableError as error:
            context.abort(grpc.StatusCode.NOT_FOUND, str(error))
        except ValueError as error:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                str(error)
            )
        except (OSError, ET.ParseError) as error:
            context.abort(grpc.StatusCode.INTERNAL, f"Napaka pri branju podatkov: {error}")


def serve():

    server = grpc.server(
        futures.ThreadPoolExecutor(
            max_workers=10
        )
    )

    energy_pb2_grpc.add_EnergyServiceServicer_to_server(
        EnergyService(),
        server
    )

    server.add_insecure_port(
        "127.0.0.1:50051"
    )

    server.start()

    print("gRPC strežnik deluje na portu 50051.")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()
