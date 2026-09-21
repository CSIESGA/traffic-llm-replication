# Traffic LLM Paper Replication — Zenodo-ready Experimental Version

This project expands the structured-state experiment from **Masri, Ashqar & Elhenawy, Vehicles (2025)**.

Pipeline:

`scenario JSON -> validation -> ground-truth backend -> fixed manual prompt -> LLM JSON -> quantitative evaluation`

## Ground-truth provenance — important correction

The published paper **does identify an official code/data record**: **Zenodo record 14171745**, DOI **10.5281/zenodo.14171745**. Therefore the preferred replication backend is now `official`.

The previous geometric simulator has been renamed to `ground_truth_reconstruction.py`. It is **not author code** and remains only as a fallback / sensitivity-analysis baseline.

Because this build environment could verify the Zenodo record from the paper but could not retrieve its file bytes through the sandbox, the official archive itself is not falsely bundled here. Instead this project includes a reproducible installer and a strict adapter layer. See `ZENODO_GROUND_TRUTH.md`.

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 1. Install the authors' Zenodo record

```powershell
python install_zenodo_ground_truth.py
python inspect_zenodo_ground_truth.py
```

Then map the **actual** author module/function in `official_adapter_config.json`. The project deliberately refuses to invent a function name.

If Zenodo API access is blocked, manually download DOI `10.5281/zenodo.14171745` and use:

```powershell
python install_zenodo_ground_truth.py --archive C:\path\to\downloaded_file.zip --force
```

### 2. Generate official ground truth

```powershell
python generate_ground_truth.py --backend official --input-dir data/scenarios --output-dir data/ground_truth_official
```

One-scenario inspection:

```powershell
python main.py --scenario data/scenarios/scenario_003.json --ground-truth --gt-backend official --dry-run
```

### 3. Export copy/paste prompts

```powershell
python export_manual_prompts.py --input-dir data/scenarios
```

Open `prompts/scenario_XXX.txt`, start a fresh chat, paste it, and save the first model JSON reply as:

`outputs/manual_llm/scenario_XXX.json`

### 4. Evaluate against official labels

```powershell
python evaluate_manual.py --gt-dir data/ground_truth_official
```

Results are written to `outputs/evaluation.csv` and `outputs/evaluation_summary.json`.

### 5. Optional reconstruction baseline

```powershell
python generate_ground_truth.py --backend reconstruction --input-dir data/scenarios --output-dir data/ground_truth_reconstruction
```

Do **not** describe this output as the paper's official ground truth.

### 6. Generate a larger reproducible scenario bank

```powershell
python generate_scenarios.py --count 100 --balanced --seed 20260915 --gt-backend reconstruction
```

If/when the official adapter is configured, you can balance with the official backend instead:

```powershell
python generate_scenarios.py --count 100 --balanced --seed 20260915 --gt-backend official
```

## Project files

- `intersection.py` — paper Figure-4 lane/destination map and movement inference used by this demo's structured state.
- `vehicle.py` — vehicle validation, speed conversion, time-to-intersection, structured state.
- `parser.py` — JSON scenario loader and duplicate-ID checks.
- `ground_truth.py` — explicit backend router.
- `official_ground_truth_adapter.py` — adapter/normalizer for the authors' Zenodo implementation; never silently falls back.
- `install_zenodo_ground_truth.py` — downloads Zenodo record 14171745, verifies checksums, safely extracts files, and never executes them.
- `inspect_zenodo_ground_truth.py` — statically lists functions/classes/keyword hits without importing author code.
- `official_adapter_config.json` — exact mapping to the author code after inspection.
- `ground_truth_reconstruction.py` — previous geometric reconstruction, retained only as a non-author baseline.
- `generate_ground_truth.py` — labels one scenario or a directory using an explicit backend.
- `generate_scenarios.py` — seeded 2–8 vehicle scenario generator; optional balancing.
- `prompt_builder.py` — fixed LLM prompt.
- `export_manual_prompts.py` — creates copy/paste prompt files.
- `evaluate_manual.py` — computes classification/pair/action/priority/waiting-time metrics.
- `ZENODO_GROUND_TRUTH.md` — official-code installation/integration notes.
- `EXPERIMENT_PROTOCOL.md` — controls for manual LLM experiments.

## What remains intentionally unguessed

A Zenodo DOI proves where the authors deposited code/data, but it does not tell us the internal Python module/function API. Until the actual files are fetched and inspected, this project will **not** claim that some guessed function is the author's simulator. That distinction is essential for a defensible replication.
