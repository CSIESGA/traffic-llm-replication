import argparse
import csv
import json
from pathlib import Path

from parser import load_scenario
from llm_client import TrafficLLMClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/scenarios")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    scenario_files = sorted(input_dir.glob("*.json"))

    if not scenario_files:
        raise RuntimeError(
            f"No JSON scenario files found in {input_dir}"
        )

    client = TrafficLLMClient(model=args.model)

    rows = []

    for scenario_file in scenario_files:
        print(f"Analyzing {scenario_file.name}...")

        vehicles = load_scenario(str(scenario_file))
        result = client.analyze(vehicles)

        detail_path = output_dir / f"{scenario_file.stem}_result.json"
        with detail_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        rows.append({
            "scenario": scenario_file.name,
            "is_conflict": result["is_conflict"],
            "number_of_conflicts": result["number_of_conflicts"],
            "priority_order": " > ".join(result["priority_order"]),
            "explanation": result["explanation"],
        })

    csv_path = output_dir / "batch_results.csv"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scenario",
                "is_conflict",
                "number_of_conflicts",
                "priority_order",
                "explanation",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved batch summary to {csv_path}")


if __name__ == "__main__":
    main()
