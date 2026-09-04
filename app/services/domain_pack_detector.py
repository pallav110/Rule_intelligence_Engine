"""Domain pack auto-detection service.

Analyzes feedback text against available domain packs to determine
which domain the feedback belongs to based on schema entities and terminology.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class DomainPackDetector:
    """Auto-detect which domain pack feedback belongs to."""

    def __init__(self):
        """Initialize detector with all available domain packs."""
        self.domain_packs: Dict[str, Dict[str, Any]] = {}
        self._load_domain_packs()

    def _load_domain_packs(self) -> None:
        """Load all domain pack configurations and schemas."""
        domain_packs_dir = Path(__file__).parent.parent.parent / "rie_ml" / "domain-packs"

        for pack_dir in sorted(domain_packs_dir.iterdir()):
            if not pack_dir.is_dir():
                continue

            config_file = pack_dir / "domain_config.json"
            if not config_file.exists():
                continue

            try:
                with open(config_file) as f:
                    config = json.load(f)

                domain_id = config.get("domain_pack_id", pack_dir.name)

                # Load schema
                schema = {}
                schema_file = pack_dir / "schema" / "schema.json"
                if schema_file.exists():
                    with open(schema_file) as f:
                        schema = json.load(f)

                # Load taxonomy
                taxonomy = {}
                taxonomy_file = pack_dir / "taxonomy" / "labels.json"
                if taxonomy_file.exists():
                    with open(taxonomy_file) as f:
                        taxonomy = json.load(f)

                self.domain_packs[domain_id] = {
                    "config": config,
                    "schema": schema,
                    "taxonomy": taxonomy,
                }
            except Exception as e:
                print(f"Warning: Failed to load domain pack {pack_dir.name}: {e}")

    def detect(self, feedback_text: str) -> Tuple[str, float, Dict[str, Any]]:
        """
        Detect which domain pack the feedback belongs to.
        Enhanced with domain-specific heuristics and better confidence calculation.

        Returns:
            (domain_pack_id, confidence, reasoning)
        """
        if not feedback_text or not feedback_text.strip():
            return "customer_support", 0.0, {"error": "Empty feedback"}

        feedback_lower = feedback_text.lower()
        scores: Dict[str, float] = {}

        # Domain-specific keywords for better detection
        domain_keywords = {
            "ecommerce": [
                "revenue", "order", "payment", "product", "customer", "discount",
                "price", "cart", "checkout", "inventory", "shipping", "promotion",
                "transaction", "purchase", "sale", "billing", "receipt", "refund",
                "quantity", "sku", "catalog", "storefront", "merchant"
            ],
            "saas_subscription": [
                "subscription", "billing", "plan", "user", "license", "seat",
                "tier", "upgrade", "downgrade", "renewal", "invoice", "credit",
                "trial", "onboard", "tenant", "feature", "access", "entitlement",
                "churn", "retention", "usage", "quota"
            ],
            "customer_support": [
                "ticket", "support", "issue", "problem", "bug", "error",
                "help", "assistance", "complaint", "resolution", "incident",
                "request", "service", "agent", "priority", "escalation",
                "queue", "category", "tag", "assigned", "status"
            ]
        }

        # Score each domain pack
        for domain_id, pack_data in self.domain_packs.items():
            score = 0.0

            # Extract all searchable terms from this domain pack
            domain_terms = self._extract_domain_terms(pack_data)

            # Count schema/column matches
            matched_terms = []
            for term in domain_terms:
                if term in feedback_lower:
                    matched_terms.append(term)
                    score += 1.0

            # Boost score if multiple schema matches
            if len(matched_terms) > 1:
                score += len(matched_terms) * 0.5

            # Add heuristic keyword matching (stronger signal)
            if domain_id in domain_keywords:
                keyword_matches = sum(
                    2.0 for keyword in domain_keywords[domain_id]
                    if keyword in feedback_lower
                )
                score += keyword_matches

            scores[domain_id] = score

        # Find best match
        if not scores or all(v == 0 for v in scores.values()):
            # Return unknown/None for gibberish/no match - don't default to a domain
            return None, 0.0, {"reason": "No strong domain matches - input appears to be noise/gibberish"}

        best_domain = max(scores, key=scores.get)
        best_score = scores[best_domain]

        # Normalize confidence to 0-1 range (increased from 20 to 30 for heuristics)
        max_possible_score = 30.0
        confidence = min(1.0, best_score / max_possible_score)

        return best_domain, confidence, {
            "detected_domain": best_domain,
            "confidence": round(confidence, 3),
            "scores": {k: round(v, 2) for k, v in scores.items()},
            "reason": f"Detected {best_domain} with confidence {round(confidence*100, 1)}%"
        }

    def _extract_domain_terms(self, pack_data: Dict[str, Any]) -> set:
        """Extract all domain-specific terms from a domain pack."""
        terms = set()

        # Extract table names from schema
        if pack_data["schema"] and "tables" in pack_data["schema"]:
            for table_name, table_def in pack_data["schema"]["tables"].items():
                # Add table name in various forms
                terms.add(table_name)
                terms.add(table_name.replace("_", " "))

                # Add column names
                if "columns" in table_def:
                    for col_name in table_def["columns"].keys():
                        terms.add(col_name)
                        terms.add(col_name.replace("_", " "))

                        # Add business meanings as terms
                        col_data = table_def["columns"][col_name]
                        if "business_meaning" in col_data:
                            meaning = col_data["business_meaning"].lower()
                            # Extract key words (>3 chars)
                            for word in meaning.split():
                                if len(word) > 3:
                                    terms.add(word.rstrip(".,"))

        # Extract from taxonomy
        if pack_data["taxonomy"]:
            if "rule_categories" in pack_data["taxonomy"]:
                for cat in pack_data["taxonomy"]["rule_categories"]:
                    terms.add(cat.replace("_", " "))

            if "operations" in pack_data["taxonomy"]:
                for op in pack_data["taxonomy"]["operations"]:
                    terms.add(op)

        return terms


# Global detector instance
_detector = None


def get_domain_detector() -> DomainPackDetector:
    """Get or create the global domain pack detector."""
    global _detector
    if _detector is None:
        _detector = DomainPackDetector()
    return _detector


def detect_domain_pack(feedback_text: str) -> Tuple[Optional[str], float]:
    """
    Convenience function to detect domain pack from feedback.

    Returns:
        (domain_pack_id, confidence) - domain_pack_id is None if no match found
    """
    detector = get_domain_detector()
    domain_id, confidence, _ = detector.detect(feedback_text)
    return domain_id, confidence
