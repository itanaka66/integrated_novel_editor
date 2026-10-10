"""add source_project_id to projects

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Which work a translated project was made from, so a later translation
    # can fill in only what is missing.
    op.add_column('projects', sa.Column('source_project_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'source_project_id')
