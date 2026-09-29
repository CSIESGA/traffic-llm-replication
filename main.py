"""Preview or save one manual prompt; no API key or model API is used."""

import argparse
import json
from pathlib import Path

from ground_truth import analyze_ground_truth
from parser import load_scenario
from prompt_builder import build_manual_prompt, build_detailed_prompt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", default="data/scenario_example.json")
    ap.add_argument("--protocol", choices=["detailed", "binary"], default="detailed")
    ap.add_argument("--save-prompt", metavar="PATH", help="Save only the copy-and-paste prompt to PATH.")
    ap.add_argument("--overwrite", action="store_true", help="Replace a differing saved prompt.")
    ap.add_argument("--ground-truth", action="store_true", help="Print GT separately after the prompt; never include it in the saved prompt.")
    ap.add_argument("--gt-backend", choices=["official", "reconstruction"], default="official")
    ap.add_argument("--dry-run", action="store_true", help="Compatibility flag: preview is already the default; never calls an API.")
    args = ap.parse_args()

    vehicles = load_scenario(args.scenario)
    prompt = (build_detailed_prompt if args.protocol == "detailed" else build_manual_prompt)(vehicles)
    if args.save_prompt:
        target = Path(args.save_prompt)
        content = prompt.encode("utf-8")
        if target.exists() and target.read_bytes() != content and not args.overwrite:
            raise FileExistsError(f"Refusing to replace {target}; choose another path or pass --overwrite.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    print(prompt, end="")

    if args.ground_truth:
        print("\n=== GROUND TRUTH: FOR LOCAL CHECKING ONLY; DO NOT PASTE INTO LLM ===")
        print(json.dumps(analyze_ground_truth(vehicles, backend=args.gt_backend), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
