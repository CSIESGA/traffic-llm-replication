# Traffic LLM Replication: Detailed Output Evaluation

**The primary workflow now uses structured JSON outputs**, following the same eight fields defined in `archive/legacy_reconstruction_20260928/manual_llm/`:

`is_conflict`, `number_of_conflicts`, `places_of_conflicts`, `conflict_vehicles`, `decisions`, `priority_order`, `waiting_times`, and `explanation`.

A total of **324 detailed prompts** have been generated in `prompts/detailed/`.

This is an **extended experiment introduced by this project**, not the original yes/no classification prompt used by the authors.

The model input remains a natural-language description of the six original vehicle attributes, with numerical precision preserved. Neither ground-truth labels (GT) nor movement hints from the previous reconstruction are provided to the model.

## 1. Detailed Experiment: Current Workflow

Use the following procedure to conduct the detailed-output experiment:

1. Follow `data/manual_trial_order_detailed.csv` to open the corresponding `prompts/detailed/scenario_XXX.txt` files.
2. Start a new conversation for each scenario using identical model settings. Submit the complete prompt and preserve the model's first complete response without modification.
3. Save each response to `outputs/detailed_llm/scenario_XXX.txt`. Raw JSON responses may alternatively be saved using the `.json` extension, but both extensions must not exist for the same scenario.
4. Record the model and experimental settings in `outputs/browser_detailed_324/run_metadata.json`. If the exact underlying model version is unknown, leave it as `null` rather than inferring it from the interface label.
5. Run `python evaluate_detailed.py`. Evaluation results will be saved to `outputs/evaluation_detailed/`.

```powershell
$py = 'C:\Users\黃翊峰\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py evaluate_detailed.py
```

The detailed evaluator measures:

- Binary conflict classification
- Conflict-pair identification
- Number of conflicts
- Per-vehicle actions
- Priority ordering among conflicting vehicles
- Waiting times
- Approximate conflict locations

The complete reasoning and `explanation` fields are preserved. However, because no ground-truth explanations are available, **the evaluator does not claim to assess the semantic correctness of model explanations**.

Some cases in the authors' ground truth contain inconsistencies between pairwise and global priority assignments. These cases are explicitly identified in the evaluation report, which also provides separate results for consistent and inconsistent subsets.

**Current experiment status:** Only six genuine responses from the previous binary-classification pilot are available. No responses have been collected for the new detailed-output experiment.

Test fixtures are not treated as LLM-generated responses and are never stored in the official prediction directory.

### Detailed Experiment Files

| File / Directory | Purpose |
|---|---|
| `prompt_builder.py::build_detailed_prompt` | Constructs natural-language inputs and specifies the eight-field JSON output format |
| `export_manual_prompts.py --protocol detailed` | Exports detailed prompts in batches and records their hashes |
| `prepare_detailed_experiment.py` | Prepares 324 scenarios, preserves the original randomized trial order, and initializes experiment records |
| `detailed_output.py` | Validates complete structured outputs and explicitly converts the authors' raw ground truth |
| `evaluate_detailed.py` | Performs field-level comparisons, coverage analysis, subgroup evaluation, and GT inconsistency analysis |
| `browser_output_collector.py` | Provides a local-only interface for collecting unmodified browser responses without an LLM API |
| `outputs/detailed_llm/` | Stores raw model responses from the detailed experiment |
| `outputs/browser_detailed_324/` | Stores model metadata, timestamps, scenario status, and response provenance |
| `outputs/evaluation_detailed/` | Stores CSV reports, complete scenario-level comparisons, parsed results, and aggregate metrics |
| `outputs/manual_llm/` | Preserves six responses from the previous binary pilot; these must not be mixed with detailed-experiment responses |

For complete field specifications, scoring methods, limitations, execution commands, and resumption procedures, see [DETAILED_EXPERIMENT_PROTOCOL.md](DETAILED_EXPERIMENT_PROTOCOL.md).

The original ground-truth files remain unchanged and are stored in `data/ground_truth_official/`.

