"""Escalation reason: an admin handing a ticket off says why ("needs VPN
expertise", "overloaded", ...) so the next owner has the context. A column
rather than a ticket_messages row because messages are the staff-visible
conversation — an internal "I couldn't fix this" must not show up there.
Only exposed to admins (see routers/tickets.get_ticket_detail).

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("alter table tickets add column escalation_reason text")


def downgrade() -> None:
    op.execute("alter table tickets drop column escalation_reason")
