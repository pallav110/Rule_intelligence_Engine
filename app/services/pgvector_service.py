"""pgvector service for semantic similarity search on rules."""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text, literal_column
from sqlalchemy.sql import bindparam


class PgvectorService:
    """Semantic similarity search using pgvector and cosine distance."""

    # Similarity thresholds
    VERY_HIGH_SIMILARITY = 0.90  # Likely exact/semantic duplicate
    HIGH_SIMILARITY = 0.75  # Possible modification/extension
    MEDIUM_SIMILARITY = 0.60  # Potential conflict
    LOW_SIMILARITY = 0.40  # Distant relationship

    def __init__(self):
        """Initialize pgvector service."""
        self.enabled = self._check_pgvector_enabled()

    def _check_pgvector_enabled(self) -> bool:
        """Check if pgvector extension is available in PostgreSQL."""
        # This will be verified during initialization
        # For now, assume it will be enabled during setup
        return True

    def retrieve_similar_rules(
        self,
        embedding: List[float],
        workspace_id: str,
        domain_id: str = None,
        top_k: int = 10,
        similarity_threshold: float = None,
        db=None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve Top-K most similar rules using cosine similarity.

        This is the core semantic retrieval step for duplicate and conflict detection.
        It pre-filters candidates BEFORE detailed structural comparison.

        Args:
            embedding: 384-dimensional Sentence-BERT vector
            workspace_id: Workspace to search in
            domain_id: Optional domain filter
            top_k: Number of similar rules to return (default 10)
            similarity_threshold: Only return rules above this similarity (0.0-1.0)
            db: SQLAlchemy session

        Returns:
            List of dicts:
            [
                {
                    "rule_id": "R123",
                    "similarity_score": 0.92,
                    "business_term": "Revenue",
                    "operation": "exclude",
                    "scope": "global",
                    ...
                },
                ...
            ]
        """
        if not db:
            return []

        if not embedding or len(embedding) == 0:
            return []

        try:
            # Convert embedding to pgvector string format
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

            # Use a SEPARATE psycopg2 connection to avoid corrupting the main transaction
            # If pgvector query fails, it won't rollback the main SQLAlchemy session
            import psycopg2
            from app.db.database import DATABASE_URL

            separate_conn = psycopg2.connect(DATABASE_URL)
            cursor = separate_conn.cursor()

            query = """
                SELECT r.rule_id, r.business_term, r.operation, r.scope, r.conditions,
                       r.affected_entities, r.threshold, r.time_window, r.status,
                       (1.0 - (re.embedding <=> %s::vector)) as similarity_score
                FROM rule_embeddings re
                JOIN rules r ON re.rule_id = r.rule_id
                WHERE re.workspace_id = %s AND r.status IN ('active', 'draft')
            """
            params = [embedding_str, workspace_id]

            if domain_id:
                query += " AND r.domain_id = %s"
                params.append(domain_id)

            if similarity_threshold is not None:
                query += " AND (1.0 - (re.embedding <=> %s::vector)) >= %s"
                params.append(embedding_str)
                params.append(similarity_threshold)

            query += " ORDER BY similarity_score DESC LIMIT %s"
            params.append(top_k)

            # Execute via separate psycopg2 cursor
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            separate_conn.close()

            # Convert rows to dicts
            candidates = []
            for row in rows:
                candidates.append({
                    "rule_id": row[0],
                    "business_term": row[1],
                    "operation": row[2],
                    "scope": row[3],
                    "conditions": row[4],
                    "affected_entities": row[5],
                    "threshold": row[6],
                    "time_window": row[7],
                    "status": row[8],
                    "similarity_score": round(float(row[9]), 3),
                })

            return candidates

        except Exception as e:
            print(f"Error retrieving similar rules: {e}")
            return []

    def get_most_similar_rule(
        self,
        embedding: List[float],
        workspace_id: str,
        domain_id: str = None,
        db=None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the single most similar rule.

        Shortcut for retrieving Top-1.

        Args:
            embedding: 384-dimensional Sentence-BERT vector
            workspace_id: Workspace to search in
            domain_id: Optional domain filter
            db: SQLAlchemy session

        Returns:
            Dict with rule_id, similarity_score, and rule details, or None
        """
        candidates = self.retrieve_similar_rules(
            embedding=embedding,
            workspace_id=workspace_id,
            domain_id=domain_id,
            top_k=1,
            db=db,
        )
        return candidates[0] if candidates else None

    def similarity_to_confidence(self, similarity_score: float) -> str:
        """
        Convert similarity score to human-readable confidence level.

        Args:
            similarity_score: Float 0.0-1.0

        Returns:
            "very_high" | "high" | "medium" | "low" | "very_low"
        """
        if similarity_score >= self.VERY_HIGH_SIMILARITY:
            return "very_high"
        elif similarity_score >= self.HIGH_SIMILARITY:
            return "high"
        elif similarity_score >= self.MEDIUM_SIMILARITY:
            return "medium"
        elif similarity_score >= self.LOW_SIMILARITY:
            return "low"
        else:
            return "very_low"

    def batch_retrieve_similar_rules(
        self,
        embeddings_list: List[Tuple[str, List[float]]],
        workspace_id: str,
        domain_id: str = None,
        top_k: int = 10,
        db=None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve similar rules for multiple embeddings in one batch.

        Useful for bulk duplicate/conflict detection.

        Args:
            embeddings_list: List of (rule_id, embedding) tuples
            workspace_id: Workspace to search in
            domain_id: Optional domain filter
            top_k: Number of similar rules per query
            db: SQLAlchemy session

        Returns:
            Dict mapping rule_id → list of similar rules
        """
        results = {}
        for rule_id, embedding in embeddings_list:
            similar = self.retrieve_similar_rules(
                embedding=embedding,
                workspace_id=workspace_id,
                domain_id=domain_id,
                top_k=top_k,
                db=db,
            )
            results[rule_id] = similar

        return results


# Global instance
_pgvector_service = None


def get_pgvector_service() -> PgvectorService:
    """Get or create global pgvector service instance."""
    global _pgvector_service
    if _pgvector_service is None:
        _pgvector_service = PgvectorService()
    return _pgvector_service
