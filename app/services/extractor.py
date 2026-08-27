"""Extraction service for business rule extraction.

Uses trained baseline extractor (template-based) for deterministic
rule extraction with fallback to simple patterns if needed.
"""

import re
import os
from typing import Dict, Any, List
from pathlib import Path


class RealExtractor:
    """Extract business rules from feedback text."""

    def __init__(self, domain: str = "ecommerce"):
        """Initialize extractor with optional trained baseline model."""
        self.domain = domain
        self.is_ready = False
        self.extractor = None
        self.glossary = None
        self.schema = None
        self._fallback_to_simple = False

        # Try to load baseline extractor
        self._load_baseline_extractor()

    def _load_baseline_extractor(self):
        """Load trained baseline extractor if available."""
        try:
            from rie_ml.src.baseline.extractor import BaselineExtractor, load_glossary, load_schema

            # Load glossary and schema
            self.glossary = load_glossary(self.domain)
            self.schema = load_schema(self.domain)

            if self.glossary and self.schema:
                self.extractor = BaselineExtractor(self.glossary, self.schema)
                self.is_ready = True
                print(f"✅ Loaded baseline extractor for domain: {self.domain}")
            else:
                print(f"⚠️  No glossary/schema found for {self.domain}, using simple fallback")
                self._fallback_to_simple = True
        except Exception as e:
            print(f"⚠️  Failed to load baseline extractor: {e}, using simple fallback")
            self._fallback_to_simple = True

    def extract(
        self,
        feedback: str,
        classification: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Extract business rules from feedback text.

        Parameters
        ----------
        feedback: str
            Raw feedback text.
        classification: dict
            Classification result (optional).

        Returns
        -------
        dict
            {
                "extracted_rules": [
                    {
                        "business_term": str,
                        "operation": str,
                        "conditions": [{"field": str, "operator": str, "value": any}],
                        "scope": str,
                        "confidence": float
                    }
                ],
                "confidence": float,
                "method": "baseline|fallback",
                "error": str (if applicable)
            }
        """
        if self.is_ready and self.extractor and not self._fallback_to_simple:
            try:
                result = self.extractor.extract(feedback, classification or {})
                return {
                    "extracted_rules": [{
                        "business_term": result["business_term"],
                        "operation": result["operation"],
                        "conditions": result["conditions"],
                        "scope": result["scope"],
                        "confidence": result["confidence"]["overall"]
                    }],
                    "confidence": result["confidence"]["overall"],
                    "method": "baseline",
                    "field_confidence": result["confidence"]
                }
            except Exception as e:
                print(f"⚠️  Extractor failed: {e}, falling back to simple patterns")
                return self._extract_with_simple_patterns(feedback)
        else:
            return self._extract_with_simple_patterns(feedback)

    def _extract_with_simple_patterns(self, feedback: str) -> Dict[str, Any]:
        """Extract using simple regex patterns (fallback)."""
        text = feedback.lower()
        result = {
            "business_term": None,
            "operation": None,
            "conditions": [],
            "scope": "global"
        }

        # Extract business term
        business_terms = ["revenue", "order", "customer", "product", "payment"]
        for term in business_terms:
            if term in text:
                result["business_term"] = term
                break

        # Extract operation
        if any(word in text for word in ["exclude", "remove", "omit"]):
            result["operation"] = "exclude"
        elif any(word in text for word in ["include", "add"]):
            result["operation"] = "include"
        elif any(word in text for word in ["restrict", "limit"]):
            result["operation"] = "restrict"
        elif any(word in text for word in ["map", "convert"]):
            result["operation"] = "map"

        # Extract simple conditions
        if "status" in text and "cancelled" in text:
            result["conditions"].append({
                "field": "orders.status",
                "operator": "equals",
                "value": "cancelled"
            })
        elif "status" in text and "failed" in text:
            result["conditions"].append({
                "field": "payments.status",
                "operator": "equals",
                "value": "failed"
            })

        # Calculate confidence
        confidence = 0.5
        if result["business_term"]:
            confidence += 0.1
        if result["operation"]:
            confidence += 0.1
        if result["conditions"]:
            confidence += 0.1

        return {
            "extracted_rules": [result],
            "confidence": round(confidence, 3),
            "method": "fallback",
            "field_confidence": {
                "business_term": 0.6 if result["business_term"] else 0.0,
                "operation": 0.6 if result["operation"] else 0.0,
                "conditions": 0.6 if result["conditions"] else 0.0,
                "scope": 0.5
            }
        }

    def train(self, training_data, labels):
        """Train extractor (not used with baseline model)."""
        self.is_ready = True
        return {"status": "using_baseline_model"}


if __name__ == "__main__":
    # Test the extractor
    extractor = RealExtractor("ecommerce")

    test_feedback = "Revenue should exclude cancelled orders"
    classification = {
        "feedback_type": "business_rule_correction",
        "rule_category": "metric_definition"
    }

    result = extractor.extract(test_feedback, classification)
    print("Extraction Result:")
    print(result)
