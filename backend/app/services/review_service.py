from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import DailyCharacter, ForgottenCharacter, TargetCharacter


def add_daily_characters(db: Session, record_date: date, characters: list[str], pinyin: list[str] | None = None, category: str = "chinese", student_id: int = 1):
    records = []
    for i, char in enumerate(characters):
        py = pinyin[i] if pinyin and i < len(pinyin) else None
        existing = db.query(DailyCharacter).filter(
            DailyCharacter.record_date == record_date,
            DailyCharacter.character == char,
            DailyCharacter.student_id == student_id,
        ).first()
        if existing:
            continue
        record = DailyCharacter(record_date=record_date, character=char, pinyin=py, category=category, student_id=student_id)
        db.add(record)
        records.append(record)
    db.commit()
    return records


def get_daily_characters(db: Session, record_date: date, student_id: int = 1) -> list[DailyCharacter]:
    return db.query(DailyCharacter).filter(DailyCharacter.record_date == record_date, DailyCharacter.student_id == student_id).all()


def get_all_dates_with_characters(db: Session, student_id: int = 1) -> list[date]:
    rows = db.query(DailyCharacter.record_date).filter(DailyCharacter.student_id == student_id).distinct().order_by(DailyCharacter.record_date.desc()).all()
    return [r[0] for r in rows]


def get_today_target_chars(db: Session, student_id: int = 1) -> list[str]:
    """读取今天录入的教学区生字"""
    today = date.today()
    rows = (
        db.query(TargetCharacter.character)
        .filter(func.date(TargetCharacter.added_at) == today, TargetCharacter.student_id == student_id)
        .all()
    )
    return [r[0] for r in rows]


def get_total_target_chars(db: Session, student_id: int = 1) -> int:
    return db.query(TargetCharacter).filter(TargetCharacter.student_id == student_id).count()


def record_forgotten(db: Session, forgotten_date: date, characters: list[str], pinyin: list[str] | None = None, category: str = "chinese", learned_days_ago: list[int | None] | None = None, student_id: int = 1):
    for i, char in enumerate(characters):
        py = pinyin[i] if pinyin and i < len(pinyin) else None
        lda = learned_days_ago[i] if learned_days_ago and i < len(learned_days_ago) else None
        existing = db.query(ForgottenCharacter).filter(ForgottenCharacter.character == char, ForgottenCharacter.student_id == student_id).first()
        if existing:
            existing.forget_count += 1
            existing.last_forgotten_date = forgotten_date
            existing.level = _compute_level(existing.forget_count)
        else:
            record = ForgottenCharacter(
                student_id=student_id,
                character=char,
                pinyin=py,
                forget_count=1,
                first_forgotten_date=forgotten_date,
                last_forgotten_date=forgotten_date,
                level="active",
                category=category,
                learned_days_ago=lda,
            )
            db.add(record)
    db.commit()


def _compute_level(count: int) -> str:
    if count >= 5:
        return "五次以上"
    elif count >= 3:
        return "三次"
    else:
        return "活跃"


def get_forgotten_characters(db: Session, level: str | None = None, student_id: int = 1) -> list[ForgottenCharacter]:
    q = db.query(ForgottenCharacter).filter(ForgottenCharacter.student_id == student_id).order_by(ForgottenCharacter.forget_count.desc())
    if level:
        q = q.filter(ForgottenCharacter.level == level)
    return q.all()


def get_forgotten_stats(db: Session, student_id: int = 1) -> dict[str, int]:
    rows = db.query(ForgottenCharacter.level, func.count(ForgottenCharacter.id)).filter(ForgottenCharacter.student_id == student_id).group_by(ForgottenCharacter.level).all()
    stats = {"活跃": 0, "三次": 0, "五次以上": 0}
    for level, cnt in rows:
        stats[level] = cnt
    return stats


def mark_learned(db: Session, character_id: int):
    record = db.query(ForgottenCharacter).filter(ForgottenCharacter.id == character_id).first()
    if record:
        record.level = "已学会"
        db.commit()
