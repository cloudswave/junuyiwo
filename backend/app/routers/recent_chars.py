"""Standalone router for /api/recent-chars — avoids path-parameter collision.
四区字库适配: 0=Scout(系统发现), 1=Target(教学区), 2=Ally(友军区), 3=Lost(战损区)"""
from datetime import date as date_type, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TargetCharacter, ScoutCharacter, AllyCharacter, LostCharacter
from .students import get_current_student_id

router = APIRouter()


def _days_ago(d: date_type | datetime | None) -> int | None:
    if not d:
        return None
    if isinstance(d, datetime):
        d = d.date()
    return (date_type.today() - d).days


@router.get("/api/recent-chars")
def get_recent_char_dates(db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    """返回四区所有字的日期信息: {char: {d: days_ago, t: zone}}
    t: 0=Scout(系统发现), 1=Target(教学区), 2=Ally(友军区), 3=Lost(战损区)"""
    char_info: dict[str, dict] = {}

    for r in db.query(TargetCharacter).filter(
        TargetCharacter.student_id == student_id
    ).all():
        char_info[r.character] = {"d": _days_ago(r.added_at) or 0, "t": 1}

    for r in db.query(ScoutCharacter).filter(
        ScoutCharacter.student_id == student_id
    ).all():
        if r.character not in char_info:
            char_info[r.character] = {"d": _days_ago(r.first_seen_date) or 0, "t": 0}

    for r in db.query(AllyCharacter).filter(
        AllyCharacter.student_id == student_id
    ).all():
        if r.character not in char_info:
            char_info[r.character] = {"d": _days_ago(r.created_at) or 0, "t": 2}

    for r in db.query(LostCharacter).filter(
        LostCharacter.student_id == student_id
    ).all():
        if r.character not in char_info:
            char_info[r.character] = {"d": _days_ago(r.first_lost_date) or 0, "t": 3}

    return char_info
