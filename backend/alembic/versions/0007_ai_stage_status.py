"""Add tickets.ai_priority_status / ai_rag_status: persist the AI priority
classification and RAG-suggestion pipelines as two independent outcomes
(pending/success/failed, and pending/success/no_match/failed) instead of
inferring success from priority_confidence being non-null or an AiSuggestion
row existing. This lets a failed stage be retried without redoing one that
already succeeded, and lets the UI tell "no similar cases found" (no_match,
not an error) apart from "the AI service call itself failed" (failed,
retryable) — see POST /tickets/{id}/retry-enrichment.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("create type ai_priority_status as enum ('pending', 'success', 'failed')")
    op.execute("create type ai_rag_status as enum ('pending', 'success', 'no_match', 'failed')")
    op.execute("alter table tickets add column ai_priority_status ai_priority_status not null default 'pending'")
    op.execute("alter table tickets add column ai_rag_status ai_rag_status not null default 'pending'")

    # Backfill from existing evidence: a ticket that already has an AI
    # confidence score completed priority classification; one with a stored
    # embedding got at least as far as the RAG stage running (whether or
    # not it produced a usable suggestion).
    op.execute("update tickets set ai_priority_status = 'success' where priority_confidence is not null")
    op.execute(
        "update tickets set ai_rag_status = 'success' where id in (select ticket_id from ai_suggestions)"
    )
    op.execute(
        "update tickets set ai_rag_status = 'no_match' "
        "where ai_rag_status = 'pending' and id in (select ticket_id from ticket_embeddings)"
    )


def downgrade() -> None:
    op.execute("alter table tickets drop column ai_rag_status")
    op.execute("alter table tickets drop column ai_priority_status")
    op.execute("drop type ai_rag_status")
    op.execute("drop type ai_priority_status")
