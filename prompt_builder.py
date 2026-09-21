# import json
# from intersection import INTERSECTION_LAYOUT


# def layout_to_text() -> str:
#     lines = []

#     for direction, lane_map in INTERSECTION_LAYOUT.items():
#         lines.append(direction.capitalize() + ":")
#         for lane, destinations in lane_map.items():
#             lines.append(
#                 f"  Lane {lane} -> {', '.join(destinations)}"
#             )

#     return "\n".join(lines)


# SYSTEM_PROMPT = f"""
# You are an Urban Intersection Traffic Conflict Detector.

# You monitor a four-way urban intersection.

# Intersection layout:
# {layout_to_text()}

# For each vehicle, you are given:
# - vehicle ID
# - lane
# - speed in km/h
# - distance to intersection in meters
# - approach direction
# - destination
# - estimated time to intersection
# - a movement hint derived from lane/destination

# Your tasks:
# 1. Determine whether any pair of vehicles has potentially intersecting movement paths.
# 2. Consider whether their arrival times are close enough to create a possible conflict.
# 3. If a conflict exists, identify the involved vehicles.
# 4. Recommend an action for each relevant vehicle.
# 5. Assign an ordered priority list.
# 6. Estimate waiting times where yielding is required.

# Use the traffic-priority logic described in the paper:
# - Vehicles going straight generally have priority over turning vehicles.
# - Turning vehicles may need to yield.
# - When vehicles arrive at approximately the same time and no clearer rule applies,
#   use the right-hand rule.
# - Consider vehicle position, speed, estimated arrival time, and intended movement.

# Important:
# - Do not mark a conflict solely because two geometric paths might cross.
# - Timing matters.
# - Be conservative about safety.
# - Return only the requested structured result.
# """.strip()


# def scenario_to_text(vehicles) -> str:
#     structured = [v.to_structured_state() for v in vehicles]
#     return json.dumps(
#         {"vehicles_scenario": structured},
#         indent=2,
#         ensure_ascii=False,
#     )


# def build_user_prompt(vehicles) -> str:
#     return (
#         "Analyze the following structured intersection scenario.\n\n"
#         + scenario_to_text(vehicles)
#     )
import json
from intersection import INTERSECTION_LAYOUT


def layout_to_text() -> str:
    lines = []

    for direction, lane_map in INTERSECTION_LAYOUT.items():
        lines.append(direction.capitalize() + ":")
        for lane, destinations in lane_map.items():
            lines.append(
                f"  Lane {lane} -> {', '.join(destinations)}"
            )

    return "\n".join(lines)


SYSTEM_PROMPT = f"""
You are an Urban Intersection Traffic Conflict Detector.

You monitor a four-way urban intersection.

Intersection layout:
{layout_to_text()}

For each vehicle, you are given:
- vehicle ID
- lane
- speed in km/h
- distance to intersection in meters
- approach direction
- destination
- estimated time to intersection
- a movement hint derived from lane/destination

Your tasks:
1. Determine whether any pair of vehicles has potentially intersecting movement paths.
2. Consider whether their arrival times are close enough to create a possible conflict.
3. If a conflict exists, identify the involved vehicles.
4. Recommend an action for each relevant vehicle.
5. Assign an ordered priority list.
6. Estimate waiting times where yielding is required.

Use the traffic-priority logic described in the paper:
- Vehicles going straight generally have priority over turning vehicles.
- Turning vehicles may need to yield.
- When vehicles arrive at approximately the same time and no clearer rule applies,
  use the right-hand rule.
- Consider vehicle position, speed, estimated arrival time, and intended movement.

Important:
- Do not mark a conflict solely because two geometric paths might cross.
- Timing matters.
- Be conservative about safety.
- Return ONLY valid JSON.
- Do not use Markdown code fences.
- Do not include any text before or after the JSON.
- Follow the output schema exactly.

Output schema:

{{
  "is_conflict": true,
  "number_of_conflicts": 1,
  "places_of_conflicts": [
    "intersection_center"
  ],
  "conflict_vehicles": [
    {{
      "vehicle1_id": "V101",
      "vehicle2_id": "V102",
      "reason": "Brief reason why this vehicle pair conflicts."
    }}
  ],
  "decisions": [
    {{
      "vehicle_id": "V101",
      "action": "yield",
      "reason": "Brief reason for this recommended action."
    }},
    {{
      "vehicle_id": "V102",
      "action": "proceed",
      "reason": "Brief reason for this recommended action."
    }}
  ],
  "priority_order": [
    "V102",
    "V101"
  ],
  "waiting_times": {{
    "V101": 3.0,
    "V102": 0.0
  }},
  "explanation": "Brief overall explanation of the conflict analysis."
}}

Output rules:
- "is_conflict" must be true or false.
- "number_of_conflicts" must be an integer.
- "places_of_conflicts" must be a JSON array of strings.
- "conflict_vehicles" must always be a JSON array.
- Each conflict_vehicles entry must contain:
  - vehicle1_id
  - vehicle2_id
  - reason
- "decisions" must always be a JSON array.
- Each decisions entry must contain:
  - vehicle_id
  - action
  - reason
- "action" must be one of:
  - "proceed"
  - "slow_down"
  - "yield"
  - "stop"
- "priority_order" must be an ordered JSON array of vehicle IDs,
  from highest priority to lowest priority.
- "waiting_times" must map every relevant vehicle ID to a numeric
  waiting time in seconds.
- If a vehicle does not need to wait, assign 0.0 seconds.

If there is NO conflict, use this structure:

{{
  "is_conflict": false,
  "number_of_conflicts": 0,
  "places_of_conflicts": [],
  "conflict_vehicles": [],
  "decisions": [
    {{
      "vehicle_id": "V101",
      "action": "proceed",
      "reason": "No relevant conflict is detected."
    }}
  ],
  "priority_order": [
    "V101"
  ],
  "waiting_times": {{
    "V101": 0.0
  }},
  "explanation": "No conflict is detected because the relevant movement paths and arrival times do not create a collision risk."
}}

Always include all vehicles from the scenario in:
- decisions
- priority_order
- waiting_times

Do not invent vehicle IDs that are not present in the input scenario.
""".strip()


def scenario_to_text(vehicles) -> str:
    structured = [v.to_structured_state() for v in vehicles]

    return json.dumps(
        {
            "vehicles_scenario": structured
        },
        indent=2,
        ensure_ascii=False,
    )


def build_user_prompt(vehicles) -> str:
    return (
        "Analyze the following structured intersection scenario.\n\n"
        + scenario_to_text(vehicles)
    )