import argparse
import json
import random
from pathlib import Path
from intersection import INTERSECTION_LAYOUT
from parser import load_scenario
from ground_truth import analyze_ground_truth


def random_vehicle(i, rng):
    direction = rng.choice(list(INTERSECTION_LAYOUT))
    lane = rng.choice(list(INTERSECTION_LAYOUT[direction]))
    destination = rng.choice(INTERSECTION_LAYOUT[direction][lane])
    speed = round(rng.uniform(25, 75), 2)
    # Generate around a target arrival time so both positive and negative cases occur.
    target_tti = rng.uniform(3.5, 13.0)
    distance = round((speed / 3.6) * target_tti, 2)
    return {
        "vehicle_id": f"V{i:04d}",
        "lane": lane,
        "speed": speed,
        "distance_to_intersection": distance,
        "direction": direction,
        "destination": destination,
    }


def main():
    ap = argparse.ArgumentParser(description="Generate reproducible 2-8 vehicle scenarios.")
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20260915)
    ap.add_argument("--output-dir", default="data/generated_scenarios")
    ap.add_argument("--balanced", action="store_true", help="Try to balance conflict/non-conflict cases")
    ap.add_argument("--gt-backend", choices=["official", "reconstruction"], default="reconstruction", help="Backend used only to label/filter generated candidates.")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pos = neg = 0
    accepted = 0
    attempts = 0

    while accepted < args.count and attempts < args.count * 200:
        attempts += 1
        n = rng.randint(2, 8)
        payload = {"vehicles_scenario": [random_vehicle(accepted * 10 + j + 1, rng) for j in range(n)]}
        temp = out / "_candidate.json"
        temp.write_text(json.dumps(payload), encoding="utf-8")
        try:
            gt = analyze_ground_truth(load_scenario(str(temp)), backend=args.gt_backend)
        except Exception:
            continue
        label = gt["is_conflict"]
        if args.balanced:
            target_each = args.count // 2
            if label and pos >= target_each + (args.count % 2):
                continue
            if not label and neg >= target_each:
                continue
        accepted += 1
        pos += int(label)
        neg += int(not label)
        path = out / f"generated_{accepted:03d}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp = out / "_candidate.json"
    if temp.exists(): temp.unlink()
    print(f"Generated {accepted} scenarios (conflict={pos}, no_conflict={neg}) seed={args.seed} backend={args.gt_backend}")


if __name__ == "__main__":
    main()
