from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyCharacter
from ..schemas import CharacterCreate, CharacterResponse, CharacterListResponse
from ..services.review_service import add_daily_characters, get_daily_characters
from ..services.article_generator import extract_characters_from_text
from .students import get_current_student_id

router = APIRouter(prefix="/api/characters", tags=["生字管理"])


class TextExtractRequest(BaseModel):
    text: str


class TextExtractResponse(BaseModel):
    characters: list[str]
    count: int


@router.post("/extract", response_model=TextExtractResponse)
def extract_from_text(body: TextExtractRequest):
    chars = extract_characters_from_text(body.text)
    return TextExtractResponse(characters=chars, count=len(chars))


@router.post("/", response_model=list[CharacterResponse])
def create_characters(body: CharacterCreate, db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    records = add_daily_characters(db, body.record_date, body.characters, body.pinyin, body.category, student_id)
    return records


@router.get("/", response_model=list[CharacterListResponse])
def list_characters(db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    from ..services.review_service import get_all_dates_with_characters

    dates = get_all_dates_with_characters(db, student_id)
    result = []
    for d in dates:
        chars = get_daily_characters(db, d, student_id)
        result.append({"date": d, "characters": chars})
    return result


@router.get("/all")
def list_all_unique_characters(category: str | None = Query(None, description="按分类筛选: chinese/math"), db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    """Get all unique characters learned with stats."""
    from collections import Counter

    q = db.query(DailyCharacter).filter(DailyCharacter.student_id == student_id).order_by(DailyCharacter.record_date.desc())
    if category:
        q = q.filter(DailyCharacter.category == category)
    chars = q.all()
    word_stats = {}
    for c in chars:
        if c.character not in word_stats:
            word_stats[c.character] = {
                "character": c.character,
                "pinyin": c.pinyin,
                "first_date": c.record_date.isoformat(),
                "last_date": c.record_date.isoformat(),
                "count": 1,
                "category": c.category,
                "tier": c.tier,
            }
        else:
            word_stats[c.character]["count"] += 1
            word_stats[c.character]["last_date"] = c.record_date.isoformat()
            if c.tier > word_stats[c.character]["tier"]:
                word_stats[c.character]["tier"] = c.tier

    return list(word_stats.values())


@router.get("/{record_date}", response_model=CharacterListResponse)
def get_characters_by_date(record_date: date, db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    chars = get_daily_characters(db, record_date, student_id)
    return {"date": record_date, "characters": chars}


class MarkKnownRequest(BaseModel):
    date: date
    character: str
    article_id: int | None = None  # 当前文章ID，用于跨文章去重（tier2→3需要不同文章）


@router.post("/mark-known")
def mark_character_known(body: MarkKnownRequest, db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    """三层字库晋升逻辑：
    新鲜字库(tier 1): 连续3次"认识" → 升入熟悉字库
    熟悉字库(tier 2): 3篇不同文章中确认 → 升入老朋友字库
    老朋友字库(tier 3): 已掌握，不再变化
    """
    existing = (
        db.query(DailyCharacter)
        .filter(DailyCharacter.character == body.character, DailyCharacter.student_id == student_id)
        .first()
    )

    if not existing:
        # 全新字 → 从 tier 1 开始
        from ..services.review_service import add_daily_characters
        rec = add_daily_characters(db, body.date, [body.character], category="chinese", student_id=student_id)
        if rec:
            rec[0].tier = 1
            rec[0].confirm_count = 1
            db.commit()
        return {
            "character": body.character,
            "tier": 1,
            "confirm_count": 1,
            "promoted": False,
            "message": "已加入新鲜字库，再确认2次升入熟悉字库",
        }

    if existing.tier == 3:
        return {"character": body.character, "tier": 3, "message": "已在老朋友字库，已掌握"}

    if existing.tier == 1:
        existing.confirm_count += 1
        existing.record_date = body.date
        promoted = False
        new_tier = 1
        if existing.confirm_count >= 3:
            existing.tier = 2
            existing.confirm_count = 0
            existing.last_confirm_article_id = body.article_id
            promoted = True
            new_tier = 2
        db.commit()
        return {
            "character": body.character,
            "tier": new_tier,
            "confirm_count": existing.confirm_count,
            "promoted": promoted,
            "message": f"新鲜字库 已确认{existing.confirm_count}次" + (" → 升入熟悉字库！" if promoted else f"，还需{3 - existing.confirm_count}次升入熟悉字库"),
        }

    # tier == 2: need 3 DIFFERENT articles
    if existing.tier == 2:
        if body.article_id and body.article_id == existing.last_confirm_article_id:
            # Same article, don't double count
            return {
                "character": body.character,
                "tier": 2,
                "confirm_count": existing.confirm_count,
                "promoted": False,
                "message": f"熟悉字库 已在本篇确认过（{existing.confirm_count}/3篇），换篇文章再确认",
            }
        existing.confirm_count += 1
        existing.last_confirm_article_id = body.article_id
        existing.record_date = body.date
        promoted = False
        new_tier = 2
        if existing.confirm_count >= 3:
            existing.tier = 3
            existing.confirm_count = 0
            promoted = True
            new_tier = 3
        db.commit()
        return {
            "character": body.character,
            "tier": new_tier,
            "confirm_count": existing.confirm_count,
            "promoted": promoted,
            "message": f"熟悉字库 已确认{existing.confirm_count}/3篇" + (" 升入老朋友字库！俊宜真的会了！" if promoted else f"，还需{3 - existing.confirm_count}篇升入老朋友字库"),
        }

    return {"character": body.character, "message": "未知状态"}


@router.delete("/by-char/{character}")
def delete_character_by_char(character: str, db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    """删除某个汉字的所有记录"""
    db.query(DailyCharacter).filter(DailyCharacter.character == character, DailyCharacter.student_id == student_id).delete()
    db.commit()
    return {"ok": True}


@router.delete("/{character_id}")
def delete_character(character_id: int, db: Session = Depends(get_db)):
    record = db.query(DailyCharacter).filter(DailyCharacter.id == character_id).first()
    if record:
        db.delete(record)
        db.commit()
    return {"ok": True}
