"""merge divergent heads

Revision ID: fb5bdc75776b
Revises: 589fc4686c71, 20260904_enhance_model_versions_spec811, add_execution_timestamps
Create Date: 2026-09-07 16:00:42.018004

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb5bdc75776b'
down_revision: Union[str, Sequence[str], None] = ('589fc4686c71', '20260904_enhance_model_versions_spec811', 'add_execution_timestamps')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
