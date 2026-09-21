TRAFFIC_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_conflict": {"type": "boolean"},
        "number_of_conflicts": {"type": "integer", "minimum": 0},
        "places_of_conflicts": {
            "type": "array",
            "items": {"type": "string"},
        },
        "conflict_vehicles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "vehicle1_id": {"type": "string"},
                    "vehicle2_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["vehicle1_id", "vehicle2_id", "reason"],
                "additionalProperties": False,
            },
        },
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "vehicle_id": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["proceed", "slow_down", "yield", "stop"],
                    },
                    "reason": {"type": "string"},
                },
                "required": ["vehicle_id", "action", "reason"],
                "additionalProperties": False,
            },
        },
        "priority_order": {
            "type": "array",
            "items": {"type": "string"},
        },
        "waiting_times": {
            "type": "object",
            "additionalProperties": {"type": "number"},
        },
        "explanation": {"type": "string"},
    },
    "required": [
        "is_conflict",
        "number_of_conflicts",
        "places_of_conflicts",
        "conflict_vehicles",
        "decisions",
        "priority_order",
        "waiting_times",
        "explanation",
    ],
    "additionalProperties": False,
}
