"""
Unified ML Model Service - Loads ACTIVE models from registry with baseline fallback.

This service integrates with the model_version table (Spec 8.11) to automatically
use the best available model for each task:
- Classification: DistilBERT if ACTIVE, else TF-IDF baseline
- Rule Extraction: DistilBERT token classifier if ACTIVE, else regex baseline

Per Spec 8.11 Model Registry: Models progress CANDIDATE → APPROVED → ACTIVE
The ACTIVE model is used for production inference without code changes.
"""

import torch
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MLModelService:
    """Unified service for loading and using ACTIVE ML models from registry."""

    def __init__(self, db=None):
        """
        Initialize ML model service.

        Args:
            db: Database session for querying model_version table.
                If None, will fallback to baseline without ML.
        """
        self.db = db
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self._classifier_cache = None
        self._extractor_cache = None

    def get_active_model(self, model_type: str) -> Optional[Dict[str, Any]]:
        """
        Get ACTIVE model from registry for given model_type.

        Args:
            model_type: One of "classification", "rule-extraction"

        Returns:
            Model version dict if found, None otherwise
        """
        if self.db is None:
            return None

        try:
            from app.services.model_version_service import ModelVersionService
            service = ModelVersionService()
            active = service.get_active_model(self.db, model_type)
            if active:
                return {
                    "model_version_id": active.model_version_id,
                    "model_name": active.model_name,
                    "model_type": active.model_type,
                    "version": active.version,
                    "checkpoint_path": active.checkpoint_path,
                    "status": active.status,
                    "evaluation_metrics": active.evaluation_metrics,
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to query active model for {model_type}: {e}")
            return None

    def _resolve_checkpoint_path(self, checkpoint_path: str) -> Optional[Path]:
        """
        Resolve checkpoint path, handling both absolute and relative paths.

        The DB may store paths like "/models/distilbert-classifier" but
        actual checkpoints are at "rie_ml/models/distilbert_candidate/checkpoints/best_model.pt"

        Returns:
            Resolved Path if exists, None otherwise
        """
        # Direct path check
        direct = Path(checkpoint_path)
        if direct.exists() and direct.is_file():
            return direct
        if direct.exists() and direct.is_dir():
            # Check for best_model.pt inside directory
            candidate = direct / "checkpoints" / "best_model.pt"
            if candidate.exists():
                return candidate
            candidate = direct / "best_model.pt"
            if candidate.exists():
                return candidate

        # Known mappings for this project
        known_paths = {
            "/models/distilbert-classifier": Path(__file__).parent.parent.parent / "rie_ml" / "models" / "distilbert_candidate" / "checkpoints" / "best_model.pt",
            "/models/distilbert-extractor": Path(__file__).parent.parent.parent / "rie_ml" / "models" / "distilbert_token_extractor" / "checkpoints" / "best_model.pt",
            "distilbert-classifier": Path(__file__).parent.parent.parent / "rie_ml" / "models" / "distilbert_candidate" / "checkpoints" / "best_model.pt",
            "distilbert-extractor": Path(__file__).parent.parent.parent / "rie_ml" / "models" / "distilbert_token_extractor" / "checkpoints" / "best_model.pt",
        }

        if checkpoint_path in known_paths:
            resolved = known_paths[checkpoint_path]
            if resolved.exists():
                return resolved

        # Also try interpreting as model_name lookup
        for key, path in known_paths.items():
            if path.exists() and checkpoint_path in key:
                return path

        return None

    def classify(self, feedback: str, domain: str = None) -> Dict[str, Any]:
        """
        Classify feedback using best available model.

        Tries: DistilBERT (if ACTIVE in registry) → TF-IDF baseline → regex fallback

        Args:
            feedback: Text to classify
            domain: Domain for baseline fallback

        Returns:
            Classification result with model info
        """
        # Try DistilBERT if ACTIVE model exists
        active = self.get_active_model("classification")
        if active:
            checkpoint = self._resolve_checkpoint_path(active["checkpoint_path"])
            if checkpoint and checkpoint.exists():
                result = self._classify_with_distilbert(feedback, checkpoint)
                if result.get("model") == "distilbert" and result.get("confidence", 0) > 0:
                    result["model_version_id"] = active["model_version_id"]
                    result["model_version"] = active["version"]
                    result["registry_status"] = "active_ml"
                    return result
                logger.warning(f"DistilBERT classification failed, falling back to baseline: {result.get('error')}")

        # Fallback to baseline
        from app.services.classifier import RealClassifier
        classifier = RealClassifier(domain=domain or "ecommerce")
        result = classifier.classify(feedback)
        result["model_version_id"] = active["model_version_id"] if active else None
        result["registry_status"] = "baseline_fallback" if active else "no_active_model"
        result["model"] = "baseline"
        return result

    def extract(self, feedback: str, schema_context: Dict = None) -> Dict[str, Any]:
        """
        Extract rules using best available model.

        Tries: DistilBERT token classifier (if ACTIVE) → Enhanced regex baseline

        Args:
            feedback: Text to extract from
            schema_context: Domain/schema context for enrichment

        Returns:
            Extraction result with model info
        """
        # Try DistilBERT if ACTIVE model exists
        active = self.get_active_model("rule-extraction")
        if active:
            checkpoint = self._resolve_checkpoint_path(active["checkpoint_path"])
            if checkpoint and checkpoint.exists():
                result = self._extract_with_distilbert(feedback, checkpoint, schema_context)
                if result.get("model") == "distilbert_token_classifier" and not result.get("error"):
                    # Check if extraction actually produced rules.
                    # A valid rule requires at least an operation OR a business_term.
                    # Rules with only conditions and no operation are too partial to use.
                    rules = result.get("extraction", {}).get("extracted_rules", [])
                    if rules and (rules[0].get("business_term") or rules[0].get("operation")):
                        result["model_version_id"] = active["model_version_id"]
                        result["model_version"] = active["version"]
                        result["registry_status"] = "active_ml"
                        return result
                logger.warning(f"DistilBERT extraction produced no rules, falling back to baseline")

        # Fallback to baseline
        from app.services.enhanced_rule_extractor import EnhancedRuleExtractor
        extractor = EnhancedRuleExtractor()
        result = extractor.extract(feedback, schema_context)
        result["model_version_id"] = active["model_version_id"] if active else None
        result["registry_status"] = "baseline_fallback" if active else "no_active_model"
        # Normalize model field
        if "model" not in result:
            result["model"] = "baseline"
        return result

    def _classify_with_distilbert(self, feedback: str, checkpoint_path: Path) -> Dict[str, Any]:
        """Classify using DistilBERT checkpoint directly."""
        try:
            from app.services.distilbert_classifier import get_distilbert_classifier
            # Use the global singleton which is already loaded
            classifier = get_distilbert_classifier()
            if not classifier.model_ready:
                return {"error": "DistilBERT model not ready", "confidence": 0}
            return classifier.classify(feedback)
        except Exception as e:
            logger.error(f"DistilBERT classification error: {e}")
            return {"error": str(e), "confidence": 0}

    def _extract_with_distilbert(self, feedback: str, checkpoint_path: Path, schema_context: Dict = None) -> Dict[str, Any]:
        """Extract using DistilBERT token classifier checkpoint directly."""
        try:
            from app.services.distilbert_token_extractor import get_distilbert_token_extractor
            extractor = get_distilbert_token_extractor()
            if not extractor.model_ready:
                return {"error": "DistilBERT extractor not ready"}
            # Pass schema_context to extractor for Rule Construction (Spec 8.4)
            result = extractor.extract(feedback, schema_context)

            # Enrich with domain info if available
            if schema_context and result.get("extraction", {}).get("extracted_rules"):
                domain_id = schema_context.get("domain_pack_id", "ecommerce")
                from app.services.domain_pack_matcher import DomainPackMatcher
                try:
                    matcher = DomainPackMatcher()
                    rules = result["extraction"]["extracted_rules"]
                    matching = matcher.match_extracted_rules(rules, domain_id)
                    enriched = matcher.enrich_with_schema_details(rules, domain_id)
                    taxonomy = matcher.validate_against_taxonomy(rules, domain_id)

                    result["extraction"]["extracted_rules"] = enriched
                    result["domain_pack_matching"] = matching
                    result["taxonomy_validation"] = taxonomy
                except Exception as enrich_e:
                    logger.warning(f"Domain enrichment failed: {enrich_e}")

            # Normalize result shape to match baseline so the pipeline consumes
            # both uniformly (main.py reads rule_count, rules, evidence, etc.)
            if "extraction" in result:
                extracted_rules = result["extraction"].get("extracted_rules", [])
                overall = result.get("overall_confidence", 0.95)
                result["extraction"].setdefault("candidate_rules", [])
                result["extraction"]["rules"] = extracted_rules[:1] if extracted_rules else []
                if not result["extraction"].get("confidence"):
                    result["extraction"]["confidence"] = {
                        "business_term": overall,
                        "operation": overall,
                        "conditions": overall,
                        "scope": overall,
                        "affected_entities": overall,
                    }
                if "rule_count" not in result:
                    result["rule_count"] = {"extracted": len(extracted_rules), "candidates": 0}
                if "extraction_confidence" not in result:
                    result["extraction_confidence"] = overall
                if "evidence" not in result:
                    result["evidence"] = ""

            return result
        except Exception as e:
            logger.error(f"DistilBERT extraction error: {e}")
            return {"error": str(e)}
