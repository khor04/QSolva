"""Recurring-issue clustering: incrementally groups tickets by embedding
similarity into IssueCluster rows (rather than a separate batch job), so
admins can see systemic/emerging problems instead of only individual
tickets. Runs as part of the same per-ticket enrichment step that already
computes the embedding, so it doesn't cost an extra AI call on its own —
only the occasional label/symptom refresh does.

Also owns resolution-evidence lookup, shared with services/tickets.py's RAG
retrieval: a ticket's resolution counts as evidence whether or not staff
explicitly confirmed it (an admin's own resolution is still real knowledge —
only a ticket closed with no resolution text at all contributes nothing).
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiSuggestion, Feedback, IssueCluster, Ticket, TicketMessage, User
from app.services import ai

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.70  # cosine similarity required to join an existing cluster
# Empirically calibrated (not guessed): live-tested paraphrased same-issue ticket
# pairs scored 0.70-0.86 cosine similarity, while unrelated-issue pairs capped
# around 0.59 — 0.70 sits in the gap with margin on both sides.
MIN_MEMBERS_FOR_SUMMARY = 3  # a cluster needs this many tickets before an AI label makes sense
RESUMMARIZE_EVERY = 3  # refresh the label/symptoms every N members after that
SUMMARY_SAMPLE_SIZE = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_admin_reply(db: Session, ticket_id: uuid.UUID) -> str | None:
    stmt = (
        select(TicketMessage.body)
        .join(User, User.id == TicketMessage.sender_id)
        .where(TicketMessage.ticket_id == ticket_id, User.role == "admin")
        .order_by(TicketMessage.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def resolution_text_for(db: Session, ticket_id: uuid.UUID) -> str | None:
    """The best available resolution text for a ticket: an admin's chat
    reply, or — if the ticket was solved purely by accepting an AI
    suggestion with no separate reply — that suggestion's own text."""
    reply = _latest_admin_reply(db, ticket_id)
    if reply:
        return reply
    return db.execute(
        select(AiSuggestion.resolution_text)
        .where(AiSuggestion.ticket_id == ticket_id, AiSuggestion.state == "accepted")
        .order_by(AiSuggestion.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


@dataclass
class ResolutionEvidence:
    """Three tiers of resolution evidence for a cluster's resolved/closed
    tickets: staff-confirmed (strongest — someone explicitly said it
    worked), admin-resolved (an admin wrote a resolution but no one has
    confirmed it), and unconfirmed (marked done with no resolution text at
    all — not usable as evidence)."""

    staff_confirmed: list[str] = field(default_factory=list)
    admin_resolved: list[str] = field(default_factory=list)
    unconfirmed_count: int = 0

    @property
    def best_resolution(self) -> str | None:
        if self.staff_confirmed:
            return self.staff_confirmed[0]
        if self.admin_resolved:
            return self.admin_resolved[0]
        return None


def gather_evidence(db: Session, cluster_id: uuid.UUID) -> ResolutionEvidence:
    tickets = (
        db.execute(
            select(Ticket.id)
            .where(Ticket.cluster_id == cluster_id, Ticket.status.in_(["resolved", "closed"]))
            .order_by(Ticket.updated_at.desc())
        )
        .scalars()
        .all()
    )
    if not tickets:
        return ResolutionEvidence()

    confirmed_ticket_ids = set(
        db.execute(
            select(Feedback.ticket_id).where(Feedback.ticket_id.in_(tickets), Feedback.outcome == "solved")
        )
        .scalars()
        .all()
    )

    evidence = ResolutionEvidence()
    for ticket_id in tickets:
        text = resolution_text_for(db, ticket_id)
        if text is None:
            evidence.unconfirmed_count += 1
        elif ticket_id in confirmed_ticket_ids:
            evidence.staff_confirmed.append(text)
        else:
            evidence.admin_resolved.append(text)
    return evidence


async def assign_cluster(db: Session, ticket: Ticket, embedding: list[float]) -> IssueCluster:
    distance = IssueCluster.centroid_embedding.cosine_distance(embedding)
    best = db.execute(select(IssueCluster, distance.label("distance")).order_by(distance).limit(1)).first()

    if best is not None and (1 - float(best[1])) >= SIMILARITY_THRESHOLD:
        cluster, _distance = best
        n = cluster.member_count
        # Running average, so the centroid doesn't need every member's embedding kept around.
        cluster.centroid_embedding = [(c * n + e) / (n + 1) for c, e in zip(cluster.centroid_embedding, embedding)]
        cluster.member_count = n + 1
        cluster.updated_at = _now()
    else:
        cluster = IssueCluster(
            label=ticket.title,
            category=ticket.category,
            centroid_embedding=embedding,
            member_count=1,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(cluster)
        db.flush()

    ticket.cluster_id = cluster.id
    db.flush()

    if cluster.member_count >= MIN_MEMBERS_FOR_SUMMARY and cluster.member_count % RESUMMARIZE_EVERY == 0:
        try:
            await _refresh_summary(db, cluster)
        except Exception:
            # The label/symptom refresh is a nice-to-have; the ticket's
            # cluster membership above is already committed-worthy and
            # shouldn't be lost just because this optional AI call failed
            # (e.g. rate-limited).
            logger.exception("Cluster summary refresh failed for cluster %s", cluster.id)

        try:
            await _refresh_article(db, cluster)
        except Exception:
            logger.exception("Cluster KB article refresh failed for cluster %s", cluster.id)

    return cluster


async def _refresh_summary(db: Session, cluster: IssueCluster) -> None:
    sample = db.execute(
        select(Ticket.title, Ticket.description)
        .where(Ticket.cluster_id == cluster.id)
        .order_by(Ticket.created_at.desc())
        .limit(SUMMARY_SAMPLE_SIZE)
    ).all()
    tickets = [{"title": title, "description": description} for title, description in sample]

    label, symptoms = await ai.summarize_cluster(tickets)
    cluster.label = label
    cluster.symptoms = symptoms
    cluster.symptoms_updated_at = _now()


async def _refresh_article(db: Session, cluster: IssueCluster) -> None:
    """Drafts (or updates) the cluster's Help Center article from whatever
    resolution evidence exists — an admin's own resolution is usable even
    before staff confirms it, since otherwise a brand-new problem an admin
    just solved would sit unused until someone happens to click confirm. An
    already-published article's status is left untouched here; it just gets
    fresher content as more evidence comes in, without needing re-approval
    for every refresh."""
    evidence = gather_evidence(db, cluster.id)
    if evidence.best_resolution is None:
        return  # nothing usable to draft an article from yet

    question, answer = await ai.generate_kb_article(
        label=cluster.label,
        symptoms=cluster.symptoms or [],
        confirmed_resolution=evidence.best_resolution,
        staff_confirmed_count=len(evidence.staff_confirmed),
        admin_resolved_count=len(evidence.admin_resolved),
        member_count=cluster.member_count,
    )
    cluster.article_question = question
    cluster.article_answer = answer
    cluster.article_generated_at = _now()
    if cluster.article_status is None:
        cluster.article_status = "draft"
