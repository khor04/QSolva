"""last_message_by / last_message_at: who posted the most recent message on a
ticket, and when. Lets the admin queue flag tickets where an admin replied and
the ball has sat in the staff member's court for a while, without a
per-ticket message query on every queue load. Set on every reply (see
routers/tickets.post_message) and backfilled here from ticket_messages.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("alter table tickets add column last_message_by user_role")
    op.execute("alter table tickets add column last_message_at timestamptz")
    op.execute(
        """
        update tickets t
        set last_message_by = last.role, last_message_at = last.created_at
        from (
            select distinct on (m.ticket_id)
                m.ticket_id, u.role, m.created_at
            from ticket_messages m
            join users u on u.id = m.sender_id
            order by m.ticket_id, m.created_at desc
        ) last
        where last.ticket_id = t.id
        """
    )


def downgrade() -> None:
    op.execute("alter table tickets drop column last_message_at")
    op.execute("alter table tickets drop column last_message_by")
