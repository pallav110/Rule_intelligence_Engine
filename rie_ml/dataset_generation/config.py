"""Configuration for dataset generation pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GenerationConfig:
    """Configuration for dataset generation."""

    # Domain pack configuration (set via CLI or config file)
    domain_pack_id: str = ""
    domain_pack_version: str = ""
    domain_pack_path: Path = Path(".")

    # Seed data (set via CLI or config file)
    seed_path: Path = Path(".")

    # Output configuration (set via CLI or config file)
    output_dir: Path = Path(".")
    
    # Dataset versioning
    dataset_version: str = "dataset_v0.2.0"
    annotation_version: str = "ann_v0.2.0"
    
    # Reproducibility
    random_seed: int = 42
    
    # Generation targets (approximate)
    target_train_size: int = 600
    target_val_size: int = 150
    target_test_size: int = 200
    target_duplicate_pairs: int = 150
    target_conflict_pairs: int = 150
    target_ambiguous: int = 100
    
    # Generation multipliers (per seed example)
    paraphrase_multiplier: int = 3
    conversational_multiplier: int = 2
    hinglish_multiplier: int = 1
    multi_rule_multiplier: int = 1
    
    # Validation
    strict_validation: bool = True
    allow_invalid_schema_refs: bool = False  # For schema validation test cases
    
    # Output files
    output_candidates: str = "candidates.jsonl"
    output_approved: str = "approved.jsonl"
    output_classification: str = "classification.jsonl"
    output_extraction: str = "extraction.jsonl"
    output_clarification: str = "clarification.jsonl"
    output_duplicate_pairs: str = "duplicate_pairs.jsonl"
    output_conflict_pairs: str = "conflict_pairs.jsonl"
    output_rejected: str = "rejected.jsonl"
    output_validation_report: str = "validation_report.json"
    
    # Train/val/test split files
    output_train: str = "train.jsonl"
    output_val: str = "val.jsonl"
    output_test: str = "test.jsonl"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "domain_pack_id": self.domain_pack_id,
            "domain_pack_version": self.domain_pack_version,
            "domain_pack_path": str(self.domain_pack_path),
            "seed_path": str(self.seed_path),
            "output_dir": str(self.output_dir),
            "dataset_version": self.dataset_version,
            "annotation_version": self.annotation_version,
            "random_seed": self.random_seed,
            "target_train_size": self.target_train_size,
            "target_val_size": self.target_val_size,
            "target_test_size": self.target_test_size,
            "target_duplicate_pairs": self.target_duplicate_pairs,
            "target_conflict_pairs": self.target_conflict_pairs,
            "target_ambiguous": self.target_ambiguous,
            "paraphrase_multiplier": self.paraphrase_multiplier,
            "conversational_multiplier": self.conversational_multiplier,
            "hinglish_multiplier": self.hinglish_multiplier,
            "multi_rule_multiplier": self.multi_rule_multiplier,
            "strict_validation": self.strict_validation,
            "allow_invalid_schema_refs": self.allow_invalid_schema_refs,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenerationConfig":
        """Create config from dictionary."""
        # Convert string paths back to Path objects
        if "domain_pack_path" in data:
            data["domain_pack_path"] = Path(data["domain_pack_path"])
        if "seed_path" in data:
            data["seed_path"] = Path(data["seed_path"])
        if "output_dir" in data:
            data["output_dir"] = Path(data["output_dir"])
        return cls(**data)
    
    def save(self, path: Path) -> None:
        """Save config to JSON file."""
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "GenerationConfig":
        """Load config from JSON file."""
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
