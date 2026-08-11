RIE Dataset v1 — Reproducibility

Configuration:
- Config file: rie-ml/dataset_pipeline/config.json (version: v1)
- Random seed: 42

Reproducible commands (from repository root):

- Generate full dataset (writes to `rie-ml/datasets/generated/v1`):

  python3 -m rie-ml.dataset_pipeline.make_dataset

- Generate small test dataset:

  python3 -m rie-ml.dataset_pipeline.make_dataset --small

Notes:
- The `make_dataset` module runs generation, basic validation, family-safe splitting, pair generation (duplicate/conflict/clarifications), and a stronger pairs+split validation.
- Do not modify the `rie-ml/domain-packs/*` contents or the seed if you need exact reproducibility.
