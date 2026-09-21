import argparse
from pathlib import Path
from parser import load_scenario
from prompt_builder import SYSTEM_PROMPT, build_user_prompt

MANUAL_INSTRUCTION = """
Return ONLY valid JSON with these keys:
is_conflict, number_of_conflicts, places_of_conflicts, conflict_vehicles,
decisions, priority_order, waiting_times, explanation.
Do not use markdown fences.
""".strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", default="data/scenarios")
    ap.add_argument("--output-dir", default="prompts")
    args = ap.parse_args()
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    for p in sorted(Path(args.input_dir).glob("*.json")):
        vehicles = load_scenario(str(p))
        text = SYSTEM_PROMPT + "\n\n" + MANUAL_INSTRUCTION + "\n\n" + build_user_prompt(vehicles)
        (out / f"{p.stem}.txt").write_text(text, encoding="utf-8")
        print(out / f"{p.stem}.txt")

if __name__ == "__main__": main()
