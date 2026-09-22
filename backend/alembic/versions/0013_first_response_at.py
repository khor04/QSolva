"""first_response_at: when an admin first picked a ticket up (claimed it,
replied, or resolved it). The SLA "respond by" deadline is judged against this
rather than the ticket's current status, so a ticket that was claimed and later
released back to the queue doesn't start looking unanswered again.

Existing tickets are backfilled from their earliest admin reply, falling back
to resolved_at/updated_at for ones that were claimed or finished without one.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("alter table tickets add column first_response_at timestamptz")
    op.execute(
        """
        update tickets t
        set first_response_at = coalesce(
            (
                select min(m.created_at)
                from ticket_messages m
                join users u on u.id = m.sender_id
                where m.ticket_id = t.id and u.role = 'admin'
            ),
            t.resolved_at,
            t.updated_at
        )
        where t.assigned_admin_id is not null or t.status <> 'open'
        """
    )


def downgrade() -> None:
    op.execute("alter table tickets drop column first_response_at")
