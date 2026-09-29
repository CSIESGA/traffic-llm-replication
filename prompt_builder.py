"""Author v1.0.0 binary-classification wording for manual experiments.

Source: sarimasri3/Intersection-Conflict-Detection, tag v1.0.0:
  run_evaluation.py::system_instruction
  gpt_finetuning/prepare_data.py::parse_scenario_to_string
  gpt_finetuning/prepare_data.py::prepare_test_data_for_gpt

Only the six original input fields are serialized. In particular, neither
derived movement/TTI nor simulator answers are injected into the prompt.
Manual chat cannot assign a real system-role message; the combined text below
preserves the author's wording and makes the two original sections explicit.
"""

from collections.abc import Iterable

from vehicle import Vehicle


PROTOCOL_NAME = "author_v1_binary_manual"
EXPECTED_OUTPUT = "yes_or_no"
AUTHOR_TAG = "v1.0.0"
PROMPT_SOURCES = [
    "https://github.com/sarimasri3/Intersection-Conflict-Detection/blob/v1.0.0/run_evaluation.py",
    "https://github.com/sarimasri3/Intersection-Conflict-Detection/blob/v1.0.0/gpt_finetuning/prepare_data.py",
]

# Exact author's system instruction, excluding surrounding whitespace.
SYSTEM_PROMPT = """
You are an Urban Intersection Traffic Conflict Detector, responsible for monitoring a four-way intersection with traffic coming from the north, east, south, and west. Each direction has two lanes guiding vehicles to different destinations:

- North: Lane 1 directs vehicles to F and H, Lane 2 directs vehicles to E, D, and C.
- East: Lane 3 leads to H and B, Lane 4 leads to G, E, and F.
- South: Lane 5 directs vehicles to B and D, Lane 6 directs vehicles to A, G, and H.
- West: Lane 7 directs vehicles to D and F, Lane 8 directs vehicles to B, C, and A.

Analyze the traffic data from all directions and lanes, and determine if there is a potential conflict between vehicles at the intersection. Respond only with 'yes' or 'no'.
""".strip()


def scenario_to_text(vehicles: Iterable[Vehicle]) -> str:
    """Render the author's natural-language template in original vehicle order.

    The author's formatting rounds speed and distance to two decimal places.
    The input Scenario itself is not modified or enriched.
    """
    return " ".join(
        f"Vehicle {vehicle.vehicle_id} is in lane {vehicle.lane}, "
        f"moving {vehicle.direction} at a speed of {vehicle.speed:.2f} km/h, "
        f"and is {vehicle.distance_to_intersection:.2f} meters away from the "
        f"intersection, heading towards {vehicle.destination}."
        for vehicle in vehicles
    )


def build_user_prompt(vehicles: Iterable[Vehicle]) -> str:
    """Match the author's classification test message, without its true label."""
    return (
        "Analyze the following scenario and determine if there is a conflict "
        "(Respond only with 'yes' or 'no'): "
        + scenario_to_text(vehicles)
    )


def build_manual_prompt(vehicles: Iterable[Vehicle]) -> str:
    """Combine system/user text into a single copy-and-paste message."""
    return (
        "=== SYSTEM INSTRUCTION ===\n"
        + SYSTEM_PROMPT
        + "\n\n=== SCENARIO ===\n"
        + build_user_prompt(vehicles)
        + "\n"
    )


DETAILED_PROTOCOL_NAME = "project_detailed_v1_full_precision"
DETAILED_EXPECTED_OUTPUT = "legacy_eight_field_json"
DETAILED_SYSTEM_PROMPT = SYSTEM_PROMPT.split("Analyze the traffic data")[0].strip() + """

Analyze potential vehicle conflicts using intended paths and arrival timing. Give
recommended actions, a priority order, and waiting-time estimates. Distinguish
your traffic judgment from information that the input does not establish.

Return ONLY one valid JSON object, with exactly these eight keys:
- is_conflict: boolean.
- number_of_conflicts: nonnegative integer, counting distinct unordered vehicle pairs.
- places_of_conflicts: one location string per reported pair. Use "intersection"
  when a more precise location is not established; do not invent coordinates.
- conflict_vehicles: array of objects with vehicle1_id, vehicle2_id, and reason.
  List each conflicting pair once. Each reason is a brief justification.
- decisions: one object per input vehicle, with vehicle_id, action, and reason.
  action must be "proceed", "slow_down", "yield", or "stop".
- priority_order: array containing every input vehicle ID exactly once, highest
  recommended priority first. Put the vehicles you identify as conflicting first,
  followed by non-conflicting vehicles in input order.
- waiting_times: object mapping every input vehicle ID to a nonnegative finite
  number of seconds; use 0 when no waiting is needed.
- explanation: brief overall justification and any important uncertainty.

If no conflict is found, set is_conflict to false, number_of_conflicts to 0,
places_of_conflicts and conflict_vehicles to empty arrays. Still include every
vehicle in decisions, priority_order, and waiting_times.
Use only vehicle IDs from the input. Make the reported count and boolean agree
with the listed pairs. Give concise reasons (about 20 words each) and an overall
explanation of about 40 words. Do not use Markdown fences or text outside JSON.
"""


def detailed_scenario_to_text(vehicles: Iterable[Vehicle]) -> str:
    """Six original fields, without rounding away numeric information or GT hints."""
    return " ".join(
        f"Vehicle {v.vehicle_id} is in lane {v.lane}, moving {v.direction} "
        f"at a speed of {v.speed!r} km/h, and is {v.distance_to_intersection!r} "
        f"meters away from the intersection, heading towards {v.destination}."
        for v in vehicles
    )


def build_detailed_prompt(vehicles: Iterable[Vehicle]) -> str:
    """Project extension matching archived answer keys, not an original author prompt."""
    return ("=== SYSTEM INSTRUCTION ===\n" + DETAILED_SYSTEM_PROMPT
            + "\n\n=== SCENARIO ===\n" + detailed_scenario_to_text(vehicles) + "\n")
