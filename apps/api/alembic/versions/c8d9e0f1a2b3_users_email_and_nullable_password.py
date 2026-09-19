"""allow OAuth2-only user accounts: nullable password_hash, add email

Revision ID: c8d9e0f1a2b3
Revises: b7c1d2e3f4a5
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, None] = 'b7c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A Google/GitHub-only account (editor_common.users.get_or_create_oauth_user)
    # has no password to hash — see editor_common.users.UserMixin's docstring.
    # batch_alter_table (rather than a bare op.alter_column) so this also
    # works against SQLite, which has no native ALTER COLUMN and needs the
    # table recreated — CI's migration round-trip check runs against
    # SQLite even though every real deployment uses Postgres.
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('password_hash', existing_type=sa.String(length=255), nullable=True)
    op.add_column('users', sa.Column('email', sa.String(length=255), nullable=True))
    op.create_index('ix_users_email', 'users', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_email', table_name='users')
    op.drop_column('users', 'email')
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('password_hash', existing_type=sa.String(length=255), nullable=False)
