from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.memory_service import get_memory_context

router = APIRouter(prefix="/api/memory", tags=["记忆上下文"])


class MemoryContextRequest(BaseModel):
    topic: str
    characters: list[str]
    lookback_days: int = 30


@router.post("/context")
def memory_context(body: MemoryContextRequest, db: Session = Depends(get_db)):
    """Get the child's learning memory context relevant to a topic.

    Returns recent articles, unanswered questions, and easily-forgotten characters
    to help the parent decide whether to weave them into a new article.
    """
    return get_memory_context(db, body.topic, body.characters, body.lookback_days)
