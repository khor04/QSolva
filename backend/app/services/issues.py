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
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import AiSuggestion, Feedback, IssueCluster, Ticket, TicketEmbedding, TicketMessage, User
from app.services import ai
from app.services.alerts import send_admin_alert
from app.services.notifications import all_staff_ids, notify, notify_admins

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.70  # cosine similarity required to join an existing cluster
# Empirically calibrated (not guessed): live-tested paraphrased same-issue ticket
# pairs scored 0.70-0.86 cosine similarity, while unrelated-issue pairs capped
# around 0.59 — 0.70 sits in the gap with margin on both sides.
MIN_MEMBERS_FOR_SUMMARY = 3  # a cluster needs this many tickets before an AI label makes sense
RESUMMARIZE_EVERY = 3  # refresh the label/symptoms every N members after that
SUMMARY_SAMPLE_SIZE = 10

OPEN_STATUSES = ("open", "in_progress", "escalated")
RELATED_ACTIVITY_WINDOW_HOURS = 24  # "recent" for the "others are reporting this" banner
MIN_RELATED_FOR_BANNER = 2  # one other duplicate ticket isn't a signal worth surfacing on its own


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


@dataclass
class RelatedActivity:
    """"Others are already reporting this" signal for a single ticket's
    detail page: is this a known, currently-active problem rather than
    something the reporter is waiting on alone."""

    active_reports: int
    window_hours: int
    someone_working_on_it: bool
    incident_status: str | None
    incident_message: str | None


def related_activity_for(db: Session, ticket: Ticket) -> RelatedActivity | None:
    """None means there's nothing worth surfacing — either the ticket isn't
    clustered yet, or it's the only recent/open report in its cluster and no
    admin has declared an incident. Returns a populated RelatedActivity as
    soon as either condition says otherwise, so the frontend can show a
    banner instead of leaving the reporter to wait in silence."""
    if ticket.cluster_id is None:
        return None
    cluster = db.get(IssueCluster, ticket.cluster_id)
    if cluster is None:
        return None

    since = _now() - timedelta(hours=RELATED_ACTIVITY_WINDOW_HOURS)
    rows = db.execute(
        select(Ticket.assigned_admin_id).where(
            Ticket.cluster_id == cluster.id,
            Ticket.id != ticket.id,
            Ticket.created_at >= since,
            Ticket.status.in_(OPEN_STATUSES),
        )
    ).all()
    active_reports = len(rows)
    incident_active = cluster.incident_status == "active"

    if active_reports < MIN_RELATED_FOR_BANNER and not incident_active:
        return None

    return RelatedActivity(
        active_reports=active_reports,
        window_hours=RELATED_ACTIVITY_WINDOW_HOURS,
        someone_working_on_it=incident_active or any(admin_id is not None for (admin_id,) in rows),
        incident_status=cluster.incident_status,
        incident_message=cluster.incident_message if incident_active else None,
    )


def start_incident(
    db: Session, cluster: IssueCluster, message: str, admin: User, notify_all_staff: bool = False
) -> int:
    """Declares (or updates the status message of) an active incident, and
    — only on the transition into "active" — notifies people about it,
    rather than re-notifying everyone each time the admin tweaks the
    message. By default that's just staff with a still-open ticket in the
    cluster; for something like a VPN outage that affects everyone on VPN,
    not only the handful who've already filed a ticket, notify_all_staff
    broadcasts to the whole staff roster instead. Returns how many people
    were notified.

    Staff who already have an open ticket in the cluster still get the
    ticket-scoped notification (so it links straight to their own ticket)
    even in broadcast mode; only staff with no ticket in the cluster get the
    generic incident_alert. Every other admin also gets notified (excluding
    whoever declared it) — otherwise only the declaring admin would know
    this incident exists, and others could end up independently
    investigating or replying to the same problem."""
    was_active = cluster.incident_status == "active"
    cluster.incident_status = "active"
    cluster.incident_message = message
    cluster.incident_updated_at = _now()

    tickets = db.execute(
        select(Ticket).where(Ticket.cluster_id == cluster.id, Ticket.status.in_(OPEN_STATUSES))
    ).scalars().all()
    reporting_staff = {t.staff_id: t.id for t in tickets}

    notified = 0
    if not was_active:
        for staff_id, ticket_id in reporting_staff.items():
            notify(db, staff_id, "ticket_updated", ticket_id)
            notified += 1
        if notify_all_staff:
            for staff_id in all_staff_ids(db):
                if staff_id in reporting_staff:
                    continue  # already got the ticket-scoped notification above
                notify(db, staff_id, "incident_alert", message=message)
                notified += 1
        notify_admins(db, "incident_alert", message=message, exclude_user_id=admin.id)
        send_admin_alert(f"🔶 New incident declared by {admin.name}: {cluster.label} — {message}")
        other_admin_count = db.execute(
            select(func.count()).select_from(User).where(User.role == "admin", User.id != admin.id)
        ).scalar_one()
        notified += other_admin_count
    db.commit()
    return notified


