"""Initial migration — create all SCOS tables

Revision ID: bfa2415d5970
Revises:
Create Date: 2026-06-04 13:57:48.893299

NOTE: The original auto-generated migration was a no-op (empty pass).
The application relied on SQLAlchemy create_all() at startup.
This migration now explicitly creates every table so that the schema
can be reproduced from an empty database via `alembic upgrade head`
without needing the application's startup hook.

It is safe to run against an existing database: all CREATE TABLE
statements use IF NOT EXISTS semantics via Alembic's checkfirst=True.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'bfa2415d5970'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()

    if 'users' not in existing:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(), nullable=True),
            sa.Column('email', sa.String(), nullable=True, unique=True, index=True),
            sa.Column('password_hash', sa.String(), nullable=True),
            sa.Column('role', sa.String(), nullable=True),
            sa.Column('eco_points', sa.Integer(), server_default='0', nullable=True),
        )

    if 'complaints' not in existing:
        op.create_table(
            'complaints',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('citizen_id', sa.Integer(), nullable=True),
            sa.Column('zone', sa.String(), nullable=True),
            sa.Column('area', sa.String(), nullable=True),
            sa.Column('waste_type', sa.String(), nullable=True),
            sa.Column('severity_level', sa.String(), nullable=True),
            sa.Column('status', sa.String(), server_default='PENDING', nullable=True),
            sa.Column('lat', sa.Float(), nullable=True),
            sa.Column('lng', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )

    if 'driver_locations' not in existing:
        op.create_table(
            'driver_locations',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('driver_id', sa.Integer(), nullable=True),
            sa.Column('lat', sa.Float(), nullable=True),
            sa.Column('lng', sa.Float(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )

    if 'rewards' not in existing:
        op.create_table(
            'rewards',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('title', sa.String(), nullable=True),
            sa.Column('provider', sa.String(), nullable=True),
            sa.Column('category', sa.String(), nullable=True),
            sa.Column('points_cost', sa.Integer(), nullable=True),
            sa.Column('image_url', sa.String(), nullable=True),
            sa.Column('is_active', sa.Integer(), server_default='1', nullable=True),
        )

    if 'reward_redemptions' not in existing:
        op.create_table(
            'reward_redemptions',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('reward_id', sa.Integer(), nullable=True),
            sa.Column('redeemed_at', sa.DateTime(), nullable=True),
        )

    if 'driver_tasks' not in existing:
        op.create_table(
            'driver_tasks',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('driver_id', sa.Integer(), nullable=True),
            sa.Column('complaint_id', sa.Integer(), nullable=True),
            sa.Column('priority', sa.String(), server_default='MEDIUM', nullable=True),
            sa.Column('waste_type', sa.String(), nullable=True),
            sa.Column('address', sa.String(), nullable=True),
            sa.Column('bin_fill_percent', sa.Integer(), server_default='50', nullable=True),
            sa.Column('distance_km', sa.Float(), server_default='0', nullable=True),
            sa.Column('status', sa.String(), server_default='ASSIGNED', nullable=True),
            sa.Column('assigned_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
        )

    if 'dumping_incidents' not in existing:
        op.create_table(
            'dumping_incidents',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('zone', sa.String(), nullable=True),
            sa.Column('cluster_id', sa.String(), nullable=True),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('severity', sa.String(), server_default='MEDIUM', nullable=True),
            sa.Column('predicted_culprit', sa.String(), nullable=True),
            sa.Column('common_time', sa.String(), nullable=True),
            sa.Column('confidence', sa.Float(), server_default='0', nullable=True),
            sa.Column('lat', sa.Float(), nullable=True),
            sa.Column('lng', sa.Float(), nullable=True),
            sa.Column('status', sa.String(), server_default='ACTIVE', nullable=True),
            sa.Column('detected_at', sa.DateTime(), nullable=True),
            sa.Column('dispatched_at', sa.DateTime(), nullable=True),
        )

    if 'contractors' not in existing:
        op.create_table(
            'contractors',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(), nullable=True),
            sa.Column('completion_rate', sa.Float(), server_default='0', nullable=True),
            sa.Column('satisfaction_score', sa.Float(), server_default='0', nullable=True),
            sa.Column('response_time_hours', sa.Float(), server_default='0', nullable=True),
            sa.Column('active_drivers', sa.Integer(), server_default='0', nullable=True),
        )


def downgrade() -> None:
    # Drop in reverse dependency order
    for table in [
        'contractors', 'dumping_incidents', 'driver_tasks',
        'reward_redemptions', 'rewards', 'driver_locations',
        'complaints', 'users',
    ]:
        op.drop_table(table)
