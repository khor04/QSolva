"""Add tickets.priority_reason: a short human-readable explanation for the
AI's triage decision, shown to admins alongside priority/confidence. Cleared
whenever an admin manually overrides priority, since it no longer describes
the current (manual) value.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("alter table tickets add column priority_reason text")


def downgrade() -> None:
    op.execute("alter table tickets drop column priority_reason")
