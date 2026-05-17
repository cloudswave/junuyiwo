from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ForgottenRecord, ForgottenResponse, ForgottenListResponse
from ..services.review_service import (
    record_forgotten,
    get_forgotten_characters,
    get_forgotten_stats,
    mark_learned,
)
from .students import get_current_student_id

router = APIRouter(prefix="/api/review", tags=["复习管理"])


@router.post("/forgotten")
def record_forgotten_chars(body: ForgottenRecord, db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    record_forgotten(db, body.date, body.characters, body.pinyin, body.category, body.learned_days_ago, student_id)
    return {"ok": True}


@router.get("/forgotten", response_model=ForgottenListResponse)
def list_forgotten(
    level: str | None = Query(None, description="筛选等级: 活跃/三次/五次以上"),
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    items = get_forgotten_characters(db, level, student_id)
    stats = get_forgotten_stats(db, student_id)
    return {
        "total": len(items),
        "items": items,
        "level_counts": stats,
    }


@router.post("/forgotten/{character_id}/learned")
def mark_as_learned(character_id: int, db: Session = Depends(get_db)):
    mark_learned(db, character_id)
    return {"ok": True}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    return get_forgotten_stats(db, student_id)
