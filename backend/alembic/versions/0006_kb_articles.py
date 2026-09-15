"""Help Center: an issue_cluster can carry a self-service Q&A article,
AI-drafted from confirmed resolutions once the cluster has enough evidence,
but only visible to staff once an admin explicitly publishes it.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("create type kb_article_status as enum ('draft', 'published')")
    op.execute("alter table issue_clusters add column article_question text")
    op.execute("alter table issue_clusters add column article_answer text")
    op.execute("alter table issue_clusters add column article_status kb_article_status")
    op.execute("alter table issue_clusters add column article_generated_at timestamptz")
    op.execute("alter table issue_clusters add column article_published_at timestamptz")


def downgrade() -> None:
    op.execute("alter table issue_clusters drop column article_published_at")
    op.execute("alter table issue_clusters drop column article_generated_at")
    op.execute("alter table issue_clusters drop column article_status")
    op.execute("alter table issue_clusters drop column article_answer")
    op.execute("alter table issue_clusters drop column article_question")
    op.execute("drop type kb_article_status")
