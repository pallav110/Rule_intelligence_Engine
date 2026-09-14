"""Workspace membership model (Spec §10.1 RBAC + §10.2).

Links a user to a workspace with exactly one role. This is the entity that the
authenticated workspace check validates: a user may perform an operation inside
a workspace only if a row here exists for (workspace_id, user_id) and the user's
role grants that operation (see app/services/security.py:ROLE_LEVEL).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        # One role per user per workspace.
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member_workspace_user"),
    )

    membership_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.workspace_id"),
        nullable=False,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
    )

    # business_user | reviewer | administrator  (Spec §10.1)
    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )