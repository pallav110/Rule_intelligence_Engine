#!/usr/bin/env python3
"""
Patch the trained RoBERTa best_model.pt to embed label_mappings + config,
so all three handoff checkpoints (DistilBERT/BERT/RoBERTa) are uniform for
the CPU-only co-developer. No retraining — pure metadata rewrite.

Safe: writes to a temp file first, then atomically replaces best_model.pt.
The original was already backed up to best_model.pt.bak by the operator.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ml_models import (
    FEEDBACK_TYPE_LABELS,
    RULE_CATEGORY_LABELS,
    get_label_mappings,
)

MODEL_TYPE = "roberta_candidate"
CKPT = Path(__file__).parent.parent.parent / "models" / MODEL_TYPE / "checkpoints" / "best_model.pt"


def main():
    print(f"Loading checkpoint: {CKPT}")
    ckpt = __import__("torch").load(CKPT, map_location="cpu", weights_only=False)

    keys = set(ckpt.keys())
    print(f"Existing top-level keys: {sorted(keys)}")

    if "label_mappings" in keys or "config" in keys:
        print("WARNING: checkpoint already has label_mappings/config. Aborting (no overwrite).")
        sys.exit(1)
    if "model_state_dict" not in keys:
        print("FATAL: no model_state_dict — refusing to patch a non-model checkpoint.")
        sys.exit(1)

    # Add metadata matching the BERT best_model.pt convention.
    ckpt["label_mappings"] = get_label_mappings()
    ckpt["config"] = {
        "num_feedback_types": len(FEEDBACK_TYPE_LABELS),
        "num_rule_categories": len(RULE_CATEGORY_LABELS),
        "model_name": "roberta-base",
        "batch_size": 8,
    }

    print("label_mappings keys:", sorted(ckpt["label_mappings"].keys()))
    print("config:", json.dumps(ckpt["config"], indent=2))

    # Atomic write: temp file then replace.
    tmp = CKPT.with_suffix(".pt.tmp")
    print(f"Saving to temp: {tmp}")
    __import__("torch").save(ckpt, tmp)
    print(f"Replacing {CKPT}")
    tmp.replace(CKPT)

    # Verify round-trip.
    reloaded = __import__("torch").load(CKPT, map_location="cpu", weights_only=False)
    print("POST-PATCH top-level keys:", sorted(reloaded.keys()))
    print("POST-PATCH label_mappings present:", "label_mappings" in reloaded)
    print("POST-PATCH config present:", "config" in reloaded)
    n_params = sum(p.numel() for p in reloaded["model_state_dict"].values())
    print(f"POST-PATCH param count (state_dict): {n_params}")
    print("DONE")


if __name__ == "__main__":
    main()