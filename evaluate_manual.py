"""Evaluate manually saved conflict answers without calling a model.

The primary task matches the authors' binary classification experiment. A .txt
answer must contain only yes/no, optionally inside one plain/text code fence. A
.json answer must contain is_conflict as a boolean or yes/no string.
Other legacy JSON fields are accepted but are not scored. Missing or invalid
answers stay unscored and are visible in coverage and the per-scenario CSV.
Undefined metrics are JSON null, never NaN or an invented perfect/zero score.
"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


CSV_FIELDS = [
    "scenario", "status", "gt_conflict", "llm_conflict", "binary_correct",
    "ground_truth_file", "prediction_files", "error",
]


def parse_conflict(value):
    """Do not coerce arbitrary values with bool(): bool('no') is True."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"yes", "no"}:
        return value.strip().lower() == "yes"
    raise ValueError("is_conflict must be a JSON boolean or the string yes/no")


def _reject_nonfinite(value):
    raise ValueError(f"Non-standard JSON number is not allowed: {value}")


def _load_json(text):
    return json.loads(text, parse_constant=_reject_nonfinite)


def parse_prediction(path):
    """Return a binary label; reject explanations or ambiguous multiple answers."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8-sig").strip()
    if path.suffix.lower() == ".json":
        payload = _load_json(raw)
        if not isinstance(payload, dict) or "is_conflict" not in payload:
            raise ValueError("JSON must be an object containing is_conflict")
        return parse_conflict(payload["is_conflict"])
    if path.suffix.lower() != ".txt":
        raise ValueError("Prediction extension must be .txt or .json")
    fenced = re.fullmatch(r"\x60{3}(?:text)?\s*\n(.*?)\n\x60{3}", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    if raw.lower() not in {"yes", "no"}:
        raise ValueError("Text prediction must contain only yes or no")
    return raw.lower() == "yes"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _divide(numerator, denominator):
    return round(numerator / denominator, 6) if denominator else None


def _file_record(path):
    return {"path": path.as_posix(), "sha256": _sha256(path)}


def _classification_metrics(labels):
    tp = sum(t and p for t, p in labels)
    tn = sum(not t and not p for t, p in labels)
    fp = sum(not t and p for t, p in labels)
    fn = sum(t and not p for t, p in labels)
    return {
        "TP": tp, "TN": tn, "FP": fp, "FN": fn,
        "accuracy": _divide(tp + tn, len(labels)),
        "precision": _divide(tp, tp + fp),
        "recall": _divide(tp, tp + fn),
        "f1": _divide(2 * tp, 2 * tp + fp + fn),
    }


def _read_scenario_groups(path):
    manifest = _load_json(path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("scenarios"), list):
        raise ValueError("Scenario manifest must be an object with a scenarios list")
    groups = {}
    for entry in manifest["scenarios"]:
        if not isinstance(entry, dict):
            raise ValueError("Each scenario manifest entry must be an object")
        scenario_id = entry.get("scenario_id")
        source_group = entry.get("source_group")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ValueError("Each scenario manifest entry must have a nonempty scenario_id")
        if not isinstance(source_group, str) or not source_group.strip():
            raise ValueError(f"Scenario {scenario_id} must have a nonempty source_group")
        if scenario_id in groups:
            raise ValueError(f"Duplicate scenario_id in scenario manifest: {scenario_id}")
        groups[scenario_id] = source_group
    return groups


def evaluate(gt_dir, pred_dir, run_metadata_path=None, scenario_manifest_path=None):
    """Build rows and summary in memory. This function does not write files."""
    gt_dir, pred_dir = Path(gt_dir), Path(pred_dir)
    gt_paths = sorted(gt_dir.glob("*_gt.json"))
    metadata_path = Path(run_metadata_path) if run_metadata_path else None
    manifest_path = Path(scenario_manifest_path) if scenario_manifest_path else None
    scenario_groups = _read_scenario_groups(manifest_path) if manifest_path else {}
    run_metadata = None
    if metadata_path:
        run_metadata = _load_json(metadata_path.read_text(encoding="utf-8-sig"))
        if not isinstance(run_metadata, dict):
            raise ValueError("Run metadata must be a JSON object")

    pred_paths = sorted(
        p for p in pred_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".json", ".txt"}
        and (metadata_path is None or p.resolve() != metadata_path.resolve())
    ) if pred_dir.exists() else []
    by_scenario = {}
    for path in pred_paths:
        by_scenario.setdefault(path.stem, []).append(path)

    rows, matches, invalid, ambiguous = [], [], [], []
    missing, invalid_gt, gt_records, pred_records = [], [], [], []
    labels = []
    valid_gt_count = 0
    backends, methods = Counter(), Counter()
    expected_stems = {p.stem[:-3] for p in gt_paths}
    extra_paths = [p for p in pred_paths if p.stem not in expected_stems]

    # Fingerprint all candidate answers, including invalid/extra files.
    for path in pred_paths:
        try:
            pred_records.append(_file_record(path))
        except OSError as exc:
            pred_records.append({"path": path.as_posix(), "sha256": None, "error": str(exc)})

    for gt_path in gt_paths:
        scenario = gt_path.stem[:-3]
        candidates = by_scenario.get(scenario, [])
        row = {
            "scenario": scenario, "status": "", "gt_conflict": "",
            "llm_conflict": "", "binary_correct": "",
            "ground_truth_file": gt_path.as_posix(),
            "prediction_files": " | ".join(p.as_posix() for p in candidates), "error": "",
        }
        try:
            record = _file_record(gt_path)
            gt_records.append(record)
            gt = _load_json(gt_path.read_text(encoding="utf-8-sig"))
            if not isinstance(gt, dict) or "is_conflict" not in gt:
                raise ValueError("Ground truth must be an object containing is_conflict")
            truth = parse_conflict(gt["is_conflict"])
            row["gt_conflict"] = truth
            valid_gt_count += 1
            backend = gt.get("ground_truth_backend", "unspecified")
            method = gt.get("ground_truth_method", "unspecified")
            record["ground_truth_backend"] = backend
            record["ground_truth_method"] = method
            for key in ("official_source", "official_provenance", "ground_truth_provenance"):
                if key in gt:
                    record[key] = gt[key]
            backends[str(backend)] += 1
            methods[str(method)] += 1
        except (OSError, UnicodeError, ValueError) as exc:
            row.update(status="invalid_ground_truth", error=str(exc))
            invalid_gt.append({"scenario": scenario, "file": gt_path.as_posix(), "error": str(exc)})
            rows.append(row)
            continue

        if not candidates:
            row["status"] = "missing_prediction"
            missing.append(scenario)
        elif len(candidates) != 1:
            row.update(status="ambiguous_prediction", error="Multiple prediction files; keep exactly one .txt or .json answer per scenario")
            ambiguous.append({"scenario": scenario, "files": [p.as_posix() for p in candidates]})
        else:
            pred_path = candidates[0]
            try:
                prediction = parse_prediction(pred_path)
                labels.append((truth, prediction))
                matches.append(scenario)
                row.update(status="evaluated", llm_conflict=prediction, binary_correct=truth == prediction)
            except (OSError, UnicodeError, ValueError) as exc:
                row.update(status="invalid_prediction", error=str(exc))
                invalid.append({"scenario": scenario, "file": pred_path.as_posix(), "error": str(exc)})
        rows.append(row)

    n = len(labels)
    metrics = _classification_metrics(labels)
    counts = Counter(row["status"] for row in rows)
    status = "pending" if not n else ("complete" if n == len(gt_paths) else "partial")
    grouped_rows = {}
    for row in rows:
        group = scenario_groups.get(row["scenario"], "original_or_unassigned")
        grouped_rows.setdefault(group, []).append(row)
    by_group = {}
    for group, group_rows in sorted(grouped_rows.items()):
        group_labels = [
            (row["gt_conflict"], row["llm_conflict"])
            for row in group_rows if row["status"] == "evaluated"
        ]
        by_group[group] = {
            "expected": len(group_rows), "evaluated": len(group_labels),
            "coverage": _divide(len(group_labels), len(group_rows)),
            **_classification_metrics(group_labels),
        }
    summary = {
        "task": "scenario_conflict_binary_classification",
        "status": status,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "gt_dir": gt_dir.as_posix(), "pred_dir": pred_dir.as_posix(),
        "n_ground_truth_files": len(gt_paths), "n_valid_ground_truth": valid_gt_count,
        "n_evaluated": n, "n_scenarios": n,
        "coverage": _divide(n, len(gt_paths)),
        "n_missing_predictions": len(missing), "n_invalid_predictions": len(invalid),
        "n_ambiguous_predictions": len(ambiguous), "n_invalid_ground_truth": len(invalid_gt),
        "n_extra_prediction_files": len(extra_paths),
        "row_status_counts": dict(counts),
        **metrics,
        "by_group": by_group,
        "grouping_policy": "Groups come only from scenario_id/source_group in the supplied scenario manifest. Unmatched ground-truth scenarios are original_or_unassigned. Expected counts include only files in gt_dir; groups are not paper training/validation/test splits.",
        "metric_policy": {
            "positive_class": "conflict / yes / true",
            "population": "Only valid, unambiguous predictions with valid ground truth are scored; coverage uses all ground-truth files.",
            "undefined": "A metric with a zero denominator is null. With no evaluated predictions, all four metrics are null.",
            "f1_formula": "2*TP / (2*TP + FP + FN), evaluated independently of precision and recall.",
            "secondary_fields": "Legacy structured JSON is accepted for is_conflict only. Pairs, actions, priority, waiting times and explanations are not scored in this binary experiment.",
        },
        "evaluated_scenarios": matches, "missing_predictions": missing,
        "invalid_predictions": invalid, "ambiguous_predictions": ambiguous,
        "invalid_ground_truth": invalid_gt,
        "extra_prediction_files": [p.as_posix() for p in extra_paths],
        "ground_truth_provenance": {"backend_counts": dict(backends), "method_counts": dict(methods)},
        "ground_truth_files": gt_records, "prediction_files": pred_records,
        "run_metadata": run_metadata,
        "run_metadata_policy": "User-supplied metadata is recorded, not independently verified.",
    }
    if metadata_path:
        summary["run_metadata_file"] = _file_record(metadata_path)
    if manifest_path:
        summary["scenario_manifest_file"] = _file_record(manifest_path)
    return rows, summary


def write_results(rows, summary, output_dir, csv_path=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = Path(csv_path) if csv_path else output_dir / "evaluation.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    summary_path = output_dir / "evaluation_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return csv_path, summary_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gt-dir", default="data/ground_truth_official")
    ap.add_argument("--pred-dir", default="outputs/manual_llm")
    ap.add_argument("--output-dir", default="outputs/evaluation_official", help="Directory for CSV and summary; use a distinct directory for each experimental run")
    ap.add_argument("--output", help="Optional legacy CSV path override; summary remains under --output-dir")
    ap.add_argument("--run-metadata", help="Optional JSON object with manually recorded model/date/prompt version")
    default_manifest = Path("data/scenario_generation_manifest.json")
    ap.add_argument("--scenario-manifest", default=str(default_manifest) if default_manifest.is_file() else None, help="Scenario generation manifest for source-group metrics; defaults to data/scenario_generation_manifest.json when present")
    args = ap.parse_args()
    if not Path(args.gt_dir).is_dir():
        ap.error(f"Ground truth directory does not exist: {args.gt_dir}")
    try:
        rows, summary = evaluate(args.gt_dir, args.pred_dir, args.run_metadata, scenario_manifest_path=args.scenario_manifest)
    except (OSError, UnicodeError, ValueError) as exc:
        ap.error(str(exc))
    csv_path, summary_path = write_results(rows, summary, args.output_dir, args.output)
    print(f"Status: {summary['status']}; evaluated {summary['n_evaluated']}/{summary['n_ground_truth_files']}")
    print(f"TP={summary['TP']} TN={summary['TN']} FP={summary['FP']} FN={summary['FN']}")
    for metric in ("accuracy", "precision", "recall", "f1"):
        print(f"{metric}: {summary[metric]}")
    print(f"Missing: {summary['n_missing_predictions']}; invalid: {summary['n_invalid_predictions']}; ambiguous: {summary['n_ambiguous_predictions']}; extra files: {summary['n_extra_prediction_files']}")
    print(f"Per-scenario CSV: {csv_path}\nSummary: {summary_path}")


if __name__ == "__main__":
    main()
