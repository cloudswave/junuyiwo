"""知识库路由 — 校内教材知识 + 校外科普知识管理"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import KnowledgeEntry, StudentTextbookConfig
from ..schemas import KnowledgeEntryResponse
from ..services.knowledge_base_service import (
    search_knowledge_base,
    search_by_subject,
    get_school_entries,
    get_extracurricular_by_tags,
    build_kb_context,
    auto_generate_entry,
    auto_generate_for_hot_tags,
    get_or_create_config,
)
from .students import get_current_student_id

router = APIRouter(prefix="/api/knowledge-base", tags=["知识库"])


class TextbookSetupRequest(BaseModel):
    textbook_version: str = "人教版"
    current_grade: str = "grade_1"
    current_semester: str = "second"


class AutoGenerateRequest(BaseModel):
    tag_name: str


class ManualEntryRequest(BaseModel):
    subject: str
    content: str


# ===== 学生配置 =====

@router.get("/config")
def get_config(
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """获取学生的教材配置（首次使用时为空）"""
    config = db.query(StudentTextbookConfig).filter(
        StudentTextbookConfig.student_id == student_id
    ).first()
    if not config:
        return {"configured": False}
    return {
        "configured": True,
        "id": config.id,
        "textbook_version": config.textbook_version,
        "current_grade": config.current_grade,
        "current_semester": config.current_semester,
    }


@router.post("/config")
def setup_textbook(
    body: TextbookSetupRequest,
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """首次设置或更新教材配置"""
    config = get_or_create_config(
        db,
        student_id=student_id,
        textbook_version=body.textbook_version,
        current_grade=body.current_grade,
        current_semester=body.current_semester,
    )
    return {
        "ok": True,
        "textbook_version": config.textbook_version,
        "current_grade": config.current_grade,
        "current_semester": config.current_semester,
    }


# ===== 检索 =====

@router.get("/search", response_model=list[KnowledgeEntryResponse])
def search(
    q: str = Query("", description="搜索关键词"),
    tags: str = Query("", description="兴趣标签，逗号分隔"),
    grade_level: str | None = Query(None, description="年级过滤"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """多策略检索知识库"""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    return search_knowledge_base(db, query=q, tags=tag_list, grade_level=grade_level, student_id=student_id, limit=limit)


@router.get("/school", response_model=list[KnowledgeEntryResponse])
def school_entries(
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """获取校内教材知识条目"""
    return get_school_entries(db, student_id)


@router.get("/extracurricular", response_model=list[KnowledgeEntryResponse])
def extracurricular_entries(
    tags: str = Query("", description="兴趣标签，逗号分隔"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """获取课外科普知识条目"""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    return get_extracurricular_by_tags(db, tags=tag_list, limit=limit)


@router.get("/context")
def kb_context(
    topic: str = Query(""),
    characters: str = Query(""),
    tags: str = Query(""),
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """构建知识库上下文字符串（供文章生成调用）"""
    char_list = list(set(characters)) if characters else []
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    ctx = build_kb_context(db, topic=topic, characters=char_list, tags=tag_list, student_id=student_id)
    return {"context": ctx, "has_knowledge": len(ctx) > 0}


# ===== 自动生成 =====

@router.post("/auto-generate")
def auto_generate(
    body: AutoGenerateRequest,
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """根据兴趣标签自动生成课外科普知识"""
    entry = auto_generate_entry(db, tag_name=body.tag_name, student_id=0)
    if not entry:
        raise HTTPException(status_code=500, detail="自动生成失败")
    return {
        "id": entry.id,
        "title": entry.title,
        "content": entry.content,
        "subject": entry.subject,
    }


@router.post("/auto-generate-hot")
def auto_generate_hot(
    top_n: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """扫描热门兴趣标签，自动生成课外知识（可定时调用）"""
    count = auto_generate_for_hot_tags(db, top_n=top_n)
    return {"generated": count}


# ===== 管理 =====

@router.get("/entries", response_model=list[KnowledgeEntryResponse])
def list_entries(
    category: str | None = Query(None),
    subject: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """知识库条目列表"""
    q = db.query(KnowledgeEntry)
    if category:
        q = q.filter(KnowledgeEntry.category == category)
    if subject:
        q = q.filter(KnowledgeEntry.subject == subject)
    return q.order_by(KnowledgeEntry.grade_level.desc(), KnowledgeEntry.lesson.asc()).limit(limit).all()


@router.get("/entries/{entry_id}", response_model=KnowledgeEntryResponse)
def get_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    return entry


@router.post("/entries/manual", response_model=KnowledgeEntryResponse)
def create_manual_entry(
    body: ManualEntryRequest,
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """手动录入课外科普知识"""
    entry = KnowledgeEntry(
        student_id=student_id,
        category="extracurricular",
        subject=body.subject,
        title=f"科普：{body.subject}",
        content=body.content,
        keywords_json=[body.subject],
        source="manual",
        auto_approved=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/entries/{entry_id}/approve")
def toggle_approve(entry_id: int, approved: bool = Query(True), db: Session = Depends(get_db)):
    """切换条目的审核状态"""
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    entry.auto_approved = approved
    db.commit()
    return {"ok": True, "approved": approved}
