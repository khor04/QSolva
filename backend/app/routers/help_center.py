import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Feedback, IssueCluster, Ticket, User
from app.schemas import HelpCenterArticleDetail, HelpCenterArticleSummary

router = APIRouter(prefix="/help-center", tags=["help-center"])


def _feedback_counts(db: Session, cluster_id: uuid.UUID) -> tuple[int, int]:
    outcomes = (
        db.execute(
            select(Feedback.outcome).join(Ticket, Ticket.id == Feedback.ticket_id).where(Ticket.cluster_id == cluster_id)
        )
        .scalars()
        .all()
    )
    solved = sum(1 for outcome in outcomes if outcome == "solved")
    return solved, len(outcomes)


@router.get("", response_model=list[HelpCenterArticleSummary])
def list_articles(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    clusters = db.execute(select(IssueCluster).where(IssueCluster.article_status == "published")).scalars().all()
    out = []
    for cluster in clusters:
        solved, total = _feedback_counts(db, cluster.id)
        out.append(
            HelpCenterArticleSummary(
                id=cluster.id,
                label=cluster.label,
                question=cluster.article_question,
                category=cluster.category,
                solved_count=solved,
                total_feedback=total,
            )
        )
    return out


@router.get("/{cluster_id}", response_model=HelpCenterArticleDetail)
def get_article(cluster_id: uuid.UUID, _user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cluster = db.get(IssueCluster, cluster_id)
    if cluster is None or cluster.article_status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    solved, total = _feedback_counts(db, cluster.id)
    return HelpCenterArticleDetail(
        id=cluster.id,
        label=cluster.label,
        question=cluster.article_question,
        answer=cluster.article_answer,
        category=cluster.category,
        solved_count=solved,
        total_feedback=total,
        member_count=cluster.member_count,
    )
