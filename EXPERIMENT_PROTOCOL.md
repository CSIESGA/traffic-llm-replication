# Manual LLM experiment protocol

Use this protocol if you do **not** call the API and paste one scenario at a time into ChatGPT.

## Freeze the experimental variables

1. Use the same model/version for every scenario.
2. Use a **new chat (preferably Temporary Chat)** for every scenario so previous answers do not leak into the next test.
3. Paste the exact prompt exported by `export_manual_prompts.py`; do not paraphrase it.
4. Do not correct the model or add follow-up hints. First response only.
5. Run all scenarios in one short testing window and record date/time, because hosted models can change.
6. Randomize scenario order. Do not reveal ground truth.
7. Use the same output JSON schema for every trial.
8. For a stronger experiment, repeat each scenario 3–5 times in fresh chats and report mean/SD and/or majority-vote stability.

## Ground-truth rule

For the **primary replication analysis**, freeze the official source and provenance:

- Primary backend: authors' **Zenodo record 14171745** (`--backend official`).
- Record DOI: `10.5281/zenodo.14171745`.
- Keep `vendor/zenodo_14171745/manifest.json` with checksums in your experiment archive.
- Record the exact adapter configuration used (`official_adapter_config.json`).
- Do not edit the author code after collecting predictions unless you start a new, separately reported experiment version.

The `reconstruction` backend is a secondary baseline only. If used, report it separately and freeze its `GTConfig` values before looking at LLM outputs.

## What to measure

Primary: scenario-level conflict classification (Accuracy, Precision, Recall, F1, confusion matrix).

Secondary: conflict-pair precision/recall/F1, action accuracy, waiting-time MAE/RMSE, and priority-order agreement.

ROUGE-L can be added only to reproduce the paper's free-text comparison. Structured-field metrics are more diagnostic for this project.
