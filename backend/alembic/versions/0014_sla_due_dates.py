"""Store response_due_at/resolution_due_at on the ticket instead of computing
them on read. Needed because the SLA clock now differs by priority — 24/7 for
critical/high, business-hours-only for medium/low (see services/sla_policy.py)
— and the business-hours math isn't expressible as a plain SQL comparison the
way "created_at + N hours" was.

Backfill uses a flat calendar-time approximation (created_at + target) for all
priorities, including medium/low. That's wrong for medium/low by the business-
hours pauses, but these are historical tickets — mostly already resolved or
closed — so an exactly-right backfill isn't worth the SQL to express a
business-hours walk here. Any ticket whose priority changes after this
migration gets an accurate, business-hours-aware recompute (see
services/sla_policy.compute_due_dates).

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors services/sla_policy.SLA_POLICY as of this migration. If that policy
# changes later, only *new* backfills (of tickets created before this
# migration) would drift from it — already-migrated rows aren't touched again.
_TARGETS = {
    "critical": ("30 minutes", "4 hours"),
    "high": ("2 hours", "8 hours"),
    "medium": ("4 hours", "18 hours"),  # 2 * (18-9)h business day
    "low": ("9 hours", "36 hours"),  # 1 / 4 business days of a 9h window
}


def upgrade() -> None:
    op.execute("alter table tickets add column response_due_at timestamptz")
    op.execute("alter table tickets add column resolution_due_at timestamptz")
    for priority, (response, resolution) in _TARGETS.items():
        op.execute(
            f"""
            update tickets
            set response_due_at = created_at + interval '{response}',
                resolution_due_at = created_at + interval '{resolution}'
            where priority = '{priority}'
            """
        )
    op.execute("alter table tickets alter column response_due_at set not null")
    op.execute("alter table tickets alter column resolution_due_at set not null")


def downgrade() -> None:
    op.execute("alter table tickets drop column resolution_due_at")
    op.execute("alter table tickets drop column response_due_at")
