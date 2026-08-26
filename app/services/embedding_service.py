"""Embedding service for generating semantic vectors using Sentence-BERT."""

import json
from typing import List, Dict, Any, Optional
from uuid import uuid4
from datetime import datetime

try:
    from sentence_transformers import SentenceTransformer
    SBERT_AVAILABLE = True
except ImportError:
    SBERT_AVAILABLE = False


class EmbeddingService:
    """Generate Sentence-BERT embeddings for rules and store in database."""

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384

    def __init__(self, model_name: str = None):
        """Initialize embedding service with Sentence-BERT model."""
        self.model_name = model_name or self.MODEL_NAME
        self.model = None
        self._init_model()

    def _init_model(self) -> None:
        """Load the Sentence-BERT model (lazy loading)."""
        if not SBERT_AVAILABLE:
            print("Warning: sentence-transformers not available. Install with: pip install sentence-transformers")
            return

        try:
            self.model = SentenceTransformer(self.model_name)
        except Exception as e:
            print(f"Warning: Failed to load embedding model {self.model_name}: {e}")

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text string.

        Args:
            text: Text to embed

        Returns:
            List of floats (384-dimensional vector) or None if model unavailable
        """
        if self.model is None:
            print("Warning: Embedding model not initialized")
            return None

        try:
            # Generate embedding
            embedding = self.model.encode(text, convert_to_numpy=False)
            # Convert to list of floats
            return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None

    def generate_rule_embedding_text(self, rule: Dict[str, Any]) -> str:
        """
        Convert a rule dict into a text representation for embedding.

        This text captures the semantic meaning of the rule for similarity search.

        Args:
            rule: Rule dict with business_term, operation, conditions, etc.

        Returns:
            Text representation of the rule
        """
        parts = []

        # Business term (most important)
        if rule.get("business_term"):
            parts.append(f"Term: {rule['business_term']}")

        # Operation
        if rule.get("operation"):
            parts.append(f"Operation: {rule['operation']}")

        # Conditions
        conditions = rule.get("conditions", [])
        if conditions:
            condition_strs = []
            for cond in conditions:
                field = cond.get("field", "")
                operator = cond.get("operator", "")
                value = cond.get("value", "")
                condition_strs.append(f"{field} {operator} {value}")
            if condition_strs:
                parts.append(f"Conditions: {', '.join(condition_strs)}")

        # Scope
        if rule.get("scope"):
            scope = rule["scope"]
            scope_text = scope if isinstance(scope, str) else json.dumps(scope)
            parts.append(f"Scope: {scope_text}")

        # Time window
        if rule.get("time_window"):
            tw = rule["time_window"]
            tw_text = tw if isinstance(tw, str) else json.dumps(tw)
            parts.append(f"TimeWindow: {tw_text}")

        # Affected entities (tables)
        if rule.get("affected_entities"):
            entities = rule["affected_entities"]
            tables = entities.get("tables", []) if isinstance(entities, dict) else []
            if tables:
                parts.append(f"Tables: {', '.join(tables)}")

        return " ".join(parts)

    def generate_rule_embedding(
        self,
        rule: Dict[str, Any],
        db=None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate and optionally persist embedding for a rule.

        Args:
            rule: Rule dict with business_term, operation, conditions, etc.
            db: SQLAlchemy session (optional - if provided, persists to database)

        Returns:
            Dict with embedding_id, embedding (vector), metadata
        """
        # Generate text representation
        rule_text = self.generate_rule_embedding_text(rule)

        if not rule_text:
            print("Warning: Could not generate text representation for rule")
            return None

        # Generate embedding
        embedding = self.generate_embedding(rule_text)
        if embedding is None:
            print("Warning: Could not generate embedding")
            return None

        embedding_id = str(uuid4())

        result = {
            "embedding_id": embedding_id,
            "rule_id": rule.get("rule_id"),
            "workspace_id": rule.get("workspace_id"),
            "embedding": embedding,
            "embedding_model": self.model_name,
            "embedding_dimension": self.EMBEDDING_DIMENSION,
            "rule_text": rule_text,
            "created_at": datetime.utcnow(),
        }

        # Persist to database if session provided
        if db:
            try:
                from app.db.models.rule_embedding import RuleEmbedding

                rule_embedding = RuleEmbedding(
                    embedding_id=embedding_id,
                    rule_id=rule.get("rule_id"),
                    workspace_id=rule.get("workspace_id"),
                    embedding=embedding,
                    embedding_model=self.model_name,
                    embedding_dimension=self.EMBEDDING_DIMENSION,
                )
                db.add(rule_embedding)
                db.flush()
                result["persisted"] = True
            except Exception as e:
                print(f"Warning: Could not persist embedding to database: {e}")
                result["persisted"] = False
                result["db_error"] = str(e)

        return result

    def update_embedding(
        self,
        embedding_id: str,
        rule: Dict[str, Any],
        db=None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing embedding (e.g., when rule is modified).

        Args:
            embedding_id: ID of existing embedding to update
            rule: Updated rule dict
            db: SQLAlchemy session

        Returns:
            Updated embedding dict
        """
        # Generate new embedding
        embedding = self.generate_rule_embedding(rule, db=None)
        if embedding is None:
            return None

        embedding["embedding_id"] = embedding_id

        # Update in database if session provided
        if db:
            try:
                from app.db.models.rule_embedding import RuleEmbedding

                existing = db.query(RuleEmbedding).filter(
                    RuleEmbedding.embedding_id == embedding_id
                ).first()

                if existing:
                    existing.embedding = embedding["embedding"]
                    existing.updated_at = datetime.utcnow()
                    db.flush()
                    embedding["persisted"] = True
                else:
                    embedding["persisted"] = False
                    embedding["error"] = "Embedding not found"

            except Exception as e:
                embedding["persisted"] = False
                embedding["db_error"] = str(e)

        return embedding


# Global instance (lazy loading)
_embedding_service = None


def get_embedding_service(model_name: str = None) -> EmbeddingService:
    """Get or create global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(model_name)
    return _embedding_service
