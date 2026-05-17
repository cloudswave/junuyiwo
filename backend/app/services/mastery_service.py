from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from ..models import UserWordMastery
from ..config import EDUCATION_CONFIG


def get_or_create_mastery(db: Session, character: str, user_id: str = "default") -> UserWordMastery:
    """Get existing mastery record or create a new one."""
    mastery = (
        db.query(UserWordMastery)
        .filter(UserWordMastery.user_id == user_id, UserWordMastery.character == character)
        .first()
    )
    if not mastery:
        mastery = UserWordMastery(user_id=user_id, character=character)
        db.add(mastery)
        db.commit()
        db.refresh(mastery)
    return mastery


def update_mastery(
    db: Session,
    character: str,
    session_type: str,
    is_correct: bool,
    score: float = 0.0,
    user_id: str = "default",
) -> UserWordMastery:
    """Update mastery after a learning event."""
    mastery = get_or_create_mastery(db, character, user_id)

    weight = EDUCATION_CONFIG.MASTERY_WEIGHTS.get(session_type, 0.1)

    mastery.total_attempts += 1
    if is_correct:
        mastery.correct_count += 1
        mastery.streak_correct += 1
    else:
        mastery.streak_correct = 0

    # Weighted moving average for mastery level
    alpha = 0.3
    mastery.mastery_level = round(
        (1 - alpha) * float(mastery.mastery_level) + alpha * score * weight * 2,
        2,
    )
    mastery.mastery_level = min(1.0, float(mastery.mastery_level))

    # Update stability
    if is_correct:
        mastery.stability = round(min(1.0, float(mastery.stability) + 0.1), 2)
    else:
        mastery.stability = round(max(0.0, float(mastery.stability) - 0.2), 2)

    # Update skill level based on mastery
    if float(mastery.mastery_level) >= EDUCATION_CONFIG.MASTERY_THRESHOLD and mastery.streak_correct >= 3:
        mastery.skill_level = min(10, mastery.skill_level + 1)
    elif mastery.streak_correct == 0 and float(mastery.mastery_level) < 0.3:
        mastery.skill_level = max(1, mastery.skill_level - 1)

    mastery.last_studied_at = datetime.now()
    mastery.last_updated = datetime.now()
    db.commit()
    db.refresh(mastery)
    return mastery


def get_characters_for_article(db: Session, skill_level: int, user_id: str = "default") -> int:
    """Get recommended new character count per 100 chars of article for a skill level."""
    return EDUCATION_CONFIG.SKILL_LEVEL_DENSITY.get(skill_level, 5)


def get_due_reviews(db: Session, user_id: str = "default", limit: int | None = None) -> list[UserWordMastery]:
    """Get characters due for review today."""
    today = date.today()
    q = (
        db.query(UserWordMastery)
        .filter(
            UserWordMastery.user_id == user_id,
            UserWordMastery.next_review_date <= today,
        )
        .order_by(UserWordMastery.mastery_level.asc())
    )
    if limit:
        q = q.limit(limit)
    return q.all()


def get_mastery_summary(db: Session, user_id: str = "default") -> dict:
    """Get overall mastery statistics."""
    records = db.query(UserWordMastery).filter(UserWordMastery.user_id == user_id).all()
    total = len(records)
    if total == 0:
        return {"total": 0, "mastered": 0, "learning": 0, "average_mastery": 0.0, "average_skill": 1.0}

    mastered = sum(1 for r in records if float(r.mastery_level) >= EDUCATION_CONFIG.MASTERY_THRESHOLD)
    avg_mastery = round(sum(float(r.mastery_level) for r in records) / total, 2)
    avg_skill = round(sum(r.skill_level for r in records) / total, 1)
    return {
        "total": total,
        "mastered": mastered,
        "learning": total - mastered,
        "average_mastery": avg_mastery,
        "average_skill": avg_skill,
    }
