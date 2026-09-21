import argparse
import csv
import json
import math
from pathlib import Path


def canon_pair(a, b): return tuple(sorted((a, b)))


def safe_div(a, b): return a / b if b else 0.0


def main():
    ap = argparse.ArgumentParser(description="Compare manually saved LLM JSON with ground truth.")
    ap.add_argument("--gt-dir", default="data/ground_truth_official")
    ap.add_argument("--pred-dir", default="outputs/manual_llm")
    ap.add_argument("--output", default="outputs/evaluation.csv")
    args = ap.parse_args()

    rows = []
    y_true, y_pred = [], []
    pair_tp = pair_fp = pair_fn = 0
    wait_errors = []
    action_correct = action_total = 0
    priority_correct = priority_total = 0

    for gt_path in sorted(Path(args.gt_dir).glob("*_gt.json")):
        stem = gt_path.stem[:-3] if gt_path.stem.endswith("_gt") else gt_path.stem
        pred_path = Path(args.pred_dir) / f"{stem}.json"
        if not pred_path.exists():
            continue
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        pr = json.loads(pred_path.read_text(encoding="utf-8"))
        yt, yp = bool(gt["is_conflict"]), bool(pr["is_conflict"])
        y_true.append(yt); y_pred.append(yp)

        gt_pairs = {canon_pair(x["vehicle1_id"], x["vehicle2_id"]) for x in gt.get("conflict_vehicles", [])}
        pr_pairs = {canon_pair(x["vehicle1_id"], x["vehicle2_id"]) for x in pr.get("conflict_vehicles", [])}
        pair_tp += len(gt_pairs & pr_pairs); pair_fp += len(pr_pairs - gt_pairs); pair_fn += len(gt_pairs - pr_pairs)

        # Pairwise priority-order agreement (Kendall-like concordance on shared vehicle IDs).
        gt_order = gt.get("priority_order", [])
        pr_order = pr.get("priority_order", [])
        common = [x for x in gt_order if x in pr_order]
        gpos = {x:i for i,x in enumerate(gt_order)}; ppos = {x:i for i,x in enumerate(pr_order)}
        for i in range(len(common)):
            for j in range(i+1, len(common)):
                a,b = common[i], common[j]
                priority_total += 1
                priority_correct += int((gpos[a] < gpos[b]) == (ppos[a] < ppos[b]))

        gt_actions = {x["vehicle_id"]: x["action"] for x in gt.get("decisions", [])}
        pr_actions = {x["vehicle_id"]: x["action"] for x in pr.get("decisions", [])}
        for vid, act in gt_actions.items():
            if vid in pr_actions:
                action_total += 1
                action_correct += int(pr_actions[vid] == act)

        for vid, sec in gt.get("waiting_times", {}).items():
            if vid in pr.get("waiting_times", {}):
                wait_errors.append(float(pr["waiting_times"][vid]) - float(sec))

        rows.append({
            "scenario": stem,
            "gt_conflict": yt,
            "llm_conflict": yp,
            "binary_correct": yt == yp,
            "gt_pairs": len(gt_pairs),
            "pred_pairs": len(pr_pairs),
            "pair_exact_match": gt_pairs == pr_pairs,
        })

    if not rows:
        raise SystemExit("No matching prediction JSON files found. Save them as outputs/manual_llm/<scenario>.json")

    tp = sum(t and p for t, p in zip(y_true, y_pred)); tn = sum((not t) and (not p) for t,p in zip(y_true,y_pred))
    fp = sum((not t) and p for t,p in zip(y_true,y_pred)); fn = sum(t and (not p) for t,p in zip(y_true,y_pred))
    accuracy = safe_div(tp + tn, len(y_true)); precision = safe_div(tp, tp + fp); recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    pp = safe_div(pair_tp, pair_tp + pair_fp); prc = safe_div(pair_tp, pair_tp + pair_fn); pf1 = safe_div(2*pp*prc, pp+prc)
    mae = sum(abs(e) for e in wait_errors)/len(wait_errors) if wait_errors else math.nan
    rmse = math.sqrt(sum(e*e for e in wait_errors)/len(wait_errors)) if wait_errors else math.nan

    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

    summary = {
        "n_scenarios": len(rows), "TP": tp, "TN": tn, "FP": fp, "FN": fn,
        "accuracy": round(accuracy,4), "precision": round(precision,4), "recall": round(recall,4), "f1": round(f1,4),
        "pair_precision": round(pp,4), "pair_recall": round(prc,4), "pair_f1": round(pf1,4),
        "action_accuracy": round(safe_div(action_correct, action_total),4),
        "priority_pairwise_agreement": round(safe_div(priority_correct, priority_total),4),
        "waiting_time_mae_s": None if math.isnan(mae) else round(mae,4),
        "waiting_time_rmse_s": None if math.isnan(rmse) else round(rmse,4),
    }
    Path("outputs/evaluation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Per-scenario CSV: {out}")

if __name__ == "__main__": main()
