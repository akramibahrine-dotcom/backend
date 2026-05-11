"""Add customer_address to orders

Revision ID: 002
Revises: 001
Create Date: 2026-05-11

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("customer_address", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "customer_address")
