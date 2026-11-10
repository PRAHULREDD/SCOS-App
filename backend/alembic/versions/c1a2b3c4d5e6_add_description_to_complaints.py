"""Add description column to complaints table

Revision ID: c1a2b3c4d5e6
Revises: bfa2415d5970
Create Date: 2026-11-07 23:42:00.000000

Safe, reversible migration adding nullable description column to complaints.
Preserves all existing rows, columns, and test fixtures without data loss.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3c4d5e6'
down_revision: Union[str, None] = 'bfa2415d5970'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'complaints' in tables:
        columns = [col['name'] for col in inspector.get_columns('complaints')]
        if 'description' not in columns:
            op.add_column('complaints', sa.Column('description', sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'complaints' in tables:
        columns = [col['name'] for col in inspector.get_columns('complaints')]
        if 'description' in columns:
            op.drop_column('complaints', 'description')
