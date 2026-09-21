INTERSECTION_LAYOUT = {
    "north": {"1": ["F", "H"], "2": ["E", "D", "C"]},
    "east": {"3": ["H", "B"], "4": ["G", "E", "F"]},
    "south": {"5": ["B", "D"], "6": ["A", "G", "H"]},
    "west": {"7": ["D", "F"], "8": ["B", "C", "A"]},
}

LANE_TO_DIRECTION = {
    "1": "north", "2": "north", "3": "east", "4": "east",
    "5": "south", "6": "south", "7": "west", "8": "west",
}

# Exact movement classification reconstructed from Figure 4 and the lane/destination
# rules stated in Table 2 of the paper.  The approach labels are kept exactly as
# the paper uses them, even though the drawing is visually rotated.
MOVEMENTS = {
    ("1", "F"): "straight", ("1", "H"): "right",
    ("2", "E"): "straight", ("2", "D"): "left", ("2", "C"): "left",
    ("3", "H"): "straight", ("3", "B"): "right",
    ("4", "G"): "straight", ("4", "E"): "left", ("4", "F"): "left",
    ("5", "B"): "straight", ("5", "D"): "right",
    ("6", "A"): "straight", ("6", "G"): "left", ("6", "H"): "left",
    ("7", "D"): "straight", ("7", "F"): "right",
    ("8", "C"): "straight", ("8", "B"): "left", ("8", "A"): "left",
}

# Clockwise order of approach directions in the paper's Figure 4 drawing.
CLOCKWISE_APPROACHES = ["west", "north", "east", "south"]


def validate_lane_destination(direction: str, lane: str, destination: str) -> None:
    if direction not in INTERSECTION_LAYOUT:
        raise ValueError(f"Unknown approach direction: {direction}")
    if lane not in INTERSECTION_LAYOUT[direction]:
        raise ValueError(f"Lane {lane} is not valid for direction {direction}.")
    if destination not in INTERSECTION_LAYOUT[direction][lane]:
        allowed = INTERSECTION_LAYOUT[direction][lane]
        raise ValueError(
            f"Destination {destination} is invalid for direction={direction}, "
            f"lane={lane}. Allowed: {allowed}"
        )


def infer_movement(lane: str, destination: str) -> str:
    return MOVEMENTS.get((str(lane), str(destination).upper()), "unknown")


def infer_movement_hint(lane: str, destination: str) -> str:
    # Backward-compatible alias used by the old demo.
    return infer_movement(lane, destination)


def direction_on_right(direction: str) -> str:
    """Return the approach that is on this vehicle's right in the drawing."""
    i = CLOCKWISE_APPROACHES.index(direction)
    return CLOCKWISE_APPROACHES[(i - 1) % len(CLOCKWISE_APPROACHES)]