---

## 2. Original Binary Classification Workflow (Historical Baseline)

The original binary-classification workflow is retained as a historical baseline.

To run this experiment, open `prompts/scenario_XXX.txt`, copy the complete prompt into a new GPT conversation, and save the model's first `yes` or `no` response to `outputs/manual_llm/scenario_XXX.txt`.

Then execute the evaluation script.

**No API key is required.**

This project is based on the *Vehicles* paper by Masri, Ashqar, and Elhenawy.

The original replication task focuses on **binary conflict detection**, determining whether a traffic scenario contains a conflict.

Reference labels are generated using the authors' publicly released `v1.0.0` code, while model inputs follow the natural-language format used in the authors' classification experiments.

The experimental methodology is documented in [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md).

### 2.1 Running the First Experiment

1. Fill in `EXPERIMENT_RUN.json` with the actual GPT model, interface, and experiment date. Leave fields unknown if their exact values cannot be verified.
2. Follow the order specified in `data/manual_trial_order.csv` and open each corresponding `prompts/scenario_XXX.txt`. The trial-order file does not contain GT labels.
3. Start a new conversation for every scenario. Use identical model settings, submit the complete prompt, and do not introduce additional instructions or corrections. Preserve the first response.
4. Save the raw response as `outputs/manual_llm/scenario_XXX.txt`. For example, `scenario_001.txt` must correspond to `scenario_001.json`. Do not save both `.txt` and `.json` responses for the same scenario.
5. Run the evaluator:

```powershell
python evaluate_manual.py --run-metadata EXPERIMENT_RUN.json
```

The evaluation outputs are:

- `outputs/evaluation_official/evaluation.csv`: Scenario-level scores and missing-response statuses.
- `outputs/evaluation_official/evaluation_summary.json`: Accuracy, Precision, Recall, F1, TP/TN/FP/FN, coverage, input-file hashes, and experiment metadata.

If no model responses have been saved, scenarios are marked as `pending`, the number of valid responses is zero, and evaluation metrics are `null`.

This indicates that the experiment has not started; it does **not** represent an accuracy of 0% or 100%.

The experiment may be conducted incrementally. Incomplete runs are explicitly marked as `partial`, and their coverage is reported.

If a model generates additional explanations, preserve the complete original response rather than manually extracting the expected label.

The evaluator marks outputs that are not strictly `yes` or `no` as `invalid_prediction`, allowing output-format failures to be tracked.

Additional response-format requirements are documented in the experimental protocol.

---

## 3. Prepared Dataset

The dataset consists of **324 traffic scenarios**, including 24 original scenarios and 300 newly generated scenarios.

| Dataset Group | Scenario IDs | Count | Source |
|---|---|---:|---|
| Original scenarios | `scenario_001`–`scenario_024` | 24 | Original input files preserved; labels regenerated using the authors' code |
| Four-vehicle scenarios | `scenario_025`–`scenario_124` | 100 | Authors' generator, seed `20260928` |
| Eight-vehicle scenarios | `scenario_125`–`scenario_224` | 100 | Authors' generator, seed `20260929` |
| Mixed-vehicle scenarios | `scenario_225`–`scenario_324` | 100 | Authors' generator, 2–8 vehicles, seed `20260930` |

Each newly generated group contains 50 conflict scenarios and 50 no-conflict scenarios.

This balancing is the result of filtering samples generated by the authors' scenario generator. **It does not reflect real-world traffic conflict prevalence.**

The original 24 scenarios are not assumed to have balanced class labels.

Generation parameters, scenario hashes, vehicle counts, and provenance information are recorded in:

`data/scenario_generation_manifest.json`

This manifest contains ground-truth labels and **must not be provided to the LLM during evaluation**.

### 3.1 Ground-Truth Distribution

The authors' code assigns the following labels:

| Dataset | Conflict | No Conflict | Total |
|---|---:|---:|---:|
| Original scenarios | 21 | 3 | 24 |
| Newly generated scenarios | 150 | 150 | 300 |
| **Total** | **171** | **153** | **324** |

