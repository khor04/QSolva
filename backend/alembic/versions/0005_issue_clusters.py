"""Recurring Issues: tickets are incrementally clustered by embedding
similarity into issue_clusters, so admins can see systemic/emerging problems
(e.g. "VPN Connection Timeout, 18 tickets this week") instead of only
individual tickets.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        create table issue_clusters (
            id uuid primary key,
            label text not null,
            category ticket_category not null,
            centroid_embedding vector(768) not null,
            member_count integer not null default 1,
            symptoms jsonb,
            symptoms_updated_at timestamptz,
            created_at timestamptz not null,
            updated_at timestamptz not null
        )
        """
    )
    op.execute("alter table tickets add column cluster_id uuid references issue_clusters(id)")


def downgrade() -> None:
    op.execute("alter table tickets drop column cluster_id")
    op.execute("drop table issue_clusters")
