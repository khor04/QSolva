"""New notification type for a ticket entering "high" priority — mirrors
new_critical_ticket, but one tier down. Needed so the admin-alerts external
channel (see services/alerts.py) can page on high-priority tickets too, not
just critical ones (see services/tickets._run_priority_stage).

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safe to run inside a transaction on Postgres 12+ as long as the new
    # value isn't used in the same transaction (it isn't).
    op.execute("alter type notification_type add value 'new_high_priority_ticket'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE — see 0011_incident_broadcast
    # for the same note. Any rows of this type would need reassigning first.
    pass
