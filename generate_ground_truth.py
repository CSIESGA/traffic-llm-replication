import argparse
import json
from pathlib import Path
from parser import load_scenario
from ground_truth import GTConfig, analyze_ground_truth


def main():
    ap = argparse.ArgumentParser(description="Generate ground-truth JSON with an explicit backend.")
    ap.add_argument("--scenario", help="Single scenario JSON")
    ap.add_argument("--input-dir", default=None, help="Directory containing scenario JSON files")
    ap.add_argument("--output-dir", default=None, help="Defaults to data/ground_truth_<backend>.")
    ap.add_argument(
        "--backend", choices=["official", "reconstruction"], default="official",
        help="Use authors' Zenodo code (preferred) or the separate reconstruction baseline.",
    )
    ap.add_argument(
        "--temporal-threshold", type=float, default=2.5,
        help="Reconstruction backend only; ignored by the official backend.",
    )
    args = ap.parse_args()

    if not args.scenario and not args.input_dir:
        ap.error("Use --scenario or --input-dir")

    cfg = GTConfig(temporal_threshold_s=args.temporal_threshold)
    files = [Path(args.scenario)] if args.scenario else sorted(Path(args.input_dir).glob("*.json"))
    out_dir = Path(args.output_dir or f"data/ground_truth_{args.backend}")
    out_dir.mkdir(parents=True, exist_ok=True)

    for path in files:
        vehicles = load_scenario(str(path))
        result = analyze_ground_truth(vehicles, cfg=cfg, backend=args.backend)
        out = out_dir / f"{path.stem}_gt.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(
            f"{path.name}: backend={args.backend} conflict={result['is_conflict']} "
            f"pairs={result['number_of_conflicts']} -> {out}"
        )


if __name__ == "__main__":
    main()
