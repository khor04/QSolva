"""Add 'ticket_escalated' to notification_type: escalating a ticket now
releases it back to the queue and notifies both the other admins and the
staff member, distinct from the generic ticket_updated notification.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside the transaction Alembic
    # normally wraps migrations in, so it needs its own autocommit block.
    with op.get_context().autocommit_block():
        op.execute("alter type notification_type add value if not exists 'ticket_escalated'")


def downgrade() -> None:
    # Postgres has no direct way to remove a single enum value.
    pass
