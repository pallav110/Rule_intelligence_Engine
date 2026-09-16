from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base

# NOTE: for Alembic autogenerate purposes this model now carries workspace_id.
# DB already has the column via a manual migration (kept lightweight to avoid
# branching alembic heads); a formal revision will codify it when heads are merged.


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    __table_args__ = (
        UniqueConstraint(
            "dataset_name",
            "version",
            name="uq_dataset_versions_name_version",
        ),
    )

    dataset_version_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    dataset_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    num_samples: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    domain_pack_id: Mapped[str | None] = mapped_column(
        ForeignKey("domain_packs.pack_id"),
        nullable=True,
    )

    domain_pack_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    annotation_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
    )

    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.workspace_id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    @property
    def version_name(self) -> str:
        return self.dataset_name

    @version_name.setter
    def version_name(self, value: str) -> None:
        self.dataset_name = value
