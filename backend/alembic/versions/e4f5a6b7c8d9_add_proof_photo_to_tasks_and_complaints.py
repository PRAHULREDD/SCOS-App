"""Add proof_photo_url to driver_tasks and complaints

Revision ID: e4f5a6b7c8d9
Revises: d2e3f4a5b6c7
Create Date: 2026-11-09 23:10:00.000000

Safe, reversible migration adding proof_photo_url column to:
1. driver_tasks
2. complaints
Preserves existing data and allows nullable string URLs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'driver_tasks' in tables:
        cols = [c['name'] for c in inspector.get_columns('driver_tasks')]
        if 'proof_photo_url' not in cols:
            op.add_column('driver_tasks', sa.Column('proof_photo_url', sa.String(), nullable=True))

    if 'complaints' in tables:
        cols = [c['name'] for c in inspector.get_columns('complaints')]
        if 'proof_photo_url' not in cols:
            op.add_column('complaints', sa.Column('proof_photo_url', sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'complaints' in tables:
        cols = [c['name'] for c in inspector.get_columns('complaints')]
        if 'proof_photo_url' in cols:
            op.drop_column('complaints', 'proof_photo_url')

    if 'driver_tasks' in tables:
        cols = [c['name'] for c in inspector.get_columns('driver_tasks')]
        if 'proof_photo_url' in cols:
            op.drop_column('driver_tasks', 'proof_photo_url')
