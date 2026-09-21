# Zenodo integration changes

This revision makes ground-truth provenance explicit.

1. Confirmed from the published paper that the official supporting code/data are deposited at Zenodo record **14171745** (DOI `10.5281/zenodo.14171745`).
2. Renamed the prior custom simulator to `ground_truth_reconstruction.py`; it is no longer described as author code.
3. Added `install_zenodo_ground_truth.py` to fetch/verify/extract the official public record on the user's machine without executing it.
4. Added `inspect_zenodo_ground_truth.py` for static AST inspection of downloaded Python files.
5. Added `official_ground_truth_adapter.py` plus `official_adapter_config.json` so the actual author entry point can be wired without guessing function names.
6. Added `ground_truth.py` as an explicit backend router (`official` vs `reconstruction`).
7. Changed primary experiment commands/default evaluation directory to `data/ground_truth_official`.
8. Moved the 24 old generated labels to `data/ground_truth_reconstruction` and marked their metadata as non-author reconstruction outputs.
9. Added `ZENODO_GROUND_TRUTH.md` with the exact installation/mapping workflow.

## Current status

The publication and Zenodo DOI were verified, but the build sandbox could not retrieve the Zenodo file bytes. Consequently, this ZIP does **not** pretend that the authors' code has already been downloaded or mapped. The one-command installer completes that download on a normal internet-connected machine. The final module/function mapping must be based on the actual downloaded source, not guessed from the paper.
