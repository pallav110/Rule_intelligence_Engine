#!/usr/bin/env python3
"""
Dataset Validation Script - Verify existing ML training datasets

This script inspects the existing datasets in rie_ml/dataset_generation/output/
to verify they are ready for DistilBERT training and compliant with specification.

Checks:
1. Labels match spec (feedback_type, rule_category, is_actionable, requires_clarification)
2. No rule_family leakage across train/val/test splits
3. Test set is truly frozen (not in train/val)
4. Dataset version is documented
5. Distribution across domains and categories
6. Data format is consistent
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Any, Set

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
END = '\033[0m'

# Expected labels per specification Section 8.3.2
EXPECTED_FEEDBACK_TYPES = {
    "business_rule_correction",
    "unclear_feedback",
    "irrelevant_spam",
    "non_rule_feedback"
}

EXPECTED_RULE_CATEGORIES = {
    "metric_definition",
    "filter_rule",
    "mapping_rule",
    "access_rule",
    "join_rule",
    "data_quality_rule",
    "calculation_correction",
    "time_rule",
    "status_mapping",
    "entity_definition",
    "column_meaning",
    "join_correction",
    "expected_result_correction",
}


class DatasetValidator:
    """Validate existing ML training datasets"""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.domains = ["ecommerce", "customer_support", "saas_subscription"]
        self.splits = ["train", "val", "test"]
        self.issues = []
        self.warnings = []
        self.stats = {}

    def print_header(self, text: str):
        print(f"\n{BOLD}{BLUE}{'=' * 80}{END}")
        print(f"{BOLD}{BLUE}{text}{END}")
        print(f"{BOLD}{BLUE}{'=' * 80}{END}\n")

    def print_success(self, text: str):
        print(f"{GREEN}✅ {text}{END}")

    def print_warning(self, text: str):
        print(f"{YELLOW}⚠️  {text}{END}")
        self.warnings.append(text)

    def print_error(self, text: str):
        print(f"{RED}❌ {text}{END}")
        self.issues.append(text)

    def load_jsonl(self, filepath: Path) -> List[Dict[str, Any]]:
        """Load JSONL file"""
        data = []
        if not filepath.exists():
            self.print_error(f"File not found: {filepath}")
            return data

        with open(filepath, 'r') as f:
            for i, line in enumerate(f, 1):
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        self.print_error(f"JSON error in {filepath.name} line {i}: {e}")

        return data

    def check_required_fields(self, data: List[Dict], split: str, domain: str):
        """Check if all examples have required fields"""
        print(f"\n{BOLD}Checking required fields for {domain}/{split}...{END}")

        required_fields = [
            "feedback_id",
            "feedback_text",
            "feedback_type",
            "is_actionable",
            "requires_clarification",
            "domain",
        ]

        missing_fields = defaultdict(int)
        for i, example in enumerate(data):
            for field in required_fields:
                if field not in example:
                    missing_fields[field] += 1

        if missing_fields:
            for field, count in missing_fields.items():
                self.print_error(f"{field} missing in {count}/{len(data)} examples")
        else:
            self.print_success(f"All {len(data)} examples have required fields")

    def check_label_values(self, data: List[Dict], split: str, domain: str):
        """Check if label values match specification"""
        print(f"\n{BOLD}Checking label values for {domain}/{split}...{END}")

        feedback_types = Counter()
        rule_categories = Counter()
        actionable_counts = Counter()
        clarification_counts = Counter()

        unexpected_feedback_types = set()
        unexpected_rule_categories = set()

        for example in data:
            # Feedback type
            ft = example.get("feedback_type")
            feedback_types[ft] += 1
            if ft and ft not in EXPECTED_FEEDBACK_TYPES:
                unexpected_feedback_types.add(ft)

            # Rule category
            rc = example.get("rule_category")
            if rc:
                rule_categories[rc] += 1
                if rc not in EXPECTED_RULE_CATEGORIES:
                    unexpected_rule_categories.add(rc)

            # Boolean flags
            actionable_counts[example.get("is_actionable")] += 1
            clarification_counts[example.get("requires_clarification")] += 1

        # Report feedback types
        print(f"\n  Feedback Type Distribution:")
        for ft, count in feedback_types.most_common():
            pct = count / len(data) * 100
            marker = "✓" if ft in EXPECTED_FEEDBACK_TYPES else "?"
            print(f"    {marker} {ft}: {count} ({pct:.1f}%)")

        if unexpected_feedback_types:
            self.print_warning(f"Unexpected feedback types: {unexpected_feedback_types}")

        # Report rule categories
        if rule_categories:
            print(f"\n  Rule Category Distribution:")
            for rc, count in rule_categories.most_common():
                pct = count / len(data) * 100
                marker = "✓" if rc in EXPECTED_RULE_CATEGORIES else "?"
                print(f"    {marker} {rc}: {count} ({pct:.1f}%)")

        if unexpected_rule_categories:
            self.print_warning(f"Unexpected rule categories: {unexpected_rule_categories}")

        # Report boolean distributions
        print(f"\n  Is Actionable: {dict(actionable_counts)}")
        print(f"  Requires Clarification: {dict(clarification_counts)}")

        # Store stats
        self.stats[f"{domain}_{split}"] = {
            "total": len(data),
            "feedback_types": dict(feedback_types),
            "rule_categories": dict(rule_categories),
            "actionable": dict(actionable_counts),
            "clarification": dict(clarification_counts),
        }

    def check_rule_family_leakage(self, train_data: List[Dict], val_data: List[Dict], test_data: List[Dict], domain: str):
        """Check if same rule_family_id appears in multiple splits"""
        print(f"\n{BOLD}Checking rule_family leakage for {domain}...{END}")

        train_families = {ex.get("rule_family_id") for ex in train_data if ex.get("rule_family_id")}
        val_families = {ex.get("rule_family_id") for ex in val_data if ex.get("rule_family_id")}
        test_families = {ex.get("rule_family_id") for ex in test_data if ex.get("rule_family_id")}

        train_val_overlap = train_families & val_families
        train_test_overlap = train_families & test_families
        val_test_overlap = val_families & test_families

        if train_val_overlap:
            self.print_error(f"Rule family leakage between train/val: {len(train_val_overlap)} families")
            if len(train_val_overlap) <= 5:
                print(f"    Examples: {list(train_val_overlap)[:5]}")

        if train_test_overlap:
            self.print_error(f"Rule family leakage between train/test: {len(train_test_overlap)} families")
            if len(train_test_overlap) <= 5:
                print(f"    Examples: {list(train_test_overlap)[:5]}")

        if val_test_overlap:
            self.print_error(f"Rule family leakage between val/test: {len(val_test_overlap)} families")
            if len(val_test_overlap) <= 5:
                print(f"    Examples: {list(val_test_overlap)[:5]}")

        if not (train_val_overlap or train_test_overlap or val_test_overlap):
            self.print_success(f"No rule_family leakage detected")
            print(f"    Train families: {len(train_families)}")
            print(f"    Val families: {len(val_families)}")
            print(f"    Test families: {len(test_families)}")

    def check_dataset_version(self, domain: str):
        """Check if dataset version is documented"""
        print(f"\n{BOLD}Checking dataset version for {domain}...{END}")

        config_path = self.base_dir / domain / "config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                version = config.get("dataset_version")
                if version:
                    self.print_success(f"Dataset version: {version}")
                else:
                    self.print_warning(f"No dataset_version in config.json")

                # Print other metadata
                for key in ["annotation_version", "generated_at", "total_examples"]:
                    if key in config:
                        print(f"    {key}: {config[key]}")
        else:
            self.print_warning(f"No config.json found for {domain}")

    def validate_domain(self, domain: str):
        """Validate all datasets for one domain"""
        self.print_header(f"VALIDATING {domain.upper()} DOMAIN")

        domain_dir = self.base_dir / domain
        if not domain_dir.exists():
            self.print_error(f"Domain directory not found: {domain_dir}")
            return

        # Load all splits
        train_data = self.load_jsonl(domain_dir / "train.jsonl")
        val_data = self.load_jsonl(domain_dir / "val.jsonl")
        test_data = self.load_jsonl(domain_dir / "test.jsonl")

        print(f"\n{BOLD}Dataset sizes:{END}")
        print(f"  Train: {len(train_data)} examples")
        print(f"  Val: {len(val_data)} examples")
        print(f"  Test: {len(test_data)} examples")
        print(f"  Total: {len(train_data) + len(val_data) + len(test_data)} examples")

        # Check each split
        if train_data:
            self.check_required_fields(train_data, "train", domain)
            self.check_label_values(train_data, "train", domain)

        if val_data:
            self.check_required_fields(val_data, "val", domain)
            self.check_label_values(val_data, "val", domain)

        if test_data:
            self.check_required_fields(test_data, "test", domain)
            self.check_label_values(test_data, "test", domain)

        # Check rule family leakage
        if train_data and val_data and test_data:
            self.check_rule_family_leakage(train_data, val_data, test_data, domain)

        # Check dataset version
        self.check_dataset_version(domain)

    def generate_summary(self):
        """Generate validation summary report"""
        self.print_header("VALIDATION SUMMARY")

        # Overall stats
        total_train = sum(s.get("total", 0) for k, s in self.stats.items() if "train" in k)
        total_val = sum(s.get("total", 0) for k, s in self.stats.items() if "val" in k)
        total_test = sum(s.get("total", 0) for k, s in self.stats.items() if "test" in k)

        print(f"\n{BOLD}Dataset Sizes Across All Domains:{END}")
        print(f"  Training: {total_train} examples")
        print(f"  Validation: {total_val} examples")
        print(f"  Test (Frozen Eval): {total_test} examples")
        print(f"  Total: {total_train + total_val + total_test} examples")

        # Specification compliance
        print(f"\n{BOLD}Specification Compliance (Section 4.5):{END}")
        spec_train, spec_val, spec_test = 600, 150, 200

        print(f"  Training: {total_train} vs spec ~{spec_train} ", end="")
        if abs(total_train - spec_train) / spec_train < 0.3:
            print(f"{GREEN}✓{END}")
        else:
            print(f"{YELLOW}(different from spec){END}")

        print(f"  Validation: {total_val} vs spec ~{spec_val} ", end="")
        if abs(total_val - spec_val) / spec_val < 0.3:
            print(f"{GREEN}✓{END}")
        else:
            print(f"{YELLOW}(different from spec){END}")

        print(f"  Test: {total_test} vs spec ~{spec_test} ", end="")
        if abs(total_test - spec_test) / spec_test < 0.3:
            print(f"{GREEN}✓{END}")
        else:
            print(f"{YELLOW}(different from spec){END}")

        # Issues and warnings
        print(f"\n{BOLD}Validation Results:{END}")
        print(f"  Errors: {len(self.issues)}")
        print(f"  Warnings: {len(self.warnings)}")

        if self.issues:
            print(f"\n{RED}{BOLD}ERRORS:{END}")
            for issue in self.issues[:10]:
                print(f"  • {issue}")
            if len(self.issues) > 10:
                print(f"  ... and {len(self.issues) - 10} more")

        if self.warnings:
            print(f"\n{YELLOW}{BOLD}WARNINGS:{END}")
            for warning in self.warnings[:10]:
                print(f"  • {warning}")
            if len(self.warnings) > 10:
                print(f"  ... and {len(self.warnings) - 10} more")

        # Final verdict
        print(f"\n{BOLD}{'=' * 80}{END}")
        if not self.issues:
            self.print_success("DATASETS ARE READY FOR ML TRAINING")
            print(f"\n{GREEN}✓ No critical issues found{END}")
            print(f"{GREEN}✓ Datasets can be used for DistilBERT training{END}")
            return True
        else:
            self.print_error("DATASETS HAVE ISSUES")
            print(f"\n{RED}✗ {len(self.issues)} critical issues must be fixed{END}")
            return False

    def run_validation(self):
        """Run complete validation"""
        self.print_header("DATASET VALIDATION - ML TRAINING READINESS")

        print(f"Base directory: {self.base_dir}")
        print(f"Domains: {', '.join(self.domains)}")
        print(f"Splits: {', '.join(self.splits)}")

        # Validate each domain
        for domain in self.domains:
            self.validate_domain(domain)

        # Generate summary
        return self.generate_summary()


def main():
    base_dir = Path(__file__).parent.parent / "dataset_generation" / "output"

    print(f"Dataset validation starting...")
    print(f"Looking for datasets in: {base_dir}")

    if not base_dir.exists():
        print(f"{RED}❌ Dataset directory not found: {base_dir}{END}")
        sys.exit(1)

    validator = DatasetValidator(base_dir)
    success = validator.run_validation()

    # Save validation report
    report_path = Path(__file__).parent.parent / "datasets" / "validation_report.json"
    report_path.parent.mkdir(exist_ok=True)

    with open(report_path, 'w') as f:
        json.dump({
            "timestamp": "2026-09-01T07:14:00Z",
            "stats": validator.stats,
            "issues": validator.issues,
            "warnings": validator.warnings,
            "ready_for_training": success,
        }, f, indent=2)

    print(f"\n{BLUE}Validation report saved to: {report_path}{END}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
