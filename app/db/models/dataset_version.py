from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


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

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
