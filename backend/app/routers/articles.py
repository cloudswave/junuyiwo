import threading
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyArticle, ArticleSeries
from ..schemas import ArticleGenerate, ArticleCreate, ArticleResponse
from ..services.article_generator import generate_article_images
from ..services.pinyin_service import annotate_article
from ..services.memory_service import get_memory_context
from ..services.curiosity_service import link_article as link_curiosity_article
from ..services import zone_service
from ..memory.retrieval_engine import index_article
from ..agent.loop import AgentLoop
from .students import get_current_student_id

router = APIRouter(prefix="/api/articles", tags=["Agent·执行"])


class ArticleWithPinyin(BaseModel):
    id: int
    record_date: date
    topic: str
    content: str
    character_count: int
    source: str
    created_at: str
    paragraphs: list

    model_config = {"from_attributes": False}


class PinyinAnnotateRequest(BaseModel):
    text: str


@router.post("/pinyin", response_model=dict)
def annotate_with_pinyin(body: PinyinAnnotateRequest):
    """Annotate arbitrary text with accurate pypinyin."""
    return annotate_article(body.text)


@router.get("/{article_id}/pinyin")
def article_with_pinyin(article_id: int, db: Session = Depends(get_db)):
    """Get an existing article with pinyin annotation."""
    article = db.query(DailyArticle).filter(DailyArticle.id == article_id).first()
    if not article:
        # try by date
        article = db.query(DailyArticle).filter(DailyArticle.record_date == str(article_id)).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    annotated = annotate_article(article.content)

    # 系列信息
    series_info = {}
    if article.series_id:
        from ..models import ArticleSeries
        series = db.query(ArticleSeries).filter(ArticleSeries.id == article.series_id).first()
        if series:
            series_info = {
                "series_id": series.id,
                "chapter_number": article.chapter_number,
                "total_chapters": series.total_chapters,
            }

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
        **series_info,
    }


