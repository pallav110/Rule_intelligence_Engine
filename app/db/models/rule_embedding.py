"""Rule embeddings for semantic similarity search using pgvector."""

from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models.workspace import Base

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    # Fallback for environments without pgvector
    Vector = lambda dimensions: String(4096)


class RuleEmbedding(Base):
    """Stores semantic embeddings (vectors) for business rules for similarity search."""

    __tablename__ = "rule_embeddings"

    embedding_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    rule_id: Mapped[str] = mapped_column(
        ForeignKey("rules.rule_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 384-dimensional Sentence-BERT embedding (all-MiniLM-L6-v2)
    embedding: Mapped[object] = mapped_column(
        Vector(384) if PGVECTOR_AVAILABLE else String(4096),
        nullable=False,
    )

    embedding_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="sentence-transformers/all-MiniLM-L6-v2",
    )

    embedding_dimension: Mapped[int] = mapped_column(
        nullable=False,
        default=384,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