def resolve_incident(db: Session, cluster: IssueCluster, resolution_text: str, admin: User) -> int:
    """Bulk-resolves every still-open ticket in the cluster with one shared
    reply, so an admin doesn't have to retype the same resolution into each
    of (potentially dozens of) individual tickets. Returns how many tickets
    were resolved."""
    now = _now()
    tickets = db.execute(
        select(Ticket).where(Ticket.cluster_id == cluster.id, Ticket.status.in_(OPEN_STATUSES))
    ).scalars().all()
    for t in tickets:
        db.add(TicketMessage(ticket_id=t.id, sender_id=admin.id, body=resolution_text, created_at=now))
        t.status = "resolved"
        t.resolved_at = now
        if t.first_response_at is None:
            t.first_response_at = now
        t.updated_at = now
        t.escalated_by_admin_id = None
        notify(db, t.staff_id, "resolution_confirm_needed", t.id)

    cluster.incident_status = "resolved"
    cluster.incident_updated_at = now
    db.commit()
    return len(tickets)


_KNOWN_ISSUE_FILTER = or_(IssueCluster.incident_status == "active", IssueCluster.article_status == "published")


async def match_known_issue(db: Session, title: str, description: str) -> IssueCluster | None:
    """Pre-submit check for the New Ticket form: does this draft match a
    cluster an admin has already vetted for staff visibility — either a
    declared active incident, or a published Help Center article. Both are
    admin-gated (start_incident / routers/issues.publish_article), so
    surfacing either is safe; an unreviewed cluster (however large) never
    reaches this check regardless of member_count. Deliberately cheap (no AI
    call at all) when neither exists yet — the common case — so declaring
    zero incidents and publishing zero articles costs nothing extra on every
    single ticket submission."""
    has_candidate = db.execute(select(IssueCluster.id).where(_KNOWN_ISSUE_FILTER).limit(1)).first()
    if has_candidate is None:
        return None

    embedding = await ai.embed_text(f"{title}\n{description}")
    distance = IssueCluster.centroid_embedding.cosine_distance(embedding)
    best = db.execute(
        select(IssueCluster, distance.label("distance"))
        .where(_KNOWN_ISSUE_FILTER)
        .order_by(distance)
        .limit(1)
    ).first()
    if best is None:
        return None
    cluster, dist = best
    if (1 - float(dist)) < SIMILARITY_THRESHOLD:
        return None
    return cluster


async def create_incident_from_scratch(
    db: Session,
    label: str,
    category: str,
    description: str,
    message: str,
    admin: User,
    notify_all_staff: bool,
) -> IssueCluster:
    """Declares a brand-new incident with no recurring-issue cluster behind
    it yet — e.g. IT knows about an outage from internal monitoring before
    any ticket has been filed. Seeds the cluster's centroid from the admin's
    own problem description so tickets that come in afterward can still
    auto-join it via assign_cluster, the same as an algorithmically-detected
    cluster would."""
    embedding = await ai.embed_text(f"{label}\n{description}")
    cluster = IssueCluster(
        label=label,
        category=category,
        centroid_embedding=embedding,
        member_count=0,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(cluster)
    db.flush()
    start_incident(db, cluster, message, admin, notify_all_staff=notify_all_staff)
    return cluster


def escalate_ticket_to_incident(
    db: Session, ticket: Ticket, message: str, admin: User, notify_all_staff: bool
) -> IssueCluster:
    """Declares a new incident seeded from a single, not-yet-clustered
    ticket — for when an admin spots a first report that's clearly going to
    be widespread and doesn't want to wait for the automatic clustering
    threshold (2+ similar tickets) before acting. Reuses the ticket's own
    embedding (already computed by the RAG stage) rather than asking the
    admin to redescribe the problem. Tickets already in a cluster should use
    that cluster's own incident flow on the Issues page instead — raises
    rather than silently pulling a ticket out of an existing cluster."""
    if ticket.cluster_id is not None:
        raise ValueError("Ticket is already part of a recurring-issue cluster")
    embedding_row = db.get(TicketEmbedding, ticket.id)
    if embedding_row is None:
        raise ValueError("This ticket has no AI embedding yet — analysis may still be in progress")

    cluster = IssueCluster(
        label=ticket.title,
        category=ticket.category,
        centroid_embedding=embedding_row.embedding,
        member_count=1,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(cluster)
    db.flush()
    ticket.cluster_id = cluster.id
    start_incident(db, cluster, message, admin, notify_all_staff=notify_all_staff)
    return cluster


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
