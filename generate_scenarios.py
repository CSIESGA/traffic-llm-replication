"""Generate new local scenarios with the archived authors' unmodified code.

These samples are NOT the paper's recovered original 10,000 scenarios.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import official_ground_truth_adapter as author_adapter
from vehicle import Vehicle

GROUPS = (("four", 4, True), ("eight", 8, True), ("mixed", 8, False))
SCENARIO_NAME = re.compile(r"scenario_(\d+)\.json$")
GENERATOR_FUNCTION = "src.data_generation.generate_dataset"


def _validate_payload(payload: Any, source: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("vehicles_scenario"), list):
        raise ValueError(f"{source}: expected a JSON object with a vehicles_scenario list")
    records = payload["vehicles_scenario"]
    if len(records) < 2:
        raise ValueError(f"{source}: at least two vehicles are required")
    seen_ids: set[str] = set()
    for raw in records:
        if not isinstance(raw, dict):
            raise ValueError(f"{source}: each vehicle must be a JSON object")
        try:
            vehicle = Vehicle(
                vehicle_id=str(raw["vehicle_id"]), lane=str(raw["lane"]),
                speed=float(raw["speed"]),
                distance_to_intersection=float(raw["distance_to_intersection"]),
                direction=str(raw["direction"]), destination=str(raw["destination"]),
            )
            if not math.isfinite(vehicle.speed) or not math.isfinite(vehicle.distance_to_intersection):
                raise ValueError("speed and distance must be finite")
            vehicle.validate()
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{source}: invalid vehicle: {exc}") from exc
        if vehicle.vehicle_id in seen_ids:
            raise ValueError(f"{source}: duplicate vehicle ID {vehicle.vehicle_id}")
        seen_ids.add(vehicle.vehicle_id)
    return records


def scenario_state_sha256(payload: dict[str, Any]) -> str:
    """Physical-state fingerprint ignoring arbitrary IDs and vehicle order."""
    states = [
        {
            "lane": str(v["lane"]).strip(), "speed": float(v["speed"]),
            "distance_to_intersection": float(v["distance_to_intersection"]),
            "direction": str(v["direction"]).strip().lower(),
            "destination": str(v["destination"]).strip().upper(),
        }
        for v in payload["vehicles_scenario"]
    ]
    canonical = sorted(json.dumps(s, sort_keys=True, separators=(",", ":"), allow_nan=False) for s in states)
    return hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode("utf-8")).hexdigest()


def _label(value: Any) -> bool:
    if value is True or value == "yes":
        return True
    if value is False or value == "no":
        return False
    raise ValueError(f"Unexpected author is_conflict value: {value!r}")


def _json_bytes(payload: Any) -> bytes:
    # Preserve author-generated floating point values without decimal rounding.
    return (json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def generate_scenario_batch(
    *, per_group: int = 100, seed: int = 20260928,
    output_dir: Path | str = Path("data/scenarios"),
    manifest_path: Path | str = Path("data/scenario_generation_manifest.json"),
) -> dict[str, Any]:
    """Validate a complete balanced batch in memory, then append without overwrite.

    For a subsequent batch specify both a new manifest path and a new seed.
    An existing manifest deliberately stops accidental repeated generation.
    """
    if per_group <= 0 or per_group % 2:
        raise ValueError("--per-group must be a positive even integer for exact author balancing")
    output_dir, manifest_path = Path(output_dir), Path(manifest_path)
    if manifest_path.exists():
        raise FileExistsError(
            f"Generation manifest already exists: {manifest_path}. This batch will not "
            "be generated again. For a new batch choose another --manifest path and a new --seed."
        )
    if output_dir.exists() and not output_dir.is_dir():
        raise NotADirectoryError(output_dir)

    next_number, existing_count = 1, 0
    known_states: dict[str, str] = {}
    for path in sorted(output_dir.glob("scenario_*.json")):
        match = SCENARIO_NAME.fullmatch(path.name)
        if match is None:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        _validate_payload(payload, str(path))
        known_states.setdefault(scenario_state_sha256(payload), str(path))
        next_number = max(next_number, int(match.group(1)) + 1)
        existing_count += 1

    provenance = author_adapter.official_source_provenance()
    entries, pending, group_summaries = [], [], []
    for offset, (group, num_vehicles, fixed) in enumerate(GROUPS):
        group_seed = seed + offset
        params = dict(count=per_group, num_vehicles=num_vehicles, fixed_vehicle_count=fixed, seed=group_seed)
        records = author_adapter.generate_author_records(**params)
        if len(records) != per_group:
            raise ValueError(f"Author generator returned {len(records)} {group} records, expected {per_group}")
        labels: Counter[bool] = Counter()
        vehicle_counts: Counter[int] = Counter()
        for record_index, raw in enumerate(records, start=1):
            payload = json.loads(raw["scenario"])
            vehicles = _validate_payload(payload, f"{group} record {record_index}")
            if (fixed and len(vehicles) != num_vehicles) or (not fixed and not 2 <= len(vehicles) <= num_vehicles):
                raise ValueError(f"Unexpected vehicle count for {group}: {len(vehicles)}")
            is_conflict = _label(raw["is_conflict"])
            signature = scenario_state_sha256(payload)
            scenario_id = f"scenario_{next_number:03d}"
            output_path = output_dir / f"{scenario_id}.json"
            if signature in known_states:
                raise ValueError(
                    f"Duplicate scenario state in {group} record {record_index}; already present "
                    f"as {known_states[signature]}. IDs and vehicle order are ignored. "
                    "No new scenarios have been written; use a new seed."
                )
            if output_path.exists() or output_path.resolve() == manifest_path.resolve():
                raise FileExistsError(f"Refusing to overwrite an existing/reserved path: {output_path}")
            content = _json_bytes(payload)
            known_states[signature] = scenario_id
            pending.append((output_path, content))
            entries.append({
                "scenario_id": scenario_id, "path": output_path.as_posix(),
                "source_group": group, "seed": group_seed,
                "record_index_within_group": record_index, "vehicle_count": len(vehicles),
                "is_conflict": is_conflict, "author_label": "yes" if is_conflict else "no",
                "sha256": hashlib.sha256(content).hexdigest(),
                "state_sha256_ignoring_vehicle_ids_and_order": signature,
                "generation_parameters": params, "generator_function": GENERATOR_FUNCTION,
                "source_provenance_ref": "author_source_provenance",
            })
            labels[is_conflict] += 1
            vehicle_counts[len(vehicles)] += 1
            next_number += 1
        if labels[True] != per_group // 2 or labels[False] != per_group // 2:
            raise ValueError(f"Author {group} group is not balanced: {dict(labels)}; no new files written")
        group_summaries.append({
            "group": group, "generation_parameters": params,
            "conflict_count": labels[True], "no_conflict_count": labels[False],
            "vehicle_count_distribution": dict(sorted(vehicle_counts.items())),
        })

    manifest = {
        "schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_origin": "new_local_sample_from_unmodified_author_generator",
        "not_original_paper_dataset": True,
        "scope_note": (
            "Generated locally from the archived authors' v1.0.0 code; these are not recovered "
            "members of the paper's original 10,000-scenario dataset and have not been assigned "
            "paper training/validation/test splits."
        ),
        "generator_function": GENERATOR_FUNCTION, "author_source_provenance": provenance,
        "base_seed": seed, "per_group": per_group, "new_scenario_count": len(entries),
        "preexisting_scenario_count": existing_count,
        "sampling": {
            "direction": "uniform random choice from north/east/south/west",
            "lane": "author random choice from the selected direction's valid lanes",
            "destination": "author random choice from destinations allowed for the selected lane",
            "speed_kmh": {"distribution": "uniform", "minimum": 20, "maximum": 80},
            "distance_to_intersection_m": {"distribution": "uniform", "minimum": 50, "maximum": 500},
            "mixed_vehicle_count": {"distribution": "discrete uniform", "minimum": 2, "maximum": 8},
            "balancing": "author rejection sampling until equal conflict/no-conflict counts per group",
            "precision": "author floating-point values retained; no decimal rounding",
            "distribution_note": "Balanced acceptance changes the final joint distribution from raw random proposals.",
        },
        "duplicate_policy": "Reject duplicate physical states across existing/new scenarios, ignoring IDs and vehicle order.",
        "groups": group_summaries, "scenarios": entries,
    }
    manifest_content = _json_bytes(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    for path, content in pending:
        with path.open("xb") as handle:
            handle.write(content)
    with manifest_path.open("xb") as handle:
        handle.write(manifest_content)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-group", type=int, default=100, help="Positive even count for EACH of four/eight/mixed groups")
    parser.add_argument("--seed", type=int, default=20260928, help="Group seeds are this value, +1 and +2")
    parser.add_argument("--output-dir", default="data/scenarios")
    parser.add_argument("--manifest", default="data/scenario_generation_manifest.json")
    args = parser.parse_args()
    try:
        result = generate_scenario_batch(per_group=args.per_group, seed=args.seed, output_dir=args.output_dir, manifest_path=args.manifest)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Scenario generation failed: {exc}\n")
    print(f"Generated {result['new_scenario_count']} new local scenarios using {GENERATOR_FUNCTION}.")
    for group in result["groups"]:
        print(f"  {group['group']}: conflict={group['conflict_count']}, no_conflict={group['no_conflict_count']}, seed={group['generation_parameters']['seed']}")
    print(f"Preserved {result['preexisting_scenario_count']} existing scenarios. Manifest: {args.manifest}")
    print("This is a newly sampled dataset, not the paper's recovered original 10,000 scenarios.")


if __name__ == "__main__":
    main()
