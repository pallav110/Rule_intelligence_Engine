"""Validation pipeline orchestrating schema validation in the suggestion workflow.

Integrates with classification results, extraction results, and domain pack schema
to produce comprehensive validation decisions and routing recommendations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pathlib import Path

from app.services.schema_validation_service import SchemaValidationService
from app.services.domain_pack_loader import DomainPackLoader


class ValidationPipeline:
    """Orchestrates full validation pipeline for suggestion processing."""

    def __init__(self, domain_pack_id: str = None):
        """Initialize validation pipeline with optional domain pack."""
        self.domain_pack_id = domain_pack_id
        self.domain_pack_loader = DomainPackLoader()
        self.schema_validator = None
        self.domain_schema = None
        self.glossary = None

        if domain_pack_id:
            self._load_domain_pack(domain_pack_id)

    def _load_domain_pack(self, pack_id: str):
        """Load domain pack schema and metadata."""
        try:
            self.domain_schema = self.domain_pack_loader.load_schema(pack_id)
            self.glossary = self._extract_glossary_terms()
            self.schema_validator = SchemaValidationService(self.domain_schema)
        except Exception as e:
            print(f"⚠️  Failed to load domain pack {pack_id}: {e}")
            self.domain_schema = None
            self.glossary = None

    def _extract_glossary_terms(self) -> List[str]:
        """Extract business terms from schema."""
        terms = []
        if not self.domain_schema:
            return terms

        # Extract from tables
        for table_name, table_info in self.domain_schema.get("tables", {}).items():
            terms.append(table_name)
            if isinstance(table_info, dict):
                if "description" in table_info:
                    terms.extend(table_info["description"].split())

        return [t.strip().lower() for t in terms if t.strip()]

    def validate_suggestion(
        self,
        classification_result: Dict[str, Any],
        extraction_result: Dict[str, Any],
        feedback_text: str,
        workspace_id: str = None,
    ) -> Dict[str, Any]:
        """
        Validate a complete suggestion (classification + extraction).

        Args:
            classification_result: Output from classification module
            extraction_result: Output from extraction module (contains rules)
            feedback_text: Original feedback text
            workspace_id: Workspace for domain pack lookup

        Returns:
            {
                "validation_id": str,
                "timestamp": str,
                "schema_validation": {
                    "status": "PASS|PARTIAL|FAIL",
                    "coverage": float,
                    "per_rule": [...]
                },
                "classification_confidence": float,
                "extraction_confidence": float,
                "mandatory_review_required": bool,
                "mandatory_review_reasons": [str],
                "routing_recommendation": "STANDARD|REVIEWER|SENIOR|CLARIFICATION",
                "overall_status": "APPROVED|REVIEW_REQUIRED|BLOCKED",
                "validation_summary": {
                    "valid_rules": int,
                    "partial_rules": int,
                    "failed_rules": int
                }
            }
        """
        validation_id = f"val_{datetime.utcnow().isoformat()}"
        results = {
            "validation_id": validation_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "schema_validation": {},
            "classification_confidence": classification_result.get("confidence", 0.0),
            "extraction_confidence": extraction_result.get("confidence", 0.0),
            "mandatory_review_required": False,
            "mandatory_review_reasons": [],
            "routing_recommendation": "STANDARD",
            "overall_status": "APPROVED",
            "validation_summary": {
                "valid_rules": 0,
                "partial_rules": 0,
                "failed_rules": 0
            }
        }

        # Validate extracted rules
        extracted_rules = extraction_result.get("extracted_rules", [])
        if not extracted_rules:
            results["mandatory_review_reasons"].append("No rules extracted")
            results["mandatory_review_required"] = True
            results["routing_recommendation"] = "CLARIFICATION"
            results["overall_status"] = "BLOCKED"
            return results

        schema_validations = []
        for i, rule in enumerate(extracted_rules):
            validation = self.schema_validator.validate_rule(
                rule,
                schema=self.domain_schema,
                glossary=self.glossary
            )
            schema_validations.append(validation)

            # Track status
            if validation["status"] == "PASS":
                results["validation_summary"]["valid_rules"] += 1
            elif validation["status"] == "PARTIAL":
                results["validation_summary"]["partial_rules"] += 1
            else:
                results["validation_summary"]["failed_rules"] += 1

        results["schema_validation"]["per_rule"] = schema_validations
        results["schema_validation"]["status"] = self._aggregate_rule_status(schema_validations)
        results["schema_validation"]["coverage"] = self._aggregate_coverage(schema_validations)

        # Apply decision rules (spec 8.9)
        results = self._apply_routing_rules(results, classification_result, extraction_result)

        return results

    def _aggregate_rule_status(self, validations: List[Dict[str, Any]]) -> str:
        """Aggregate status across multiple rules."""
        statuses = [v["status"] for v in validations]

        if all(s == "PASS" for s in statuses):
            return "PASS"
        elif any(s == "FAIL" for s in statuses):
            return "FAIL"
        else:
            return "PARTIAL"

    def _aggregate_coverage(self, validations: List[Dict[str, Any]]) -> float:
        """Aggregate coverage across multiple rules."""
        if not validations:
            return 0.0
        avg_coverage = sum(v["coverage"] for v in validations) / len(validations)
        return round(avg_coverage, 3)

    def _apply_routing_rules(
        self,
        results: Dict[str, Any],
        classification_result: Dict[str, Any],
        extraction_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply decision rules from spec 8.9 for review routing."""

        # Rule 1: Schema validation failed → Mandatory Manual Review (BLOCKED)
        schema_status = results["schema_validation"]["status"]
        if schema_status == "FAIL":
            results["mandatory_review_required"] = True
            results["mandatory_review_reasons"].append("Schema validation FAILED - cannot proceed")
            results["routing_recommendation"] = "REVIEWER"
            results["overall_status"] = "BLOCKED"
            return results

        # Rule 2: Schema validation is PARTIAL on mandatory component
        per_rule = results["schema_validation"]["per_rule"]
        for rule_validation in per_rule:
            if rule_validation["status"] == "PARTIAL":
                if not rule_validation["mandatory_fields_valid"]:
                    results["mandatory_review_required"] = True
                    results["mandatory_review_reasons"].append(
                        "Mandatory rule component failed validation"
                    )
                    results["routing_recommendation"] = "REVIEWER"
                    results["overall_status"] = "BLOCKED"
                    return results

        # Rule 3: Classification confidence below threshold
        class_conf = results["classification_confidence"]
        if class_conf < 0.70:  # 70% threshold
            results["mandatory_review_required"] = True
            results["mandatory_review_reasons"].append(
                f"Classification confidence low: {class_conf:.1%}"
            )
            results["routing_recommendation"] = "REVIEWER"
            results["overall_status"] = "REVIEW_REQUIRED"

        # Rule 4: Extraction confidence below threshold
        extract_conf = results["extraction_confidence"]
        if extract_conf < 0.70:  # 70% threshold
            results["mandatory_review_required"] = True
            results["mandatory_review_reasons"].append(
                f"Extraction confidence low: {extract_conf:.1%}"
            )
            results["routing_recommendation"] = "REVIEWER"
            results["overall_status"] = "REVIEW_REQUIRED"

        # Rule 5: Schema PARTIAL (but not mandatory)
        if results["schema_validation"]["status"] == "PARTIAL":
            results["mandatory_review_required"] = True
            results["mandatory_review_reasons"].append(
                f"Partial schema validation: {results['schema_validation']['coverage']:.0%} coverage"
            )
            results["routing_recommendation"] = "REVIEWER"
            results["overall_status"] = "REVIEW_REQUIRED"

        # If no issues found, approve
        if not results["mandatory_review_required"]:
            results["overall_status"] = "APPROVED"
            results["routing_recommendation"] = "STANDARD"

        return results

    def generate_validation_report(self, validation_result: Dict[str, Any]) -> str:
        """Generate human-readable validation report."""
        lines = [
            "=" * 80,
            "SCHEMA VALIDATION REPORT",
            "=" * 80,
            f"\nValidation ID: {validation_result['validation_id']}",
            f"Timestamp: {validation_result['timestamp']}",
            f"\nOverall Status: {validation_result['overall_status']}",
            f"Routing: {validation_result['routing_recommendation']}",
            f"Manual Review Required: {validation_result['mandatory_review_required']}",
        ]

        if validation_result["mandatory_review_reasons"]:
            lines.append("\nManual Review Reasons:")
            for reason in validation_result["mandatory_review_reasons"]:
                lines.append(f"  • {reason}")

        lines.extend([
            f"\nClassification Confidence: {validation_result['classification_confidence']:.1%}",
            f"Extraction Confidence: {validation_result['extraction_confidence']:.1%}",
            f"\nSchema Validation Status: {validation_result['schema_validation']['status']}",
            f"Schema Coverage: {validation_result['schema_validation']['coverage']:.1%}",
        ])

        summary = validation_result["validation_summary"]
        lines.append(f"\nValidation Summary:")
        lines.append(f"  Valid Rules: {summary['valid_rules']}")
        lines.append(f"  Partial Rules: {summary['partial_rules']}")
        lines.append(f"  Failed Rules: {summary['failed_rules']}")

        if validation_result["schema_validation"].get("per_rule"):
            lines.append("\nPer-Rule Results:")
            for i, rule_val in enumerate(validation_result["schema_validation"]["per_rule"]):
                lines.append(f"\n  Rule {i + 1}:")
                lines.append(f"    Status: {rule_val['status']}")
                lines.append(f"    Coverage: {rule_val['coverage']:.1%}")

                if rule_val["validation_errors"]:
                    lines.append("    Errors:")
                    for error in rule_val["validation_errors"][:3]:
                        lines.append(f"      - {error}")

        lines.append("\n" + "=" * 80)
        return "\n".join(lines)
