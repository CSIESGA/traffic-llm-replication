from dataclasses import dataclass, asdict
from math import inf
from intersection import validate_lane_destination, infer_movement


@dataclass
class Vehicle:
    vehicle_id: str
    lane: str
    speed: float
    distance_to_intersection: float
    direction: str
    destination: str

    def validate(self) -> None:
        if not self.vehicle_id:
            raise ValueError("vehicle_id cannot be empty.")
        if self.speed < 0:
            raise ValueError("speed cannot be negative.")
        if self.distance_to_intersection < 0:
            raise ValueError("distance_to_intersection cannot be negative.")

        self.direction = self.direction.lower().strip()
        self.lane = str(self.lane).strip()
        self.destination = str(self.destination).strip().upper()
        validate_lane_destination(self.direction, self.lane, self.destination)

    def speed_mps(self) -> float:
        return self.speed / 3.6

    def time_to_intersection(self) -> float:
        if self.speed == 0:
            return inf
        return self.distance_to_intersection / self.speed_mps()

    def movement(self) -> str:
        return infer_movement(self.lane, self.destination)

    def movement_hint(self) -> str:
        return self.movement()

    def to_structured_state(self) -> dict:
        tti = self.time_to_intersection()
        return {
            **asdict(self),
            "speed_kmh": self.speed,
            "distance_to_intersection_m": self.distance_to_intersection,
            "time_to_intersection_s": None if tti == inf else round(tti, 3),
            "movement": self.movement(),
        }
