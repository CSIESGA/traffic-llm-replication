"""Pinned author simulator bridge; author source files are never modified.

For an existing scenario, inject that scenario into the author's generator and
run generate_dataset(total_records=1). This executes BOTH their pair detection
and their dataset-level priority/waiting aggregation without reimplementing them.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import random
import re
import sys
from threading import RLock

PROJECT_ROOT = Path(__file__).resolve().parent
VENDOR_ROOT = PROJECT_ROOT / "vendor" / "zenodo_14171745"
CONFIG_PATH = PROJECT_ROOT / "official_adapter_config.json"
_LOCK = RLock()
_PACKAGE = "_traffic_author_v100"


class OfficialCodeNotInstalled(RuntimeError):
    pass


class OfficialAdapterNotConfigured(RuntimeError):
    pass


def _read_config():
    if not (VENDOR_ROOT / "manifest.json").exists():
        raise OfficialCodeNotInstalled("Run python install_zenodo_ground_truth.py first.")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not cfg.get("configured") or cfg.get("mode") != "author_v1_dataset":
        raise OfficialAdapterNotConfigured("Expected the pinned author_v1_dataset configuration.")
    return cfg


def verify_author_source() -> dict:
    cfg = _read_config()
    manifest = json.loads((VENDOR_ROOT / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version_doi") != "10.5281/zenodo.14171746":
        raise OfficialAdapterNotConfigured("Unexpected author source version.")
    extracted = (VENDOR_ROOT / "extracted").resolve()
    for name, expected in manifest["extracted_sha256"].items():
        path = (extracted / name).resolve()
        if not path.is_relative_to(extracted) or not path.is_file():
            raise OfficialCodeNotInstalled(f"Missing or invalid author file: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise OfficialAdapterNotConfigured(f"Author file changed: {name}")
    source = (extracted / cfg["source_directory"]).resolve()
    if not source.is_relative_to(extracted):
        raise OfficialAdapterNotConfigured("Author source directory escapes extraction root.")
    return manifest


def official_source_provenance() -> dict:
    manifest = verify_author_source()
    return {
        "concept_doi": manifest["concept_doi"], "version_doi": manifest["version_doi"],
        "version": manifest["version"], "archive_sha256": manifest["archive"]["sha256"],
        "source_repository": manifest["source_repository"],
        "source_sha256": manifest["extracted_sha256"],
        "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "adapter_config_sha256": hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
        "aggregation": "Unmodified src.data_generation.generate_dataset",
        "scope": "Authors' public v1.0.0 release; not a claim of recovered final paper splits.",
    }


def load_author_modules():
    with _LOCK:
        verify_author_source()
        cfg = _read_config()
        source = VENDOR_ROOT / "extracted" / cfg["source_directory"] / "src"
        if _PACKAGE not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                _PACKAGE, source / "__init__.py", submodule_search_locations=[str(source)]
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[_PACKAGE] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(_PACKAGE, None)
                raise
        conflict = importlib.import_module(_PACKAGE + ".conflict_detection")
        generation = importlib.import_module(_PACKAGE + ".data_generation")
        return conflict, generation


def _scenario_dict(vehicles):
    return {"vehicles_scenario": [
        {"vehicle_id": v.vehicle_id, "lane": str(v.lane), "speed": float(v.speed),
         "distance_to_intersection": float(v.distance_to_intersection),
         "direction": v.direction, "destination": v.destination}
        for v in vehicles
    ]}


def label_author_scenario(payload: dict) -> dict:
    """Return the exact author dataset row for a supplied, validated scenario."""
    with _LOCK:
        _, generation = load_author_modules()
        original_generator = generation.generate_vehicle_scenario
        calls = 0

        def supplied_scenario(num_vehicles, intersection_layout, fixed_vehicle_count=True):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise ValueError("Author code rejected supplied scenario; refusing an infinite retry.")
            return deepcopy(payload)

        generation.generate_vehicle_scenario = supplied_scenario
        try:
            frame = generation.generate_dataset(
                total_records=1, num_vehicles=len(payload["vehicles_scenario"]),
                fixed_vehicle_count=True,
            )
        finally:
            generation.generate_vehicle_scenario = original_generator
        return frame.to_dict(orient="records")[0]


def generate_author_records(count: int, num_vehicles: int, fixed_vehicle_count: bool, seed: int):
    """Call the author's balanced generator with a reproducible isolated RNG seed."""
    if count <= 0 or count % 2:
        raise ValueError("Author balanced generation requires a positive even count.")
    if not 2 <= num_vehicles <= 8:
        raise ValueError("This experiment supports 2 through 8 vehicles.")
    with _LOCK:
        _, generation = load_author_modules()
        previous = random.getstate()
        try:
            random.seed(seed)
            return generation.generate_dataset(
                total_records=count, num_vehicles=num_vehicles,
                fixed_vehicle_count=fixed_vehicle_count,
            ).to_dict(orient="records")
        finally:
            random.setstate(previous)


def normalize_official_output(raw: dict, vehicle_ids: list[str]) -> dict:
    """Normalize representation only; preserve the complete original author row."""
    if raw["is_conflict"] not in ("yes", "no"):
        raise ValueError("Unexpected author conflict label.")
    ranks = raw["priority_order"]
    ranked = sorted(
        (vid for vid in vehicle_ids if ranks.get(vid) is not None),
        key=lambda vid: ranks[vid],
    )
    yielding = set()
    for decision in raw["decisions"]:
        match = re.search(r"Vehicle\s+(\S+)\s+must\s+yield\s+to\s+Vehicle", decision)
        if not match:
            raise ValueError(f"Unrecognized author decision: {decision}")
        yielding.add(match.group(1))
    result = {
        "is_conflict": raw["is_conflict"] == "yes",
        "number_of_conflicts": int(raw["number_of_conflicts"]),
        "places_of_conflicts": raw["places_of_conflicts"],
        "conflict_vehicles": raw["conflict_vehicles"],
        "decisions": [{"vehicle_id": vid, "action": "yield" if vid in yielding else "proceed"}
                      for vid in vehicle_ids],
        "decision_normalization": "yield if named as yielding in any author pair decision; otherwise proceed",
        "priority_order": ranked,
        "priority_ranks": ranks,
        "unranked_vehicle_ids": [vid for vid in vehicle_ids if ranks.get(vid) is None],
        "waiting_times": raw["waiting_times"],
        "ground_truth_method": "authors_v1.0.0_generate_dataset",
        "ground_truth_backend": "official_zenodo_14171746",
        "official_raw_output": deepcopy(raw),
    }
    return result


def analyze_official_ground_truth(vehicles):
    vehicles = list(vehicles)
    payload = _scenario_dict(vehicles)
    raw = label_author_scenario(payload)
    result = normalize_official_output(raw, [v.vehicle_id for v in vehicles])
    result["ground_truth_provenance"] = official_source_provenance()
    return result