Seven original scenarios were previously classified as no-conflict by the local reconstruction but are classified as conflict by the authors' official implementation:

`005`, `006`, `012`, `014`, `016`, `018`, and `020`.

Scenario-level differences are recorded in:

`data/original_24_ground_truth_comparison.csv`

The complete label summary is available in:

`data/ground_truth_official/ground_truth_summary.csv`

Ground-truth summaries must not be included in prompts or otherwise exposed to the model during the experiment.

### 3.2 Dataset Provenance and Limitations

The 300 additional scenarios are **locally resampled using the authors' published generator**.

They are not recovered samples from the original 10,000-record dataset used in the paper.

This project has not yet reproduced:

- The original train/validation/test splits
- Model fine-tuning
- Multi-model comparisons
- ROUGE-L evaluation

Furthermore, manually interacting with a GPT interface is not equivalent to using the exact API model checkpoint specified in the paper.

These distinctions are essential when interpreting and reporting the replication results.

---

## 4. Experimental Pipeline

The project separates scenario input generation, ground-truth computation, model inference, and evaluation.

```text
Scenario JSON: Six original vehicle attributes
│
├── parser.load_scenario()
│   │   Validate scenario data and legal lane/destination values
│   │
│   └── Official ground-truth adapter
│       │
│       └── Authors' generate_dataset(total_records=1)
│           │
│           └── data/ground_truth_official/*_gt.json
│               Reference labels for evaluation
│
└── scenario_to_text()
    │   Convert scenario data into the authors' natural-language format
    │
    └── build_manual_prompt()
        │   Combine fixed instructions with vehicle descriptions
        │
        └── prompts/*.txt
            │   Manually submit to a new GPT conversation
            │
            └── outputs/manual_llm/*.txt
                │   Preserve the model's first raw response
                │
                └── evaluate_manual.py
                    │   Compare predictions with official ground truth
                    │
                    └── Classification metrics
```

The ground-truth and prompt-generation pipelines are kept separate.

**Ground-truth answers are never embedded in model prompts.**

### 4.1 Model Input Format

Each prompt contains only the six original vehicle attributes:

- `vehicle_id`
- `lane`
- `speed`
- `distance_to_intersection`
- `direction`
- `destination`

For the original binary-classification workflow, speed and distance values follow the authors' formatting and are displayed to two decimal places.

Locally reconstructed attributes such as `movement` and `time_to_intersection` are not injected into the prompt.

The objective is to reproduce the authors' publicly available classification input format without introducing additional geometric definitions that were not supplied to the model in the original setup.

### 4.2 Ground-Truth Compatibility

The authors' lane/destination-to-movement mapping differs from the mapping previously reconstructed in this project based on Figure 4 of the paper.

For the official evaluation, the authors' implementation is treated as the reference behavior.

This discrepancy is documented as a methodological limitation.

See [ZENODO_GROUND_TRUTH.md](ZENODO_GROUND_TRUTH.md) for details.

---

## 5. Project Structure

```text
data/
    scenarios/
        324 original-format scenario inputs

    ground_truth_official/
        324 reference labels generated using the authors' code
        Includes raw outputs and provenance

    ground_truth_reconstruction/
        24 historical labels from the local reconstruction
        Used only for historical and sensitivity comparisons

    scenario_generation_manifest.json
        Generation parameters, seeds, and hashes
        for the 300 newly generated scenarios

    manual_trial_order.csv
        Randomized trial order with a fixed seed
        Does not contain ground-truth labels

prompts/
    scenario_XXX.txt
        Complete natural-language prompts

    prompt_manifest.json
        Prompt/scenario SHA256 hashes and protocol metadata

outputs/
    manual_llm/
        Raw model responses

    evaluation_official/
        Binary-classification evaluation results

archive/
    legacy_reconstruction_20260928/
        Historical prompts, five old responses, and old metrics

vendor/
    zenodo_14171745/
        raw/
            Original ZIP archive from the authors

        extracted/
            Unmodified authors' code and sample data

        manifest.json
            DOI, ZIP checksum, and SHA256 hashes

        record_metadata.json
            Original Zenodo metadata

EXPERIMENT_RUN.json
    Manually recorded experimental settings

tests/
    Tests for author-output consistency,
    prompt generation, and evaluation
```

