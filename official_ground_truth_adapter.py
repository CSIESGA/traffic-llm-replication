"""Adapter for the authors' code from Zenodo record 14171745.

We deliberately do not guess the authors' Python entry point. The Zenodo files
must first be downloaded, statically inspected, and then this adapter is mapped
through ``official_adapter_config.json``. This prevents silently substituting our
own logic for the authors' ground truth.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

VENDOR_ROOT = Path("vendor/zenodo_14171745")
EXTRACTED_ROOT = VENDOR_ROOT / "extracted"
CONFIG_PATH = Path("official_adapter_config.json")


class OfficialCodeNotInstalled(RuntimeError):
    pass


class OfficialAdapterNotConfigured(RuntimeError):
    pass


def _scenario_dict(vehicles) -> dict[str, Any]:
    return {
        "vehicles_scenario": [
            {
                "vehicle_id": v.vehicle_id,
                "lane": str(v.lane),
                "speed": float(v.speed),
                "distance_to_intersection": float(v.distance_to_intersection),
                "direction": str(v.direction),
                "destination": str(v.destination),
            }
            for v in vehicles
        ]
    }


def _load_config() -> dict[str, Any]:
    manifest = VENDOR_ROOT / "manifest.json"
    extracted_has_files = EXTRACTED_ROOT.exists() and any(p.is_file() for p in EXTRACTED_ROOT.rglob("*"))
    if not manifest.exists() or not extracted_has_files:
        raise OfficialCodeNotInstalled(
            "Authors' Zenodo code is not installed yet. Run:\n"
            "  python install_zenodo_ground_truth.py\n"
            "The official record is DOI 10.5281/zenodo.14171745."
        )
    if not CONFIG_PATH.exists():
        raise OfficialAdapterNotConfigured(f"Missing adapter config: {CONFIG_PATH}")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not cfg.get("configured"):
        raise OfficialAdapterNotConfigured(
            "Zenodo material may be installed, but the authors' actual entry point has not been mapped yet.\n"
            "Run: python inspect_zenodo_ground_truth.py\n"
            "Then set configured=true and fill module_path/function (or command) in official_adapter_config.json.\n"
            "This project refuses to guess an author function because that would invalidate replication provenance."
        )
    return cfg


def _resolve_under_extracted(relative: str) -> Path:
    if not relative:
        raise OfficialAdapterNotConfigured("official_adapter_config.json has an empty module_path")
    root = EXTRACTED_ROOT.resolve()
    path = (root / relative).resolve()
    if root not in path.parents and path != root:
        raise OfficialAdapterNotConfigured(f"Configured path escapes the Zenodo extracted directory: {relative}")
    if not path.exists():
        raise OfficialAdapterNotConfigured(f"Configured author module does not exist: {path}")
    return path


def _call_python_function(cfg: dict[str, Any], payload: dict[str, Any]) -> Any:
    module_path = _resolve_under_extracted(str(cfg.get("module_path", "")))
    fn_name = str(cfg.get("function", ""))
    if not fn_name:
        raise OfficialAdapterNotConfigured("official_adapter_config.json has an empty function")

    module_dir = str(module_path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location("zenodo14171745_author_module", module_path)
    if spec is None or spec.loader is None:
        raise OfficialAdapterNotConfigured(f"Could not import author module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, fn_name):
        raise OfficialAdapterNotConfigured(f"Function {fn_name!r} not found in {module_path}")
    fn = getattr(module, fn_name)

    input_kind = cfg.get("input_kind", "scenario_dict")
    kwargs = dict(cfg.get("kwargs") or {})
    if input_kind == "scenario_dict":
        return fn(payload, **kwargs)
    if input_kind == "vehicles_list":
        return fn(payload["vehicles_scenario"], **kwargs)
    if input_kind == "scenario_path":
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "scenario.json"
            p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return fn(str(p), **kwargs)
    raise OfficialAdapterNotConfigured(f"Unsupported input_kind: {input_kind}")


def _call_command(cfg: dict[str, Any], payload: dict[str, Any]) -> Any:
    command = cfg.get("command")
    if not isinstance(command, list) or not command:
        raise OfficialAdapterNotConfigured("command mode requires a non-empty command list")
    with tempfile.TemporaryDirectory() as td:
        input_path = Path(td) / "scenario.json"
        output_path = Path(td) / "ground_truth.json"
        input_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        replacements = {
            "{input_json}": str(input_path),
            "{output_json}": str(output_path),
            "{vendor_root}": str(EXTRACTED_ROOT.resolve()),
        }
        resolved = []
        for token in command:
            token = str(token)
            for old, new in replacements.items():
                token = token.replace(old, new)
            resolved.append(token)
        subprocess.run(resolved, check=True, cwd=EXTRACTED_ROOT)
        if not output_path.exists():
            raise RuntimeError("Author command completed but did not create {output_json}.")
        return json.loads(output_path.read_text(encoding="utf-8"))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"yes", "y", "true", "conflict", "conflict detected"}:
            return True
        if v in {"no", "n", "false", "no conflict", "no conflict detected"}:
            return False
    return bool(value)


def _normalize_priority(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, dict):
        # Paper example uses {vehicle_id: numeric priority}, where 1 is highest.
        try:
            return [str(k) for k, _ in sorted(value.items(), key=lambda kv: float(kv[1]))]
        except (TypeError, ValueError):
            return [str(k) for k in value]
    return []


def _normalize_pairs(value: Any) -> list[dict[str, Any]]:
    out = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, dict):
            a = item.get("vehicle1_id") or item.get("vehicle_1_id") or item.get("vehicle1")
            b = item.get("vehicle2_id") or item.get("vehicle_2_id") or item.get("vehicle2")
            if a is not None and b is not None:
                out.append({"vehicle1_id": str(a), "vehicle2_id": str(b), **{k: v for k, v in item.items() if k not in {"vehicle1_id", "vehicle2_id"}}})
    return out


def _normalize_decisions(value: Any, vehicle_ids: list[str]) -> list[dict[str, str]]:
    if isinstance(value, list) and all(isinstance(x, dict) for x in value):
        out = []
        for item in value:
            vid = item.get("vehicle_id")
            action = item.get("action")
            if vid is not None and action is not None:
                out.append({"vehicle_id": str(vid), "action": str(action).lower()})
        return out

    # The paper's example stores textual decisions such as
    # "Potential conflict: Vehicle V1 must yield to Vehicle V2".
    yielding: set[str] = set()
    if isinstance(value, list):
        for line in value:
            if not isinstance(line, str):
                continue
            match = re.search(r"Vehicle\s+(\S+)\s+must\s+yield\s+to\s+Vehicle\s+(\S+)", line, flags=re.I)
            if match:
                yielding.add(match.group(1).rstrip(".,;:"))
    if yielding:
        return [{"vehicle_id": vid, "action": "yield" if vid in yielding else "proceed"} for vid in vehicle_ids]
    return []


def normalize_official_output(raw: Any, vehicle_ids: list[str]) -> dict[str, Any]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise TypeError(f"Author ground-truth function returned {type(raw).__name__}, expected dict/JSON.")

    pairs = _normalize_pairs(raw.get("conflict_vehicles", []))
    result = dict(raw)
    result["is_conflict"] = _as_bool(raw.get("is_conflict", bool(pairs)))
    result["conflict_vehicles"] = pairs
    result["number_of_conflicts"] = int(raw.get("number_of_conflicts", len(pairs)))
    result["places_of_conflicts"] = raw.get("places_of_conflicts") or ["intersection"] * len(pairs)
    result["priority_order"] = _normalize_priority(raw.get("priority_order", []))
    result["decisions"] = _normalize_decisions(raw.get("decisions", []), vehicle_ids)
    result["waiting_times"] = {
        str(k): float(v) for k, v in (raw.get("waiting_times") or {}).items()
    }
    result["ground_truth_method"] = "authors_zenodo_14171745"
    result["official_raw_output"] = raw
    return result


def analyze_official_ground_truth(vehicles) -> dict[str, Any]:
    cfg = _load_config()
    payload = _scenario_dict(vehicles)
    mode = cfg.get("mode", "python_function")
    if mode == "python_function":
        raw = _call_python_function(cfg, payload)
    elif mode == "command":
        raw = _call_command(cfg, payload)
    else:
        raise OfficialAdapterNotConfigured(f"Unsupported official adapter mode: {mode}")
    return normalize_official_output(raw, [v.vehicle_id for v in vehicles])
