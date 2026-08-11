from sqlalchemy import JSON, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class Rule(Base):
    __tablename__ = "rules"

    rule_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.workspace_id"),
        nullable=False
    )

    rule_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    operation: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    conditions: Mapped[list] = mapped_column(
        JSON,
        nullable=False
    )

    affected_tables: Mapped[list] = mapped_column(
        JSON,
        nullable=False
    )

    affected_columns: Mapped[list] = mapped_column(
        JSON,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft"
    )