The detailed-output experiment additionally uses:

```text
prompts/
    detailed/
        324 structured-output prompts

data/
    manual_trial_order_detailed.csv
        Trial order for detailed experiments

outputs/
    detailed_llm/
        Raw detailed JSON responses

    browser_detailed_324/
        Model settings, timestamps,
        response status, and provenance

    evaluation_detailed/
        Field-level comparisons,
        parsed results, and aggregate metrics
```

---

## 6. Main Scripts and Modules

| Script / Module | Description |
|---|---|
| `main.py` | Previews or saves a single prompt; optionally displays GT without making API calls |
| `parser.py`, `vehicle.py`, `intersection.py` | Load and validate six-field scenario data; local movement helpers are not used for official conflict decisions |
| `prompt_builder.py` | Defines the authors' system instructions, converts scenarios into natural-language descriptions, and builds manual prompts |
| `export_manual_prompts.py` | Exports prompts in batches and generates a hash manifest |
| `ground_truth.py` | Selects either the official or reconstructed ground-truth backend |
| `official_ground_truth_adapter.py` | Executes the authors' decision logic and dataset-level aggregation while preserving raw results |
| `official_adapter_config.json` | Stores the finalized configuration for the pinned authors' implementation |
| `generate_ground_truth.py` | Generates official reference labels for existing scenarios |
| `generate_scenarios.py` | Uses the authors' generator to create four-vehicle, eight-vehicle, and mixed-vehicle scenarios |
| `evaluate_manual.py` | Strictly parses yes/no responses, evaluates predictions, and records missing, duplicate, and invalid outputs |
| `prepare_manual_run.py` | Validates prompt hashes, prepares a label-free randomized trial order, and initializes empty experiment metadata |
| `install_zenodo_ground_truth.py` | Downloads, verifies, and extracts the pinned authors' version; refuses to overwrite an existing installation |
| `inspect_zenodo_ground_truth.py` | Statically inspects functions and classes in the authors' files |
| `ground_truth_reconstruction.py` | Preserves the historical geometric baseline separately from the official implementation |

The authors' archived files, including `gpt_finetuning/`, remain unchanged for provenance verification.

The manual replication workflow does not execute these archived fine-tuning components.

The following project-level files have been removed:

`llm_client.py`, `batch_run.py`, `config.py`, `schemas.py`, and `.env.example`.

---

## 7. Local Setup and Execution

The authors' implementation has already been downloaded and integrated. Reinstallation is not necessary for the current project environment.

For a fresh environment, use **Python 3.10 or later**.

The only additional Python package required by the current execution workflow is `pandas`.

### 7.1 Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

If `python` is unavailable on the current Windows system, the following interpreter has been verified:

```powershell
$py = 'C:\Users\黃翊峰\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

& $py evaluate_manual.py --run-metadata EXPERIMENT_RUN.json
```

### 7.2 Preview a Scenario Prompt

To preview a prompt without sending any data to GPT:

```powershell
python main.py --protocol binary --scenario data/scenarios/scenario_001.json
```

### 7.3 Regenerate Official Ground Truth

```powershell
python generate_ground_truth.py --backend official --input-dir data/scenarios --output-dir data/ground_truth_official
```

### 7.4 Re-export Binary Prompts

```powershell
python export_manual_prompts.py --protocol binary --input-dir data/scenarios --output-dir prompts
```

The exporter refuses to overwrite existing files if their contents differ.

**Once response collection begins, the dataset and prompts should be frozen.**

Any modifications to experimental inputs should be introduced as a separate experiment version rather than overwriting the original inputs during evaluation.

---

## 8. Generating Additional Scenarios

To generate additional scenarios, use a separate directory to avoid mixing datasets from different experimental runs.

