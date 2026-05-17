"""
四区字库 API — Target / Scout / Ally / Lost
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import zone_service
from .students import get_current_student_id

router = APIRouter(prefix="/api/zones", tags=["四区字库"])


# ===== Schemas =====

class CharListRequest(BaseModel):
    characters: list[str]
    pinyin: list[str] | None = None
    source: str = "manual"


class ZoneCharResponse(BaseModel):
    id: int
    character: str
    pinyin: str | None = None
    source: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class ScoutCharResponse(ZoneCharResponse):
    appeared_in_read_count: int
    never_tapped_in_read_count: int


class LostCharResponse(ZoneCharResponse):
    tap_count: int
    article_count: int
    status: str


class ZoneSummary(BaseModel):
    target: int
    scout: int
    ally: int
    lost: int


def _format_dt(dt) -> str | None:
    return dt.isoformat() if dt else None


# ===== 教学区 (Target) =====

@router.post("/target")
def add_target(body: CharListRequest, db: Session = Depends(get_db),
               student_id: int = Depends(get_current_student_id)):
    records = zone_service.target_add(
        db, body.characters, student_id, body.pinyin, body.source)
    return {"ok": True, "count": len(records)}


@router.get("/target")
def list_target(db: Session = Depends(get_db),
                student_id: int = Depends(get_current_student_id)):
    items = zone_service.target_list(db, student_id)
    return [{
        "id": r.id, "character": r.character, "pinyin": r.pinyin,
        "source": r.source, "added_at": _format_dt(r.added_at),
    } for r in items]


@router.delete("/target/{character}")
def delete_target(character: str, db: Session = Depends(get_db),
                  student_id: int = Depends(get_current_student_id)):
    zone_service.target_delete(db, character, student_id)
    return {"ok": True}


# ===== 侦查区 (Scout) =====

@router.post("/scout")
def add_scout(body: CharListRequest, db: Session = Depends(get_db),
              student_id: int = Depends(get_current_student_id)):
    records = zone_service.scout_add(
        db, body.characters, student_id, body.source, pinyin=body.pinyin)
    return {"ok": True, "count": len(records)}


@router.get("/scout")
def list_scout(db: Session = Depends(get_db),
               student_id: int = Depends(get_current_student_id)):
    items = zone_service.scout_list(db, student_id)
    return [{
        "id": r.id, "character": r.character, "pinyin": r.pinyin,
        "source": r.source,
        "appeared_in_read_count": r.appeared_in_read_count,
        "never_tapped_in_read_count": r.never_tapped_in_read_count,
        "created_at": _format_dt(r.created_at),
    } for r in items]


@router.delete("/scout/{character}")
def delete_scout(character: str, db: Session = Depends(get_db),
                 student_id: int = Depends(get_current_student_id)):
    zone_service.scout_delete(db, character, student_id)
    return {"ok": True}


# ===== 友军区 (Ally) =====

@router.post("/ally")
def add_ally(body: CharListRequest, db: Session = Depends(get_db),
             student_id: int = Depends(get_current_student_id)):
    records = zone_service.ally_add(
        db, body.characters, student_id, body.source, body.pinyin)
    return {"ok": True, "count": len(records)}


@router.get("/ally")
def list_ally(db: Session = Depends(get_db),
              student_id: int = Depends(get_current_student_id)):
    items = zone_service.ally_list(db, student_id)
    return [{
        "id": r.id, "character": r.character, "pinyin": r.pinyin,
        "source": r.source, "created_at": _format_dt(r.created_at),
    } for r in items]


@router.delete("/ally/{character}")
def delete_ally(character: str, db: Session = Depends(get_db),
                student_id: int = Depends(get_current_student_id)):
    zone_service.ally_delete(db, character, student_id)
    return {"ok": True}


# ===== 战损区 (Lost) =====

@router.get("/lost")
def list_lost(db: Session = Depends(get_db),
              student_id: int = Depends(get_current_student_id)):
    items = zone_service.lost_list(db, student_id)
    return [{
        "id": r.id, "character": r.character, "pinyin": r.pinyin,
        "tap_count": r.tap_count, "article_count": r.article_count,
        "first_lost_date": _format_dt(r.first_lost_date),
        "last_lost_date": _format_dt(r.last_lost_date),
        "status": r.status,
    } for r in items]


@router.post("/lost/{character}/recover")
def recover_lost(character: str, db: Session = Depends(get_db),
                 student_id: int = Depends(get_current_student_id)):
    zone_service.lost_recover(db, character, student_id)
    return {"ok": True, "message": f"「{character}」已移回侦查区"}


# ===== 四区总览 =====

@router.get("/summary", response_model=ZoneSummary)
def summary(db: Session = Depends(get_db),
            student_id: int = Depends(get_current_student_id)):
    return zone_service.zone_summary(db, student_id)


# ===== 文章生字密度配置（家长模式）=====

class ArticleParamsRequest(BaseModel):
    override: dict | None = None  # {min_chars, max_chars, density, reinforce} 均可选


@router.get("/article-config")
def get_article_config(db: Session = Depends(get_db),
                       student_id: int = Depends(get_current_student_id)):
    """获取当前密度配置 + 自动计算的推荐参数"""
    config = zone_service.get_parent_config(db, student_id)
    params = zone_service.calculate_article_params(db, student_id)
    return {**config, "current_params": params}


@router.post("/article-params")
def compute_article_params(body: ArticleParamsRequest, db: Session = Depends(get_db),
                           student_id: int = Depends(get_current_student_id)):
    """根据当前字库自动计算文章参数，可选家长覆盖"""
    return zone_service.calculate_article_params(db, student_id, body.override)


class AutoGenerateRequest(BaseModel):
    topic: str
    category: str = "story"
    override: dict | None = None


@router.post("/auto-generate")
def auto_generate_article(body: AutoGenerateRequest, db: Session = Depends(get_db),
                          student_id: int = Depends(get_current_student_id)):
    """根据四区密度规则自动选字并生成文章，返回带拼音的文章"""
    from ..services.article_generator import (
        generate_article_with_pinyin, build_zone_context,
        build_recent_chars_context, build_behavior_context,
    )
    from ..services.memory_service import get_memory_context
    from ..models import DailyArticle
    from ..services.pinyin_service import annotate_article
    import threading

    # 1. 计算密度参数
    params = zone_service.calculate_article_params(db, student_id, body.override)

    target_chars = params["target_chars"]
    if not target_chars:
        raise HTTPException(status_code=400, detail="教学区没有生字，请先录入生字")

    # 2. 构建上下文
    memory_ctx = get_memory_context(db, body.topic, target_chars)
    memory_ctx_str = memory_ctx.get("prompt_context", "") if memory_ctx else ""
    recent_ctx = build_recent_chars_context(db, days=5, student_id=student_id)
    behavior_ctx = build_behavior_context(db, days=7, student_id=student_id)
    zone_ctx = build_zone_context(db, student_id)

    # 3. 生成文章
    try:
        article_data = generate_article_with_pinyin(
            topic=body.topic,
            characters=target_chars,
            min_chars=params["article_min"],
            max_chars=params["article_max"],
            category=body.category,
            memory_context=memory_ctx_str,
            recent_chars_context=recent_ctx,
            behavior_context=behavior_ctx,
            zone_context=zone_ctx,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI生成失败: {str(e)}")

    content = article_data.get("content", "")
    if not content:
        raise HTTPException(status_code=500, detail="AI返回了空内容")

    # 4. 保存文章
    today = date.today()
    article = DailyArticle(
        student_id=student_id,
        record_date=today,
        topic=body.topic,
        content=content,
        character_count=len(content),
        source="ai",
        category=body.category,
    )
    db.add(article)
    db.commit()
    db.refresh(article)

    # 5. 拼音注音
    annotated = annotate_article(content)

    return {
        "id": article.id,
        "record_date": article.record_date.isoformat(),
        "topic": article.topic,
        "content": article.content,
        "character_count": article.character_count,
        "source": article.source,
        "category": article.category,
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "image_url": article.image_url,
        "images": article.images_json or [],
        "paragraphs": annotated["paragraphs"],
        "_params": {
            "article_min": params["article_min"],
            "article_max": params["article_max"],
            "target_density": params["target_density"],
            "reinforce_density": params["reinforce_density"],
            "target_chars": target_chars,
            "reinforce_chars": params["reinforce_chars"],
            "known_count": params["known_count"],
            "tier_index": params["tier_index"],
        },
    }


# ===== 阅读等级（自动晋升）=====

@router.get("/reading-level")
def get_reading_level(db: Session = Depends(get_db),
                      student_id: int = Depends(get_current_student_id)):
    """获取当前学生的阅读等级和晋升进度"""
    return zone_service.get_reading_level_info(db, student_id)


@router.post("/reading-level/check")
def trigger_level_check(db: Session = Depends(get_db),
                        student_id: int = Depends(get_current_student_id)):
    """手动触发等级晋升检查（阅读后自动检查，此为手动入口）"""
    result = zone_service.check_reading_level_up(db, student_id)
    if result:
        return result
    info = zone_service.get_reading_level_info(db, student_id)
    return {"promoted": False, "message": "暂未满足晋升条件", "current": info}
