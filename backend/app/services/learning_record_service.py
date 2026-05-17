from datetime import date, datetime
from sqlalchemy.orm import Session

from ..models import LearningRecord
from ..config import EDUCATION_CONFIG


def record(
    db: Session,
    character: str,
    session_type: str,
    is_correct: bool = False,
    score: float = 0.0,
    user_id: str = "default",
    context: dict | None = None,
    duration_seconds: int | None = None,
    review_schedule_id: int | None = None,
) -> LearningRecord:
    """Record a learning behavior event."""
    record_ = LearningRecord(
        user_id=user_id,
        character=character,
        session_type=session_type,
        score=score,
        is_correct=is_correct,
        context=context,
        duration_seconds=duration_seconds,
        review_schedule_id=review_schedule_id,
    )
    db.add(record_)
    db.commit()
    db.refresh(record_)
    return record_


def get_records(
    db: Session,
    character: str | None = None,
    session_type: str | None = None,
    user_id: str = "default",
    limit: int = 50,
    offset: int = 0,
) -> list[LearningRecord]:
    """Query learning records with optional filters."""
    q = db.query(LearningRecord).filter(LearningRecord.user_id == user_id)
    if character:
        q = q.filter(LearningRecord.character == character)
    if session_type:
        q = q.filter(LearningRecord.session_type == session_type)
    return q.order_by(LearningRecord.created_at.desc()).offset(offset).limit(limit).all()


def get_daily_stats(db: Session, record_date: date | None = None, user_id: str = "default") -> dict:
    """Get today's learning stats."""
    from datetime import date as date_type
    target_date = record_date or date_type.today()

    records = (
        db.query(LearningRecord)
        .filter(
            LearningRecord.user_id == user_id,
            LearningRecord.created_at >= target_date,
        )
        .all()
    )

    unique_chars = set(r.character for r in records)
    correct = sum(1 for r in records if r.is_correct)
    total = len(records)

    return {
        "date": target_date.isoformat(),
        "total_attempts": total,
        "correct_count": correct,
        "accuracy": round(correct / total, 2) if total > 0 else 0.0,
        "unique_characters": len(unique_chars),
        "daily_limit": EDUCATION_CONFIG.REVIEW_DAILY_LIMIT,
        "remaining": max(0, EDUCATION_CONFIG.REVIEW_DAILY_LIMIT - total),
    }