```powershell
python generate_scenarios.py --per-group 100 --seed 20261001 --output-dir data/next_batch/scenarios --manifest data/next_batch/generation_manifest.json

python generate_ground_truth.py --backend official --input-dir data/next_batch/scenarios --output-dir data/next_batch/ground_truth

python export_manual_prompts.py --protocol binary --input-dir data/next_batch/scenarios --output-dir data/next_batch/prompts
```

The `--per-group` argument must be a positive even integer.

Setting `--per-group 100` generates 100 scenarios for each of the three groups, producing 300 additional scenarios in total.

Scenario filenames in the new directory begin again at `scenario_001`.

Responses from these scenarios must be stored separately from the existing 324-scenario experiment.

When evaluating the new dataset, explicitly specify the corresponding `--gt-dir`, `--pred-dir`, and `--output-dir` arguments.

**Do not mix predictions, reference labels, or evaluation results across experimental batches.**

---

## 9. Validation and Reproducibility

The following validation procedures have been completed:

- **22 unit tests passed** using:

```powershell
python -B -m unittest discover -s tests -v
```

- The adapter's complete output fields match the results of 100 records from the authors' publicly released CSV.
- All 300 newly generated scenarios were reproduced in memory using the same random seeds. Both scenario inputs and the authors' raw outputs matched exactly.
- The original 24 scenario inputs remain unchanged.
- SHA256 hashes were verified for all 324 prompts and ground-truth files.
- The new binary evaluation report is currently marked as `pending`, with 0 out of 324 responses collected. No new LLM performance results are available.
- The evaluation summary includes a `by_group` breakdown for `four`, `eight`, `mixed`, and `original_or_unassigned` scenarios.
- The evaluation CLI reads the existing generation manifest by default. An alternative manifest can be supplied through `--scenario-manifest`.

The validation results are saved in:

`outputs/setup_validation.json`

---

## 10. Experimental Scope and Limitations

This project distinguishes between reproducing the authors' published scenario-generation and labeling behavior and reproducing the full model-training and evaluation procedures described in the paper.

The current implementation provides:

- Reproducible scenario generation using the authors' publicly released code
- Official ground-truth generation with preserved provenance
- Controlled natural-language prompt generation
- Manual LLM inference without API credentials
- Strict response collection and validation
- Binary-classification evaluation
- Extended field-level evaluation of structured JSON responses
- Scenario-level traceability through hashes and experiment metadata
- Explicit documentation of ground-truth inconsistencies and methodological limitations

However, the project does not yet reproduce the original paper's complete training pipeline, data splits, fine-tuning experiments, multi-model comparisons, or ROUGE-L evaluation.

The extended structured-output experiment is a project-specific addition and should not be presented as a direct reproduction of the authors' original binary-classification experiment.

In addition, model responses collected through a browser interface cannot automatically be assumed equivalent to responses from a specific API checkpoint.

All reported results should therefore identify the model interface, available model metadata, experimental protocol, number of evaluated scenarios, and response coverage.

---

## 11. Documentation and References

For further implementation and methodology details, see:

| Document | Description |
|---|---|
| [DETAILED_EXPERIMENT_PROTOCOL.md](DETAILED_EXPERIMENT_PROTOCOL.md) | Structured-output schema, detailed scoring rules, limitations, execution commands, and experiment resumption |
| [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md) | Original binary-classification experimental protocol |
| [ZENODO_GROUND_TRUTH.md](ZENODO_GROUND_TRUTH.md) | Authors' source code, official ground-truth integration, mapping differences, and limitations |
| [CHANGES_ZENODO.md](CHANGES_ZENODO.md) | Changes introduced during the Zenodo integration |

The authors' original code and archived artifacts are retained under `vendor/zenodo_14171745/` for verification and reproducibility.

**Project status:** The dataset, prompt-generation pipeline, ground-truth integration, and evaluation infrastructure have been prepared and validated. The new 324-scenario detailed-output experiment is ready for response collection, but its evaluation results remain pending.
