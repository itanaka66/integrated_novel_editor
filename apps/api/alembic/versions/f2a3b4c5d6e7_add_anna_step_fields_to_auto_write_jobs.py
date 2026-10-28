"""add Anna step fields to auto_write_jobs

Revision ID: f2a3b4c5d6e7
Revises: e0f1a2b3c4d5
Create Date: 2026-10-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e0f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pending_step_id: UUID of the current outstanding step (for idempotent submission)
    op.add_column('auto_write_jobs', sa.Column('pending_step_id', sa.String(100), nullable=True))
    # current_write_context: JSON blob storing in-progress episode write state between sub-phases
    op.add_column('auto_write_jobs', sa.Column('current_write_context', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('auto_write_jobs', 'current_write_context')
    op.drop_column('auto_write_jobs', 'pending_step_id')
