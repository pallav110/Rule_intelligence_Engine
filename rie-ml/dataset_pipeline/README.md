RIE Dataset Pipeline
====================

This directory contains a simple, deterministic dataset generator for the RIE domain packs.

Usage (small test):

```
python3 -m rie_ml.dataset_pipeline.make_dataset
```

Configuration: `config.json` controls random seed and target sizes. The generator is domain-agnostic and reads domain packs under `rie-ml/domain-packs`.
