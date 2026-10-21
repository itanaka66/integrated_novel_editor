"""add chapter to episodes

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The chapter (章) an episode belongs to; empty = no chapter.
    op.add_column('episodes', sa.Column('chapter', sa.String(length=300), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('episodes', 'chapter')
