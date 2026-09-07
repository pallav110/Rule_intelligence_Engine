"""Business glossary integration for rule extraction.

Loads and uses domain pack business glossary to disambiguate business terms
and improve rule extraction accuracy.
"""

import json
import re
from typing import Dict, Any, List, Set, Tuple
from pathlib import Path


class GlossaryService:
    """Load and use business glossary for term disambiguation."""

    def __init__(self):
        """Initialize glossary service."""
        self.glossaries: Dict[str, Dict[str, Any]] = {}

    def load_glossary_from_file(self, glossary_path: Path) -> Dict[str, Any]:
        """Load glossary from markdown file."""
        try:
            with open(glossary_path, 'r') as f:
                content = f.read()

            glossary = {}
            # Parse markdown glossary format: ### Term\n(definition block until next ### or end)
            # Capture everything from ### Term through all bullet points until the next ### or EOF
            pattern = r'^###\s+([^\n]+)\n((?:(?!^###)[\s\S])*?)(?=^###|\Z)'
            matches = re.finditer(pattern, content, re.MULTILINE)

            for match in matches:
                term = match.group(1).strip()
                definition = match.group(2).strip()
                glossary[term.lower()] = {
                    "term": term,
                    "definition": definition  # Full definition block with Tables/columns line
                }

            return glossary
        except Exception as e:
            print(f"Error loading glossary from {glossary_path}: {e}")
            return {}

    def load_glossary_for_domain(self, domain_pack_id: str) -> Dict[str, Any]:
        """Load glossary for a specific domain pack."""
        if not domain_pack_id:
            return {}

        if domain_pack_id in self.glossaries:
            return self.glossaries[domain_pack_id]

        glossary_path = (
            Path(__file__).parent.parent.parent /
            "rie_ml" / "domain-packs" / domain_pack_id /
            "documentation" / "business_glossary.md"
        )

        glossary = self.load_glossary_from_file(glossary_path)
        self.glossaries[domain_pack_id] = glossary
        return glossary

    def extract_glossary_terms(
        self, feedback_text: str, domain_pack_id: str
    ) -> List[Dict[str, Any]]:
        """Extract glossary terms found in feedback text with flexible matching."""
        glossary = self.load_glossary_for_domain(domain_pack_id)
        if not glossary:
            return []

        feedback_lower = feedback_text.lower()
        found_terms = {}  # Use dict to track best match per term

        for term_key, term_data in glossary.items():
            best_match_count = 0
            first_pos = len(feedback_lower)

            # Exact match
            if term_key in feedback_lower:
                best_match_count = len(term_key.split('_'))  # All parts matched
                first_pos = feedback_lower.find(term_key)
            else:
                # Try matching individual words from snake_case terms
                # e.g., "ticket_backlog" → search for "ticket" and "backlog"
                term_parts = term_key.split('_')
                matched_parts = 0

                for part in term_parts:
                    if len(part) > 2 and f" {part} " in f" {feedback_lower} ":
                        matched_parts += 1
                        pos = feedback_lower.find(part)
                        if pos >= 0:
                            first_pos = min(first_pos, pos)

                best_match_count = matched_parts

            # Store if this is a good match (matched at least one meaningful part)
            if best_match_count > 0:
                term_key_lower = term_key.lower()
                if term_key_lower not in found_terms or best_match_count > found_terms[term_key_lower][0]:
                    found_terms[term_key_lower] = (best_match_count, first_pos, term_key, term_data)

        # Convert to list and sort by quality (more parts matched, then by LATEST position for specificity)
        result = []
        for key, (match_count, pos, term_key, term_data) in found_terms.items():
            result.append({
                "term": term_data["term"],
                "definition": term_data["definition"],
                "key": term_key,
                "position": pos,
                "match_quality": match_count
            })

        # Sort by match quality (descending) then position (descending - later terms are more specific)
        result.sort(key=lambda x: (-x["match_quality"], -x["position"]))
        return result

    def disambiguate_term(
        self, ambiguous_term: str, context: str, domain_pack_id: str
    ) -> Tuple[str, str, float]:
        """
        Disambiguate a business term using glossary and context.

        Returns:
            (canonical_term, definition, confidence)
        """
        glossary = self.load_glossary_for_domain(domain_pack_id)
        term_lower = ambiguous_term.lower()

        if term_lower in glossary:
            return (
                glossary[term_lower]["term"],
                glossary[term_lower]["definition"],
                0.95
            )

        # Try fuzzy matching if exact match not found
        context_lower = context.lower()
        best_match = None
        best_score = 0.0

        for gloss_term, gloss_data in glossary.items():
            # Check if glossary term appears in context
            if gloss_term in context_lower:
                # Higher score if term is close to ambiguous term
                score = self._similarity_score(term_lower, gloss_term)
                if score > best_score:
                    best_score = score
                    best_match = (
                        gloss_data["term"],
                        gloss_data["definition"],
                        score
                    )

        if best_match:
            return best_match

        return (ambiguous_term, "Not found in glossary", 0.0)

    def enrich_extraction_with_glossary(
        self,
        extracted_rule: Dict[str, Any],
        feedback_text: str,
        domain_pack_id: str
    ) -> Dict[str, Any]:
        """
        Enrich extracted rule with glossary definitions.

        Adds glossary_definitions field to extracted rule.
        """
        glossary = self.load_glossary_for_domain(domain_pack_id)
        if not glossary:
            return extracted_rule

        glossary_definitions = {}

        # Extract glossary terms from rule
        if extracted_rule.get("business_term"):
            term = extracted_rule["business_term"].lower()
            if term in glossary:
                glossary_definitions["business_term"] = glossary[term]["definition"]

        # Extract from conditions
        if extracted_rule.get("conditions"):
            for condition in extracted_rule["conditions"]:
                value = str(condition.get("value", "")).lower()
                if value in glossary:
                    glossary_definitions[f"condition_value:{value}"] = glossary[value]["definition"]

        extracted_rule["glossary_definitions"] = glossary_definitions
        return extracted_rule

    def _similarity_score(self, term1: str, term2: str) -> float:
        """Simple similarity score between two terms."""
        if term1 == term2:
            return 1.0

        common = len(set(term1) & set(term2))
        total = max(len(term1), len(term2))
        return common / total if total > 0 else 0.0

    def get_glossary_summary(self, domain_pack_id: str) -> Dict[str, int]:
        """Get summary stats for domain glossary."""
        glossary = self.load_glossary_for_domain(domain_pack_id)
        return {
            "total_terms": len(glossary),
            "domain": domain_pack_id

        }


# Global glossary service instance
_glossary_service = None


def get_glossary_service() -> GlossaryService:
    """Get or create global glossary service."""
    global _glossary_service
    if _glossary_service is None:
        _glossary_service = GlossaryService()
    return _glossary_service
