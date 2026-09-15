"""Self-service account deletion, replacing the "reject if any activity"
rule with anonymize-in-place: since every ticket/message/feedback/invite-code
FK points at users(id), keeping the same row and just overwriting name/email
makes every join automatically resolve to "Deleted User" for free, with no
per-table cleanup needed. The row is never actually deleted (that would
cascade from auth.users and take every ticket FK down with it) — deleted_at
is the authoritative "this account is gone" flag, checked in deps.py so an
already-issued JWT stops working immediately rather than staying valid until
it naturally expires.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("alter table users add column deleted_at timestamptz")


def downgrade() -> None:
    op.execute("alter table users drop column deleted_at")
