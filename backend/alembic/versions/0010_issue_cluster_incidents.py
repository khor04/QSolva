"""Incident mode for recurring issues: an admin can explicitly declare a
cluster an "active incident" with a status message, which surfaces on every
ticket in that cluster (see services/issues.related_activity_for) instead of
each reporter waiting in silence not knowing 40 other people already filed
the same thing. Resolving the incident lets the admin close out every
still-open ticket in the cluster with one shared reply instead of retyping
the same resolution into each one individually.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-19
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("create type incident_status as enum ('active', 'resolved')")
    op.execute("alter table issue_clusters add column incident_status incident_status")
    op.execute("alter table issue_clusters add column incident_message text")
    op.execute("alter table issue_clusters add column incident_updated_at timestamptz")


def downgrade() -> None:
    op.execute("alter table issue_clusters drop column incident_updated_at")
    op.execute("alter table issue_clusters drop column incident_message")
    op.execute("alter table issue_clusters drop column incident_status")
    op.execute("drop type incident_status")
