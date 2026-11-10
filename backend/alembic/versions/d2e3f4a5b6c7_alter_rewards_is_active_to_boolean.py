"""Alter rewards.is_active from Integer to Boolean

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3c4d5e6
Create Date: 2026-11-09 12:30:00.000000

Forward migration resolving schema drift for rewards.is_active:
- Migrates column type from Integer to Boolean.
- Preserves existing values: 1 -> True, 0 -> False.
- Explicit NULL handling: existing NULL values are converted to True (active by default).
- Safe for both PostgreSQL (using CASE WHEN) and SQLite (batch mode with NULL update).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'c1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'rewards' not in tables:
        return

    dialect = bind.dialect.name

    if dialect == 'sqlite':
        # Explicit NULL handling: normalize NULL to 1 (True) before alteration
        op.execute(sa.text("UPDATE rewards SET is_active = 1 WHERE is_active IS NULL"))
        with op.batch_alter_table('rewards') as batch_op:
            batch_op.alter_column(
                'is_active',
                existing_type=sa.Integer(),
                type_=sa.Boolean(),
                existing_nullable=True,
                nullable=True,
                server_default=sa.text('1')
            )
    elif dialect == 'postgresql':
        # Drop existing integer default to prevent DatatypeMismatchError when altering type
        op.execute(sa.text("ALTER TABLE rewards ALTER COLUMN is_active DROP DEFAULT"))
        # PostgreSQL supports USING clause with explicit NULL handling
        op.alter_column(
            'rewards',
            'is_active',
            existing_type=sa.Integer(),
            type_=sa.Boolean(),
            postgresql_using="CASE WHEN is_active = 0 THEN FALSE WHEN is_active IS NULL THEN TRUE ELSE TRUE END",
            existing_nullable=True,
            nullable=True,
            server_default=sa.text('true')
        )
    else:
        # Generic fallback for other dialects
        op.execute(sa.text("UPDATE rewards SET is_active = 1 WHERE is_active IS NULL"))
        op.alter_column(
            'rewards',
            'is_active',
            existing_type=sa.Integer(),
            type_=sa.Boolean(),
            existing_nullable=True,
            nullable=True
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'rewards' not in tables:
        return

    dialect = bind.dialect.name

    if dialect == 'sqlite':
        with op.batch_alter_table('rewards') as batch_op:
            batch_op.alter_column(
                'is_active',
                existing_type=sa.Boolean(),
                type_=sa.Integer(),
                existing_nullable=True,
                nullable=True,
                server_default=sa.text('1')
            )
    elif dialect == 'postgresql':
        # Drop existing boolean default to prevent DatatypeMismatchError when altering type back to integer
        op.execute(sa.text("ALTER TABLE rewards ALTER COLUMN is_active DROP DEFAULT"))
        op.alter_column(
            'rewards',
            'is_active',
            existing_type=sa.Boolean(),
            type_=sa.Integer(),
            postgresql_using="CASE WHEN is_active IS FALSE THEN 0 ELSE 1 END",
            existing_nullable=True,
            nullable=True,
            server_default=sa.text('1')
        )
    else:
        op.alter_column(
            'rewards',
            'is_active',
            existing_type=sa.Boolean(),
            type_=sa.Integer(),
            existing_nullable=True,
            nullable=True
        )
