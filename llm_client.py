import json
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL
from prompt_builder import SYSTEM_PROMPT, build_user_prompt


class TrafficLLMClient:
    def __init__(self, model: str | None = None):
        if not OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. "
                "Copy .env.example to .env and add your key."
            )

        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = model or OPENAI_MODEL

    def analyze(self, vehicles) -> dict:
        user_prompt = build_user_prompt(vehicles)

        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": SYSTEM_PROMPT,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_prompt,
                        }
                    ],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "traffic_conflict_result",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "is_conflict": {"type": "boolean"},
                            "number_of_conflicts": {
                                "type": "integer",
                                "minimum": 0,
                            },
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
                                    "required": [
                                        "vehicle1_id",
                                        "vehicle2_id",
                                        "reason",
                                    ],
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
                                            "enum": [
                                                "proceed",
                                                "slow_down",
                                                "yield",
                                                "stop",
                                            ],
                                        },
                                        "reason": {"type": "string"},
                                    },
                                    "required": [
                                        "vehicle_id",
                                        "action",
                                        "reason",
                                    ],
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
                    },
                }
            },
        )

        return json.loads(response.output_text)
