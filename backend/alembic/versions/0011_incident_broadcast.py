"""Broadcast option for incident declarations: a VPN-wide outage affects
everyone using VPN, not just the staff who already filed a ticket about it,
so an admin can choose to notify all staff instead of only those with an
open ticket in the cluster (see services/issues.start_incident). Adds a
free-text `message` column to notifications, since a broadcast alert isn't
about "your ticket" and has no ticket_id to hang a templated message off of.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-19
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safe to run inside a transaction on Postgres 12+ as long as the new
    # value isn't used in the same transaction (it isn't — this migration
    # only alters schema).
    op.execute("alter type notification_type add value 'incident_alert'")
    op.execute("alter table notifications add column message text")


def downgrade() -> None:
    op.execute("alter table notifications drop column message")
    # Postgres has no ALTER TYPE ... DROP VALUE — removing 'incident_alert'
    # would require rebuilding the enum type and is not done here. Any rows
    # of that type will need to be deleted or reassigned by hand first if a
    # full downgrade to a type without it is ever required.
