"""Main dataset generation pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .config import GenerationConfig
from .seed_validator import SeedValidator
from .generators import GenerationPipeline
from .post_validator import PostGenerationValidator
from .dataset_splitter import DatasetSplitter
from .output_writer import OutputWriter


class DatasetGenerationPipeline:
    """Main pipeline for generating synthetic feedback datasets."""
    
    def __init__(self, config: GenerationConfig):
        self.config = config
        self.output_writer = OutputWriter(config.output_dir)
        
        # Initialize components
        self.seed_validator = SeedValidator(config.domain_pack_path)
        self.post_validator = PostGenerationValidator(
            config.domain_pack_path,
            strict=config.strict_validation
        )
        self.dataset_splitter = DatasetSplitter(random_seed=config.random_seed)
    
    def load_seed_data(self) -> list[dict[str, Any]]:
        """Load seed data from seed.jsonl."""
        seed_records: list[dict[str, Any]] = []
        
        with self.config.seed_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                seed_records.append(record)
        
        return seed_records
    
    def validate_seed(self, seed_records: list[dict[str, Any]]) -> dict[str, Any]:
        """Validate seed data before generation."""
        print("Validating seed data...")
        validation_result = self.seed_validator.validate_seed_file(self.config.seed_path)
        
        if not validation_result["is_valid"]:
            print(f"Seed validation FAILED: {len(validation_result['errors'])} errors")
            for error in validation_result["errors"][:10]:
                print(f"  - {error}")
            if len(validation_result["errors"]) > 10:
                print(f"  ... and {len(validation_result['errors']) - 10} more errors")
        
        if validation_result["warnings"]:
            print(f"Seed validation warnings: {len(validation_result['warnings'])}")
            for warning in validation_result["warnings"][:5]:
                print(f"  - {warning}")
        
        return validation_result
    
    def generate(self, seed_records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Generate synthetic feedback from seed data."""
        print("Generating synthetic feedback...")
        
        generation_pipeline = GenerationPipeline(self.config, seed_records)
        generated = generation_pipeline.generate_all()
        
        # Print generation summary
        total_generated = sum(len(records) for records in generated.values())
        print(f"Generated {total_generated} records:")
        for gen_type, records in generated.items():
            print(f"  - {gen_type}: {len(records)}")
        
        return generated
    
    def validate_generated(
        self,
        generated: dict[str, list[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Validate generated synthetic data."""
        print("Validating generated data...")
        
        # Flatten all generated records
        all_generated: list[dict[str, Any]] = []
        for records in generated.values():
            all_generated.extend(records)
        
        validation_result = self.post_validator.validate_batch(all_generated)
        
        print(f"Validation: {validation_result['valid_records']} valid, {validation_result['rejected_records']} rejected")
        
        if validation_result["errors"]:
            print(f"Validation errors: {len(validation_result['errors'])}")
            for error in validation_result["errors"][:5]:
                print(f"  - {error}")
        
        if validation_result["warnings"]:
            print(f"Validation warnings: {len(validation_result['warnings'])}")
        
        # Check annotation consistency
        consistency_result = self.post_validator.check_annotation_consistency(all_generated)
        if not consistency_result["is_consistent"]:
            print(f"Consistency issues: {len(consistency_result['consistency_issues'])}")
            for issue in consistency_result["consistency_issues"][:5]:
                print(f"  - {issue}")
        
        return {
            **validation_result,
            "consistency": consistency_result,
        }
    
    def split_dataset(
        self,
        records: list[dict[str, Any]]
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
        """Split dataset into train/val/test and create task-specific datasets."""
        print("Splitting dataset...")
        
        # Combine seed records with generated records
        all_records = records
        
        # Split by rule_family_id
        split_result = self.dataset_splitter.split_by_rule_family(
            all_records,
            target_train_size=self.config.target_train_size,
            target_val_size=self.config.target_val_size,
            target_test_size=self.config.target_test_size,
        )
        
        print(f"Split: {len(split_result.train)} train, {len(split_result.val)} val, {len(split_result.test)} test")
        
        # Create task-specific datasets from full dataset
        task_datasets = self.dataset_splitter.create_task_specific_datasets(all_records)
        
        print(f"Task-specific datasets:")
        print(f"  - Classification: {len(task_datasets['classification'])}")
        print(f"  - Extraction: {len(task_datasets['extraction'])}")
        print(f"  - Clarification: {len(task_datasets['clarification'])}")
        
        # Create duplicate and conflict pairs
        duplicate_pairs = self.dataset_splitter.create_duplicate_pairs(all_records)
        conflict_pairs = self.dataset_splitter.create_conflict_pairs(all_records)
        
        print(f"  - Duplicate pairs: {len(duplicate_pairs)}")
        print(f"  - Conflict pairs: {len(conflict_pairs)}")
        
        datasets = {
            "train": split_result.train,
            "val": split_result.val,
            "test": split_result.test,
            "classification": task_datasets["classification"],
            "extraction": task_datasets["extraction"],
            "clarification": task_datasets["clarification"],
            "duplicate_pairs": duplicate_pairs,
            "conflict_pairs": conflict_pairs,
        }
        
        return datasets, split_result.split_info
    
    def write_outputs(
        self,
        generated: dict[str, list[dict[str, Any]]],
        validation_result: dict[str, Any],
        datasets: dict[str, list[dict[str, Any]]],
        split_info: dict[str, Any],
        seed_validation: dict[str, Any],
    ) -> None:
        """Write all output files."""
        print("Writing output files...")
        
        # Save configuration
        self.output_writer.write_json(
            self.config.to_dict(),
            "config.json"
        )
        
        # Write candidates (all generated before validation)
        all_generated: list[dict[str, Any]] = []
        for records in generated.values():
            all_generated.extend(records)
        self.output_writer.write_jsonl(
            all_generated,
            self.config.output_candidates
        )
        
        # Write approved (valid records only)
        approved = validation_result.get("valid_records_data", [])
        self.output_writer.write_jsonl(
            approved,
            self.config.output_approved
        )
        
        # Write rejected
        rejected = validation_result.get("rejected_records_data", [])
        self.output_writer.write_jsonl(
            rejected,
            self.config.output_rejected
        )
        
        # Write train/val/test splits
        self.output_writer.write_jsonl(
            datasets["train"],
            self.config.output_train
        )
        self.output_writer.write_jsonl(
            datasets["val"],
            self.config.output_val
        )
        self.output_writer.write_jsonl(
            datasets["test"],
            self.config.output_test
        )
        
        # Write task-specific datasets
        self.output_writer.write_jsonl(
            datasets["classification"],
            self.config.output_classification
        )
        self.output_writer.write_jsonl(
            datasets["extraction"],
            self.config.output_extraction
        )
        self.output_writer.write_jsonl(
            datasets["clarification"],
            self.config.output_clarification
        )
        
        # Write duplicate and conflict pairs
        self.output_writer.write_jsonl(
            datasets["duplicate_pairs"],
            self.config.output_duplicate_pairs
        )
        self.output_writer.write_jsonl(
            datasets["conflict_pairs"],
            self.config.output_conflict_pairs
        )
        
        # Write validation report
        report = {
            "config": self.config.to_dict(),
            "seed_validation": {
                "is_valid": seed_validation["is_valid"],
                "total_records": seed_validation["total_records"],
                "valid_records": seed_validation["valid_records"],
                "invalid_records": seed_validation["invalid_records"],
                "errors": seed_validation["errors"],
                "warnings": seed_validation["warnings"],
            },
            "generation_breakdown": {
                gen_type: len(records) for gen_type, records in generated.items()
            },
            "total_generated": len(all_generated),
            "validation": {
                "total_records": validation_result["total_records"],
                "valid_records": validation_result["valid_records"],
                "rejected_records": validation_result["rejected_records"],
                "errors": validation_result["errors"],
                "warnings": validation_result["warnings"],
                "consistency_issues": validation_result.get("consistency", {}).get("consistency_issues", []),
            },
            "split_info": split_info,
        }
        
        self.output_writer.write_report(
            report,
            self.config.output_validation_report
        )
        
        # Write markdown report
        self.output_writer.write_markdown_report(
            report,
            "report.md"
        )
        
        print(f"Output files written to {self.config.output_dir}")
    
    def run(self) -> dict[str, Any]:
        """Run the complete pipeline."""
        print("=" * 60)
        print("RIE Dataset Generation Pipeline")
        print("=" * 60)
        print(f"Domain: {self.config.domain_pack_id}")
        print(f"Version: {self.config.domain_pack_version}")
        print(f"Output: {self.config.output_dir}")
        print(f"Random seed: {self.config.random_seed}")
        print("=" * 60)
        
        # Load seed data
        seed_records = self.load_seed_data()
        print(f"Loaded {len(seed_records)} seed records")
        
        # Validate seed
        seed_validation = self.validate_seed(seed_records)
        
        if not seed_validation["is_valid"] and self.config.strict_validation:
            print("\nERROR: Seed validation failed in strict mode. Aborting.")
            return {"success": False, "reason": "seed_validation_failed"}
        
        # Generate synthetic data
        generated = self.generate(seed_records)
        
        # Validate generated data
        validation_result = self.validate_generated(generated)
        
        # Combine seed + generated for splitting
        all_records = seed_records + validation_result.get("valid_records_data", [])
        
        # Split dataset
        datasets, split_info = self.split_dataset(all_records)
        
        # Write outputs
        self.write_outputs(
            generated,
            validation_result,
            datasets,
            split_info,
            seed_validation,
        )
        
        print("=" * 60)
        print("Pipeline completed successfully!")
        print("=" * 60)
        
        return {
            "success": True,
            "total_records": len(all_records),
            "generated": len(validation_result.get("valid_records_data", [])),
            "rejected": len(validation_result.get("rejected_records_data", [])),
        }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="RIE Dataset Generation Pipeline")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config JSON file",
    )
    parser.add_argument(
        "--domain-pack",
        type=Path,
        help="Path to domain pack directory",
    )
    parser.add_argument(
        "--seed",
        type=Path,
        help="Path to seed.jsonl file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict validation (fail on errors)",
    )
    
    args = parser.parse_args()
    
    # Load or create config
    if args.config and args.config.exists():
        config = GenerationConfig.load(args.config)
    else:
        config = GenerationConfig()
        
        if args.domain_pack:
            config.domain_pack_path = args.domain_pack
        if args.seed:
            config.seed_path = args.seed
        if args.output:
            config.output_dir = args.output
        if args.random_seed:
            config.random_seed = args.random_seed
        if args.strict:
            config.strict_validation = True
    
    # Run pipeline
    pipeline = DatasetGenerationPipeline(config)
    result = pipeline.run()
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
