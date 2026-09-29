"""Export natural-language prompts and hashes; never include Ground Truth."""

import argparse
import hashlib
import json
from pathlib import Path

from parser import load_scenario
from prompt_builder import (
    AUTHOR_TAG,
    EXPECTED_OUTPUT,
    PROMPT_SOURCES,
    PROTOCOL_NAME,
    build_manual_prompt,
    build_detailed_prompt,
    DETAILED_PROTOCOL_NAME,
    DETAILED_EXPECTED_OUTPUT,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def export_prompts(input_dir: Path, output_dir: Path, *, overwrite: bool = False, protocol: str = "binary") -> dict:
    """Validate every Scenario before writing, and guard existing experiments."""
    if protocol not in ("binary", "detailed"):
        raise ValueError("Unknown prompt protocol")
    builder = build_detailed_prompt if protocol == "detailed" else build_manual_prompt
    source_paths = sorted(input_dir.glob("*.json"))
    if not source_paths:
        raise ValueError(f"No scenario JSON files found in {input_dir}")

    prepared = []
    records = []
    for source in source_paths:
        prompt_bytes = builder(load_scenario(str(source))).encode("utf-8")
        target = output_dir / f"{source.stem}.txt"
        prepared.append((target, prompt_bytes))
        records.append({
            "scenario_id": source.stem,
            "scenario_file": source.as_posix(),
            "scenario_sha256": sha256_bytes(source.read_bytes()),
            "prompt_file": target.as_posix(),
            "prompt_sha256": sha256_bytes(prompt_bytes),
        })

    manifest = {
        "schema_version": 1,
        "protocol": DETAILED_PROTOCOL_NAME if protocol == "detailed" else PROTOCOL_NAME,
        "author_tag": AUTHOR_TAG,
        "expected_output": DETAILED_EXPECTED_OUTPUT if protocol == "detailed" else EXPECTED_OUTPUT,
        "prompt_sources": PROMPT_SOURCES,
        "manual_role_note": (
            "System and user text are combined in one user message for manual chat; "
            "this does not reproduce API system-role separation."
        ),
        "numeric_format": ("full Python float representation; no two-decimal rounding" if protocol == "detailed"
                           else "speed and distance formatted to two decimal places, as in author v1.0.0"),
        "scope": ("Project detailed-output extension using archived eight-field schema; not an original author prompt. No GT, movement hints, TTI or simulator decision rules included."
                  if protocol == "detailed" else "Author v1.0.0 classification wording"),
        "n_scenarios": len(records),
        "prompts": records,
    }
    if protocol == "binary":
        # Preserve existing binary manifests byte-for-byte on re-export.
        manifest.pop("scope")
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    prepared.append((output_dir / "prompt_manifest.json", manifest_bytes))

    # Check all destinations first, so refusal does not create a partial export.
    if not overwrite:
        for target, content in prepared:
            if target.exists() and target.read_bytes() != content:
                raise FileExistsError(
                    f"Refusing to replace existing experiment file: {target}. "
                    "Choose a fresh --output-dir, or archive it before using --overwrite."
                )

    output_dir.mkdir(parents=True, exist_ok=True)
    for target, content in prepared:
        target.write_bytes(content)
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-dir", default="data/scenarios")
    ap.add_argument("--protocol", choices=["binary", "detailed"], default="detailed")
    ap.add_argument("--output-dir", help="Default: prompts/detailed for detailed, prompts for binary")
    ap.add_argument("--overwrite", action="store_true", help="Replace differing existing exports.")
    args = ap.parse_args()
    args.output_dir = args.output_dir or ("prompts/detailed" if args.protocol == "detailed" else "prompts")
    manifest = export_prompts(Path(args.input_dir), Path(args.output_dir), overwrite=args.overwrite, protocol=args.protocol)
    print(f"Exported {manifest['n_scenarios']} prompts to {args.output_dir}")
    print(f"Manifest: {Path(args.output_dir) / 'prompt_manifest.json'}")


if __name__ == "__main__":
    main()
