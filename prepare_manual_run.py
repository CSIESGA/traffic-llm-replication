"""Freeze a label-free shuffled trial order and blank human-recorded run metadata."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random


def prepare_run(prompt_manifest, order_path, metadata_path, seed=20260928):
    prompt_manifest, order_path, metadata_path = map(Path, (prompt_manifest, order_path, metadata_path))
    if order_path.exists() or metadata_path.exists():
        raise FileExistsError("Trial order/run metadata already exists; choose new paths for a new run.")
    manifest = json.loads(prompt_manifest.read_text(encoding="utf-8"))
    trials = list(manifest["prompts"])
    for entry in trials:
        for prefix in ("scenario", "prompt"):
            path = Path(entry[prefix + "_file"])
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry[prefix + "_sha256"]:
                raise ValueError(f"File changed after prompt export: {path}")
    random.Random(seed).shuffle(trials)
    order_path.parent.mkdir(parents=True, exist_ok=True)
    with order_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["trial", "scenario_id", "prompt_file", "answer_filename"])
        writer.writeheader()
        for index, entry in enumerate(trials, 1):
            writer.writerow({"trial": index, "scenario_id": entry["scenario_id"],
                             "prompt_file": entry["prompt_file"],
                             "answer_filename": entry["scenario_id"] + ".txt"})
    metadata = {
        "run_id": "manual_author_v1_20260928",
        "protocol": manifest["protocol"], "task": "scenario_conflict_binary_classification",
        "n_planned_scenarios": len(trials), "trial_order_seed": seed,
        "trial_order_file": order_path.as_posix(),
        "trial_order_sha256": hashlib.sha256(order_path.read_bytes()).hexdigest(),
        "prompt_manifest_file": prompt_manifest.as_posix(),
        "prompt_manifest_sha256": hashlib.sha256(prompt_manifest.read_bytes()).hexdigest(),
        "model_name_as_shown": None, "model_version_if_known": None,
        "interface_used": None, "started_at_with_timezone": None, "finished_at_with_timezone": None,
        "memory_setting": None, "custom_instructions_setting": None,
        "new_chat_per_scenario": True, "first_response_only": True, "api_used": False,
        "notes": "Fill observed model/interface/date/settings before collection. Unknown version stays null. No predictions have been collected for this run.",
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(trials)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prompt-manifest", default="prompts/prompt_manifest.json")
    ap.add_argument("--order-path", default="data/manual_trial_order.csv")
    ap.add_argument("--metadata-path", default="EXPERIMENT_RUN.json")
    ap.add_argument("--seed", type=int, default=20260928)
    args = ap.parse_args()
    count = prepare_run(args.prompt_manifest, args.order_path, args.metadata_path, args.seed)
    print(f"Prepared {count} label-free trials. Fill model/date in {args.metadata_path}.")


if __name__ == "__main__":
    main()
