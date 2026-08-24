"""Output writer for saving generated datasets to files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from datetime import datetime


class OutputWriter:
    """Writes generated datasets to output files."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def write_jsonl(self, records: list[dict[str, Any]], filename: str, preserve_internal: bool = False) -> None:
        """Write records to a JSONL file.
        
        Args:
            records: List of records to write
            filename: Output filename
            preserve_internal: If True, preserve internal _-prefixed fields (for rejected.jsonl)
        """
        output_path = self.output_dir / filename
        with output_path.open("w", encoding="utf-8") as f:
            for record in records:
                if preserve_internal:
                    # Keep all fields including internal validation fields
                    clean_record = record
                else:
                    # Remove internal validation fields before writing
                    clean_record = {k: v for k, v in record.items() if not k.startswith("_")}
                f.write(json.dumps(clean_record, ensure_ascii=False) + "\n")
    
    def write_json(self, data: dict[str, Any] | list[dict[str, Any]], filename: str) -> None:
        """Write data to a JSON file."""
        output_path = self.output_dir / filename
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def write_report(self, report: dict[str, Any], filename: str) -> None:
        """Write a validation/generation report."""
        output_path = self.output_dir / filename
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    def write_markdown_report(self, report: dict[str, Any], filename: str) -> None:
        """Write a human-readable markdown report."""
        output_path = self.output_dir / filename
        with output_path.open("w", encoding="utf-8") as f:
            f.write("# Dataset Generation Report\n\n")
            f.write(f"**Generated at:** {datetime.utcnow().isoformat() + 'Z'}\n\n")
            
            # Summary
            f.write("## Summary\n\n")
            f.write(f"- Seed records: {report.get('seed_records', 0)}\n")
            f.write(f"- Total generated: {report.get('total_generated', 0)}\n")
            f.write(f"- Approved generated: {report.get('approved_generated', 0)}\n")
            f.write(f"- Rejected generated: {report.get('rejected_generated', 0)}\n")
            f.write(f"- **Total for splitting**: {report.get('total_for_splitting', 0)} (seed + approved generated)\n")
            f.write(f"- Validation errors: {len(report.get('validation', {}).get('errors', []))}\n")
            f.write(f"- Validation warnings: {len(report.get('validation', {}).get('warnings', []))}\n\n")
            
            # Generation breakdown
            if "generation_breakdown" in report:
                f.write("## Generation Breakdown\n\n")
                for gen_type, count in report["generation_breakdown"].items():
                    f.write(f"- {gen_type}: {count}\n")
                f.write("\n")
            
            # Split information
            if "split_info" in report:
                f.write("## Dataset Split\n\n")
                split_info = report["split_info"]
                config = report.get("config", {})
                
                f.write(f"**Target sizes:** Train={config.get('target_train_size', 0)}, Val={config.get('target_val_size', 0)}, Test={config.get('target_test_size', 0)}\n\n")
                f.write("**Actual sizes:**\n")
                f.write(f"- Train: {split_info.get('train', {}).get('count', 0)} records ({split_info.get('train', {}).get('ratio', 0):.1%}) - {split_info.get('train', {}).get('families', 0)} rule families\n")
                f.write(f"- Validation: {split_info.get('val', {}).get('count', 0)} records ({split_info.get('val', {}).get('ratio', 0):.1%}) - {split_info.get('val', {}).get('families', 0)} rule families\n")
                f.write(f"- Test: {split_info.get('test', {}).get('count', 0)} records ({split_info.get('test', {}).get('ratio', 0):.1%}) - {split_info.get('test', {}).get('families', 0)} rule families\n")
                f.write(f"- Total rule families: {split_info.get('total_rule_families', 0)}\n\n")
                
                # Explain split discrepancy
                total_available = report.get('total_for_splitting', 0)
                target_total = config.get('target_train_size', 0) + config.get('target_val_size', 0) + config.get('target_test_size', 0)
                if total_available < target_total:
                    f.write(f"**⚠️ Insufficient data for target split:** Available {total_available} records vs target {target_total}. ")
                    f.write(f"Split sizes are limited by available rule families and records. Add more seed data or increase generation multipliers to reach targets.\n\n")
            
            # Task-specific datasets
            if "task_datasets" in report:
                f.write("## Task-Specific Datasets\n\n")
                task_datasets = report["task_datasets"]
                f.write(f"- Classification: {task_datasets.get('classification', 0)} records\n")
                f.write(f"- Extraction: {task_datasets.get('extraction', 0)} records\n")
                f.write(f"- Clarification: {task_datasets.get('clarification', 0)} records\n")
                f.write(f"- Duplicate pairs: {task_datasets.get('duplicate_pairs', 0)} pairs\n")
                f.write(f"- Conflict pairs: {task_datasets.get('conflict_pairs', 0)} pairs\n\n")
                
                # Explain pair discrepancies
                dup_target = config.get('target_duplicate_pairs', 0)
                conf_target = config.get('target_conflict_pairs', 0)
                if task_datasets.get('duplicate_pairs', 0) < dup_target:
                    f.write(f"**⚠️ Duplicate pairs:** Generated {task_datasets.get('duplicate_pairs', 0)} vs target {dup_target}. ")
                    f.write(f"Limited by rule families with 2+ members. Increase paraphrase_multiplier or add more seed paraphrases.\n\n")
                if task_datasets.get('conflict_pairs', 0) < conf_target:
                    f.write(f"**⚠️ Conflict pairs:** Generated {task_datasets.get('conflict_pairs', 0)} vs target {conf_target}. ")
                    f.write(f"Limited by seeds with numeric thresholds that can create conflicts. Add more threshold-based rules to seed.\n\n")
            
            # Rule family analysis
            if "rule_family_analysis" in report:
                f.write("## Rule Family Analysis\n\n")
                rfa = report["rule_family_analysis"]
                f.write(f"- Total rule families: {rfa.get('total_rule_families', 0)}\n")
                f.write(f"- Business rule families: {rfa.get('business_rule_families', 0)} ({rfa.get('business_rule_records', 0)} records)\n")
                f.write(f"- Non-business families: {rfa.get('non_business_families', 0)} ({rfa.get('non_business_records', 0)} records)\n\n")
                
                # Break down non-business families
                non_business_by_category = {}
                for family in rfa.get("non_business_family_details", []):
                    cat = family.get("category", "other")
                    non_business_by_category[cat] = non_business_by_category.get(cat, 0) + family.get("count", 0)
                
                if non_business_by_category:
                    f.write("Non-business breakdown:\n")
                    for cat, count in sorted(non_business_by_category.items()):
                        f.write(f"- {cat}: {count} records\n")
                    f.write("\n")
            
            # Errors
            validation_errors = report.get("validation", {}).get("errors", [])
            if validation_errors:
                f.write("## Validation Errors\n\n")
                for error in validation_errors[:50]:  # Limit to first 50
                    f.write(f"- {error}\n")
                if len(validation_errors) > 50:
                    f.write(f"- ... and {len(validation_errors) - 50} more errors\n")
                f.write("\n")
            
            # Warnings
            validation_warnings = report.get("validation", {}).get("warnings", [])
            if validation_warnings:
                f.write("## Validation Warnings\n\n")
                for warning in validation_warnings[:50]:  # Limit to first 50
                    f.write(f"- {warning}\n")
                if len(validation_warnings) > 50:
                    f.write(f"- ... and {len(validation_warnings) - 50} more warnings\n")
                f.write("\n")
            
            # Configuration
            if "config" in report:
                f.write("## Configuration\n\n")
                f.write("```json\n")
                f.write(json.dumps(report["config"], indent=2))
                f.write("\n```\n")
