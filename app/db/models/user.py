"""User model for authentication (Spec §10.1).

A user is an authenticated identity that can be a member of one or more
workspaces. Passwords are stored only as a salted PBKDF2 hash (never plaintext);
role assignments live on the workspace_members table, not here, so a single user
can hold different roles in different workspaces.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    # PBKDF2-formatted hash string: "pbkdf2$sha256$<iterations>$<salt_hex>$<hash_hex>"
    password_hash: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )