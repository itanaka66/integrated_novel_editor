"""add translator ollama url/model to runtime_config

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL = translate with the Controller's server/model (the previous behaviour).
    op.add_column('runtime_config', sa.Column('translator_ollama_url', sa.String(length=500), nullable=True))
    op.add_column('runtime_config', sa.Column('translator_ollama_model', sa.String(length=150), nullable=True))


def downgrade() -> None:
    op.drop_column('runtime_config', 'translator_ollama_model')
    op.drop_column('runtime_config', 'translator_ollama_url')
