from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class DomainPack(Base):
    __tablename__ = "domain_packs"

    domain_pack_id: Mapped[str] = mapped_column(
        "pack_id",
        String(50),
        primary_key=True,
    )

    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.workspace_id"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    schema_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    business_glossary: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    configuration: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    @property
    def pack_id(self) -> str:
        return self.domain_pack_id
