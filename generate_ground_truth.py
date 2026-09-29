"""Generate pinned author labels (default), plus a provenance manifest and summary."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from parser import load_scenario
from ground_truth import GTConfig, analyze_ground_truth


def generate_labels(files, out_dir, backend="official", temporal_threshold=2.5):
    files, out_dir = list(files), Path(out_dir)
    if not files:
        raise ValueError("No scenario JSON files found.")
    existing_manifest = out_dir / "ground_truth_manifest.json"
    if existing_manifest.exists():
        previous = json.loads(existing_manifest.read_text(encoding="utf-8"))
        previous_ids = {entry["scenario_id"] for entry in previous["scenarios"]}
        requested_ids = {Path(path).stem for path in files}
        if previous_ids != requested_ids:
            raise ValueError(
                "Output directory belongs to a different scenario scope. "
                "Use a new --output-dir for a subset or expanded batch; existing labels/manifest are preserved."
            )
    results, entries, rows = [], [], []
    cfg = GTConfig(temporal_threshold_s=temporal_threshold)
    for path in files:
        path = Path(path)
        vehicles = load_scenario(str(path))
        result = analyze_ground_truth(vehicles, cfg=cfg, backend=backend)
        result["scenario_id"] = path.stem
        result["scenario_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        out = out_dir / f"{path.stem}_gt.json"
        content = (json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        if out.exists() and out.read_bytes() != content:
            raise FileExistsError(f"Label changed: {out}. Use a new output directory to preserve the previous experiment.")
        results.append((out, content))
        entries.append({
            "scenario_id": path.stem, "scenario_file": path.as_posix(),
            "scenario_sha256": result["scenario_sha256"],
            "ground_truth_file": out.as_posix(),
            "ground_truth_sha256": hashlib.sha256(content).hexdigest(),
        })
        rows.append({
            "scenario": path.stem, "vehicle_count": len(vehicles),
            "is_conflict": result["is_conflict"], "number_of_conflicts": result["number_of_conflicts"],
            "conflict_pairs": " | ".join(
                p["vehicle1_id"] + "--" + p["vehicle2_id"] for p in result["conflict_vehicles"]
            ),
            "ground_truth_backend": result["ground_truth_backend"],
        })
    out_dir.mkdir(parents=True, exist_ok=True)
    for path, content in results:
        path.write_bytes(content)
    manifest = {
        "backend": backend, "n_scenarios": len(entries),
        "conflict_count": sum(r["is_conflict"] for r in rows),
        "no_conflict_count": sum(not r["is_conflict"] for r in rows),
        "scenarios": entries,
    }
    (out_dir / "ground_truth_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with (out_dir / "ground_truth_summary.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--scenario", help="Single scenario JSON")
    group.add_argument("--input-dir", default="data/scenarios")
    ap.add_argument("--output-dir")
    ap.add_argument("--backend", choices=["official", "reconstruction"], default="official")
    ap.add_argument("--temporal-threshold", type=float, default=2.5, help="Reconstruction backend only")
    args = ap.parse_args()
    files = [Path(args.scenario)] if args.scenario else sorted(Path(args.input_dir).glob("*.json"))
    result = generate_labels(files, args.output_dir or f"data/ground_truth_{args.backend}",
                             args.backend, args.temporal_threshold)
    print(f"Generated {result['n_scenarios']} {args.backend} labels: "
          f"conflict={result['conflict_count']}, no_conflict={result['no_conflict_count']}")


if __name__ == "__main__":
    main()