@router.post("/generate", response_model=dict)
def generate(body: ArticleGenerate, db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    """Agent 执行：决策+执行 → 自适应生成文章 → 存入记忆"""
    agent = AgentLoop(db, student_id)

    # 自动拉取记忆上下文（前端未传时后端自动获取）
    memory_ctx = body.memory_context
    if not memory_ctx:
        mem = get_memory_context(db, body.topic, body.characters)
        if mem.get("has_memory"):
            memory_ctx = mem.get("prompt_context", "")

    # Step 1: Agent 决策 + 执行 → 调用 DeepSeek 生成
    try:
        raw = agent.generate_article(
            body.topic, body.characters, body.min_chars, body.max_chars,
            body.category, memory_ctx,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI生成失败: {str(e)}")

    # Step 2: 拼音注音
    annotated = annotate_article(raw)
    total_chars = sum(len([t for t in p if t.get("pinyin")]) for p in annotated["paragraphs"])

    # Step 3: 字库分析 — 文章中每个字来自哪个区
    from ..models import TargetCharacter, ScoutCharacter, AllyCharacter, LostCharacter
    import re
    article_chars = list(dict.fromkeys(re.findall(r'[\u4e00-\u9fff]', raw)))
    in_target = {c for c in article_chars if db.query(TargetCharacter).filter(
        TargetCharacter.character == c, TargetCharacter.student_id == student_id).count()}
    in_scout = {c for c in article_chars if db.query(ScoutCharacter).filter(
        ScoutCharacter.character == c, ScoutCharacter.student_id == student_id).count()}
    in_ally = {c for c in article_chars if db.query(AllyCharacter).filter(
        AllyCharacter.character == c, AllyCharacter.student_id == student_id).count()}
    in_lost = {c for c in article_chars if db.query(LostCharacter).filter(
        LostCharacter.character == c, LostCharacter.student_id == student_id).count()}
    in_any = in_target | in_scout | in_ally | in_lost
    not_in_lib = [c for c in article_chars if c not in in_any]
    char_breakdown = {
        "total": len(article_chars),
        "from_target": sorted(in_target),
        "from_scout": sorted(in_scout),
        "from_ally": sorted(in_ally),
        "from_lost": sorted(in_lost),
        "not_in_any": sorted(not_in_lib),
    }

    # Step 4: 存入记忆
    article = agent.remember.save_article(
        body.record_date, body.topic, raw, total_chars, body.category,
    )

    # Step 5: 若有关联的好奇心事件，自动关联
    if body.curiosity_event_id:
        link_curiosity_article(db, body.curiosity_event_id, article.id)

    # 后台索引
    threading.Thread(target=index_article, args=(article.id, article.topic, article.content), daemon=True).start()

    return {
        "id": article.id, "record_date": article.record_date.isoformat(),
        "topic": article.topic, "content": article.content,
        "character_count": article.character_count,
        "source": article.source, "category": article.category,
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "image_url": None, "images": [],
        "paragraphs": annotated["paragraphs"],
        "char_breakdown": char_breakdown,
    }


@router.post("/{article_id}/generate-images", response_model=dict)
def generate_images(article_id: int, db: Session = Depends(get_db)):
    article = db.query(DailyArticle).filter(DailyArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    # Get number of paragraphs from content
    num_paragraphs = len([p for p in article.content.split('\n\n') if p.strip()])
    images = generate_article_images(article.topic, article.content, num_paragraphs)

    if images:
        article.images_json = images  # type: ignore[assignment]
        # Also set the first image as cover
        article.image_url = images[0]["url"]
        db.commit()
        db.refresh(article)

    return {
        "id": article.id,
        "images": article.images_json or [],
    }


@router.post("/", response_model=ArticleResponse)
def create_article(body: ArticleCreate, db: Session = Depends(get_db)):
    existing = db.query(DailyArticle).filter(DailyArticle.record_date == body.record_date).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"日期 {body.record_date} 已有文章，请使用更新接口")

    article = DailyArticle(
        record_date=body.record_date,
        topic=body.topic,
        content=body.content,
        character_count=len(body.content),
        source=body.source,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


@router.get("/", response_model=list[ArticleResponse])
def list_articles(db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    return db.query(DailyArticle).filter(DailyArticle.student_id == student_id).order_by(DailyArticle.record_date.desc()).all()


@router.get("/today", response_model=dict)
def get_today_article(db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    today = date.today()
    article = db.query(DailyArticle).filter(DailyArticle.record_date == today, DailyArticle.student_id == student_id).order_by(DailyArticle.id.desc()).first()
    if not article:
        return None

    annotated = annotate_article(article.content)
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
    }


@router.get("/{record_date}", response_model=dict)
def get_article_by_date(record_date: str, db: Session = Depends(get_db)):
    article = db.query(DailyArticle).filter(DailyArticle.record_date == record_date).first()
    if not article:
        raise HTTPException(status_code=404, detail=f"日期 {record_date} 没有文章")

    annotated = annotate_article(article.content)
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
    }


class ReviseRequest(BaseModel):
    suggestions: str


@router.post("/{article_id}/revise", response_model=dict)
def revise_article(article_id: int, body: ReviseRequest, db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    """根据修改建议回炉优化文章"""
    article = db.query(DailyArticle).filter(DailyArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    # Agent 执行：调用 DeepSeek 回炉修改
    agent = AgentLoop(db, student_id)
    revised = agent.revise_article(article.content, article.topic, body.suggestions)
    article.content = revised
    article.character_count = len(revised)
    db.commit()

    annotated = annotate_article(revised)
    return {
        "id": article.id,
        "record_date": article.record_date.isoformat(),
        "topic": article.topic,
        "content": revised,
        "character_count": article.character_count,
        "source": article.source,
        "category": article.category,
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "image_url": article.image_url,
        "images": article.images_json or [],
        "paragraphs": annotated["paragraphs"],
    }


# ===== 阅读状态 =====

class ReadStatusRequest(BaseModel):
    status: str  # 'reading' | 'read'
    read_count: int = 0
    total_count: int = 0


@router.post("/{article_id}/read-status")
def update_read_status(article_id: int, body: ReadStatusRequest,
                       db: Session = Depends(get_db),
                       student_id: int = Depends(get_current_student_id)):
    record = zone_service.update_read_status(
        db, article_id, student_id, body.status, body.read_count, body.total_count)

    # 文章读完 → 触发自动晋升
    result = {}
    if body.status == "read":
        result = zone_service.on_article_read(db, article_id, student_id)

    return {
        "id": record.id,
        "status": record.status,
        "read_paragraph_count": record.read_paragraph_count,
        "total_paragraph_count": record.total_paragraph_count,
        "promotion": result,
    }


@router.get("/{article_id}/read-status")
def get_read_status(article_id: int, db: Session = Depends(get_db),
                    student_id: int = Depends(get_current_student_id)):
    record = zone_service.get_read_status(db, article_id, student_id)
    if not record:
        return {"status": "unread"}
    return {
        "id": record.id, "article_id": record.article_id,
        "status": record.status,
        "read_paragraph_count": record.read_paragraph_count,
        "total_paragraph_count": record.total_paragraph_count,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "finished_at": record.finished_at.isoformat() if record.finished_at else None,
    }


@router.get("/read-statuses")
def batch_read_status(ids: str = "", db: Session = Depends(get_db),
                      student_id: int = Depends(get_current_student_id)):
    article_ids = [int(x) for x in ids.split(",") if x.strip()]
    if not article_ids:
        return {}
    result = zone_service.get_articles_read_status(db, article_ids, student_id)
    return result


@router.delete("/{article_id}")
def delete_article(article_id: int, db: Session = Depends(get_db)):
    record = db.query(DailyArticle).filter(DailyArticle.id == article_id).first()
    if record:
        db.delete(record)
        db.commit()
    return {"ok": True}


# ===== 文章系列 =====

@router.get("/series/{series_id}")
def get_series(series_id: int, db: Session = Depends(get_db)):
    """获取系列信息 + 全部章节列表"""
    series = db.query(ArticleSeries).filter(ArticleSeries.id == series_id).first()
    if not series:
        raise HTTPException(status_code=404, detail="系列不存在")

    chapters = db.query(DailyArticle).filter(
        DailyArticle.series_id == series_id
    ).order_by(DailyArticle.chapter_number.asc()).all()

    # 获取阅读状态
    from ..models import ArticleReadStatus
    chapter_list = []
    for ch in chapters:
        status_record = db.query(ArticleReadStatus).filter(
            ArticleReadStatus.article_id == ch.id,
            ArticleReadStatus.student_id == series.student_id,
        ).first()
        chapter_list.append({
            "id": ch.id,
            "chapter_number": ch.chapter_number,
            "title": ch.topic,
            "character_count": ch.character_count,
            "read_status": status_record.status if status_record else "unread",
        })

    return {
        "id": series.id,
        "topic": series.topic,
        "status": series.status,
        "total_chapters": series.total_chapters,
        "current_chapter": series.current_chapter,
        "chapter_titles": series.chapter_titles_json or [],
        "chapters": chapter_list,
    }


@router.get("/series/{series_id}/chapter/{chapter_number}")
def get_series_chapter(series_id: int, chapter_number: int, db: Session = Depends(get_db)):
    """获取系列中某一章的完整内容（带拼音）"""
    chapter = db.query(DailyArticle).filter(
        DailyArticle.series_id == series_id,
        DailyArticle.chapter_number == chapter_number,
    ).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    annotated = annotate_article(chapter.content)
    return {
        "id": chapter.id,
        "series_id": series_id,
        "chapter_number": chapter_number,
        "topic": chapter.topic,
        "content": chapter.content,
        "character_count": chapter.character_count,
        "paragraphs": annotated["paragraphs"],
    }
