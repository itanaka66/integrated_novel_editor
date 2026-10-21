"""add premise and overwrite to auto_write_jobs

Revision ID: e0f1a2b3c4d5
Revises: d0e1f2a3b4c5
Create Date: 2026-10-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0f1a2b3c4d5'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('auto_write_jobs', sa.Column('premise', sa.Text(), nullable=False, server_default=''))
    op.add_column('auto_write_jobs', sa.Column('overwrite', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('auto_write_jobs', 'overwrite')
    op.drop_column('auto_write_jobs', 'premise')
