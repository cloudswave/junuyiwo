from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from ..models import UserWordMastery
from ..config import EDUCATION_CONFIG


def schedule_next_review(
    db: Session,
    character: str,
    is_correct: bool,
    user_id: str = "default",
) -> UserWordMastery | None:
    """Schedule the next review date based on performance and Ebbinghaus curve."""
    from .mastery_service import get_or_create_mastery

    mastery = get_or_create_mastery(db, character, user_id)

    intervals = EDUCATION_CONFIG.REVIEW_INTERVALS

    if is_correct:
        mastery.review_count += 1
        # Progress through intervals
        idx = min(mastery.review_count, len(intervals) - 1)
        mastery.review_interval_days = intervals[idx]
    else:
        # Reset to first interval on failure
        mastery.review_interval_days = intervals[0]

    mastery.next_review_date = date.today() + timedelta(days=mastery.review_interval_days)
    mastery.last_updated = datetime.now()
    db.commit()
    db.refresh(mastery)
    return mastery


def get_today_review_queue(
    db: Session,
    user_id: str = "default",
    max_chars: int | None = None,
) -> list[UserWordMastery]:
    """Get characters due for review today, sorted by urgency (lowest mastery first)."""
    if max_chars is None:
        max_chars = EDUCATION_CONFIG.REVIEW_DAILY_LIMIT

    today = date.today()
    return (
        db.query(UserWordMastery)
        .filter(
            UserWordMastery.user_id == user_id,
            UserWordMastery.next_review_date <= today,
        )
        .order_by(UserWordMastery.mastery_level.asc())
        .limit(max_chars)
        .all()
    )


def get_new_words_available(db: Session, user_id: str = "default") -> int:
    """How many new words can be introduced today."""
    today = date.today()
    new_today = (
        db.query(UserWordMastery)
        .filter(
            UserWordMastery.user_id == user_id,
            UserWordMastery.created_at >= today,
        )
        .count()
    )
    return max(0, EDUCATION_CONFIG.NEW_WORDS_DAILY_LIMIT - new_today)


def advance_skill_if_ready(
    db: Session,
    character: str,
    user_id: str = "default",
) -> bool:
    """Check if a character's skill level should advance. Returns True if advanced."""
    from .mastery_service import get_or_create_mastery

    mastery = get_or_create_mastery(db, character, user_id)

    if (
        float(mastery.mastery_level) >= EDUCATION_CONFIG.MASTERY_THRESHOLD
        and mastery.streak_correct >= 3
        and mastery.skill_level < 10
    ):
        old_level = mastery.skill_level
        mastery.skill_level += 1
        mastery.review_interval_days = EDUCATION_CONFIG.REVIEW_INTERVALS[
            min(mastery.skill_level, len(EDUCATION_CONFIG.REVIEW_INTERVALS) - 1)
        ]
        mastery.next_review_date = date.today() + timedelta(days=mastery.review_interval_days)
        mastery.last_updated = datetime.now()
        db.commit()
        return True
    return False


def get_skill_distribution(db: Session, user_id: str = "default") -> dict[int, int]:
    """Get distribution of characters across skill levels."""
    records = db.query(UserWordMastery).filter(UserWordMastery.user_id == user_id).all()
    dist: dict[int, int] = {i: 0 for i in range(1, 11)}
    for r in records:
        dist[r.skill_level] += 1
    return dist
