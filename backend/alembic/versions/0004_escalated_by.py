"""Add tickets.escalated_by_admin_id: records which admin released the
ticket back to the queue, so other admins (and the escalator themselves)
can see who escalated it rather than just "another admin". Cleared when the
ticket is claimed again, since the info stops being relevant once someone
takes ownership.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "alter table tickets add column escalated_by_admin_id uuid references users(id)"
    )


def downgrade() -> None:
    op.execute("alter table tickets drop column escalated_by_admin_id")
