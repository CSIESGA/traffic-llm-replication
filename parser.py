import json
from pathlib import Path
from vehicle import Vehicle


def load_scenario(path: str) -> list[Vehicle]:
    scenario_path = Path(path)

    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    with scenario_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if "vehicles_scenario" not in data:
        raise ValueError("JSON must contain a 'vehicles_scenario' list.")

    vehicles = []
    seen_ids = set()

    for raw in data["vehicles_scenario"]:
        vehicle = Vehicle(
            vehicle_id=str(raw["vehicle_id"]),
            lane=str(raw["lane"]),
            speed=float(raw["speed"]),
            distance_to_intersection=float(raw["distance_to_intersection"]),
            direction=str(raw["direction"]),
            destination=str(raw["destination"]),
        )

        vehicle.validate()

        if vehicle.vehicle_id in seen_ids:
            raise ValueError(f"Duplicate vehicle ID: {vehicle.vehicle_id}")

        seen_ids.add(vehicle.vehicle_id)
        vehicles.append(vehicle)

    if len(vehicles) < 2:
        raise ValueError("At least two vehicles are required.")

    return vehicles
