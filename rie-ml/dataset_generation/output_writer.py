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
    
    def write_jsonl(self, records: list[dict[str, Any]], filename: str) -> None:
        """Write records to a JSONL file."""
        output_path = self.output_dir / filename
        with output_path.open("w", encoding="utf-8") as f:
            for record in records:
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
            f.write(f"- Total records generated: {report.get('total_records', 0)}\n")
            f.write(f"- Valid records: {report.get('valid_records', 0)}\n")
            f.write(f"- Rejected records: {report.get('rejected_records', 0)}\n")
            f.write(f"- Validation errors: {len(report.get('errors', []))}\n")
            f.write(f"- Validation warnings: {len(report.get('warnings', []))}\n\n")
            
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
                f.write(f"- Train: {split_info.get('train', {}).get('count', 0)} records ({split_info.get('train', {}).get('ratio', 0):.1%})\n")
                f.write(f"- Validation: {split_info.get('val', {}).get('count', 0)} records ({split_info.get('val', {}).get('ratio', 0):.1%})\n")
                f.write(f"- Test: {split_info.get('test', {}).get('count', 0)} records ({split_info.get('test', {}).get('ratio', 0):.1%})\n")
                f.write(f"- Rule families: {split_info.get('total_rule_families', 0)}\n\n")
            
            # Errors
            if report.get("errors"):
                f.write("## Validation Errors\n\n")
                for error in report["errors"][:50]:  # Limit to first 50
                    f.write(f"- {error}\n")
                if len(report["errors"]) > 50:
                    f.write(f"- ... and {len(report['errors']) - 50} more errors\n")
                f.write("\n")
            
            # Warnings
            if report.get("warnings"):
                f.write("## Validation Warnings\n\n")
                for warning in report["warnings"][:50]:  # Limit to first 50
                    f.write(f"- {warning}\n")
                if len(report["warnings"]) > 50:
                    f.write(f"- ... and {len(report['warnings']) - 50} more warnings\n")
                f.write("\n")
            
            # Configuration
            if "config" in report:
                f.write("## Configuration\n\n")
                f.write("```json\n")
                f.write(json.dumps(report["config"], indent=2))
                f.write("\n```\n")
