"""
阅读行为上报 — Agent 感知层入口

前端 fire-and-forget 上报 → Agent.perceive.on_char_tap()
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..agent.loop import AgentLoop
from .students import get_current_student_id

router = APIRouter(prefix="/api/reading-behaviors", tags=["Agent·感知"])


class BehaviorReport(BaseModel):
    article_id: int
    character: str | None = None
    action_type: str  # char_tap


@router.post("")
def report_behavior(body: BehaviorReport, db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    """Agent 感知：采集阅读行为（前端 fire-and-forget）"""
    agent = AgentLoop(db, student_id)
    agent.perceive.on_char_tap(body.article_id, body.character or "")
    return {"ok": True}
