"""add translator_pool to runtime_config

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-10-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # JSON list of {"url", "model"}: the translation LLMs. NULL = just the single
    # translator setting (which itself defaults to the Controller).
    op.add_column('runtime_config', sa.Column('translator_pool', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('runtime_config', 'translator_pool')
