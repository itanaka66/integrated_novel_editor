"""add language to projects

Revision ID: e5f6a7b8c9d0
Revises: c8d9e0f1a2b3
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'c8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('language', sa.String(length=10), nullable=False, server_default='ja'))


def downgrade() -> None:
    op.drop_column('projects', 'language')
