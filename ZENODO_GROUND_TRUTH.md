# Official Zenodo ground-truth integration

## Provenance

The published *Vehicles* paper states in its **Data Availability Statement** that its supporting data and code are openly available as **Zenodo record 14171745**, DOI **10.5281/zenodo.14171745**.

For replication, treat that record as the primary source. The older `ground_truth_reconstruction.py` in this project is **not** author code and is retained only as a comparison/sensitivity baseline.

## Why the author files are not bundled in this ZIP

This build environment could verify the publication's Zenodo DOI but could not retrieve the record's file bytes through its web sandbox. To avoid fabricating or mislabeling code, the project now includes a local installer that fetches the official record directly from Zenodo on your machine.

## Step 1 — install the Zenodo files

```powershell
pip install -r requirements.txt
python install_zenodo_ground_truth.py
```

The installer calls Zenodo's public Records API:

`GET https://zenodo.org/api/records/14171745`

It verifies the DOI when exposed by the record metadata, downloads each file, verifies Zenodo MD5 checksums when present, computes SHA-256 checksums, and safely extracts ZIP/TAR archives under:

```text
vendor/zenodo_14171745/
├── raw/
├── extracted/
├── record_metadata.json
└── manifest.json
```

It **does not execute downloaded code**.

If API access is blocked, manually open the DOI, download the record, then run:

```powershell
python install_zenodo_ground_truth.py --archive C:\path\to\downloaded_file.zip --force
```

If Zenodo provides multiple separate files, place/download each one and run the installer for the relevant code archive; do not assume that an unrelated file is the simulator.

## Step 2 — inspect, without executing

```powershell
python inspect_zenodo_ground_truth.py
```

This writes `vendor/zenodo_14171745/inspection.json` and lists candidate Python functions/classes. This is necessary because a Zenodo record does not guarantee a stable package API.

## Step 3 — map the real author entry point

Edit `official_adapter_config.json` only after inspecting the actual files. Example *shape* (not a claim about the author's function name):

```json
{
  "configured": true,
  "mode": "python_function",
  "module_path": "some_archive/simulator.py",
  "function": "actual_function_name",
  "input_kind": "scenario_dict",
  "kwargs": {}
}
```

`module_path` is relative to `vendor/zenodo_14171745/extracted/`.

Supported `input_kind` values:

- `scenario_dict` — calls `fn({"vehicles_scenario": [...]})`
- `vehicles_list` — calls `fn([...])`
- `scenario_path` — writes a temporary JSON and calls `fn(path)`

If the official code is command-line driven rather than a function, use `mode: "command"` and a command array with placeholders `{input_json}`, `{output_json}`, and `{vendor_root}`.

## Step 4 — generate official ground truth

After the adapter is mapped:

```powershell
python generate_ground_truth.py --backend official --input-dir data/scenarios --output-dir data/ground_truth_official
```

For one scenario:

```powershell
python main.py --scenario data/scenarios/scenario_003.json --ground-truth --gt-backend official --dry-run
```

The adapter normalizes the paper-style output (including `"is_conflict": "yes"` and dictionary priority ranks) into this project's evaluation schema while preserving the exact raw author output under `official_raw_output`.

## Reconstruction baseline

The old simulator remains available explicitly:

```powershell
python generate_ground_truth.py --backend reconstruction --input-dir data/scenarios --output-dir data/ground_truth_reconstruction
```

Do not report reconstruction results as the paper's ground truth.
