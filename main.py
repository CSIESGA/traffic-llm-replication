import argparse
import json
from pathlib import Path
from parser import load_scenario
from prompt_builder import SYSTEM_PROMPT, build_user_prompt
from ground_truth import analyze_ground_truth


def main():
    parser = argparse.ArgumentParser(description="Structured traffic scenario demo + explicit ground-truth backend.")
    parser.add_argument("--scenario", default="data/scenario_example.json")
    parser.add_argument("--ground-truth", action="store_true", help="Print Python ground truth.")
    parser.add_argument(
        "--gt-backend", choices=["official", "reconstruction"], default="official",
        help="Ground-truth backend used with --ground-truth.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print states and prompt; no API call.")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    vehicles = load_scenario(args.scenario)
    print("\n=== VALIDATED / DERIVED VEHICLE STATES ===\n")
    for v in vehicles:
        print(json.dumps(v.to_structured_state(), indent=2))

    if args.ground_truth:
        print(f"\n=== PYTHON GROUND TRUTH ({args.gt_backend.upper()}) ===\n")
        print(json.dumps(analyze_ground_truth(vehicles, backend=args.gt_backend), indent=2, ensure_ascii=False))

    print("\n=== SYSTEM PROMPT ===\n" + SYSTEM_PROMPT)
    print("\n=== USER PROMPT ===\n" + build_user_prompt(vehicles))

    if args.dry_run or args.ground_truth:
        return
    from llm_client import TrafficLLMClient
    result = TrafficLLMClient(model=args.model).analyze(vehicles)
    print("\n=== LLM RESULT ===\n" + json.dumps(result, indent=2, ensure_ascii=False))
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    (out / (Path(args.scenario).stem + "_result.json")).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
