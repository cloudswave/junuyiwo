from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import EDUCATION_CONFIG
from ..database import get_db
from ..models import Student, DifficultyFeedback
from ..schemas import (
    CuriosityEventCreate,
    CuriosityEventUpdate,
    CuriosityEventResponse,
    CuriosityListResponse,
    InterestEvolutionResponse,
)
from ..services.curiosity_service import (
    create_event,
    get_events,
    get_event_by_id,
    update_event,
    link_article,
    get_tags_summary,
    delete_event,
    get_interest_tags,
    get_hot_interests,
    generate_answer_for_event,
    extract_tags_background,
    recommend_topics,
    start_conversation,
    conversation_turn,
    complete_conversation,
    run_answer_one_shot,
    run_conversation_start,
    run_conversation_turn,
    run_conversation_generate,
    run_series_start,
    run_series_next,
)
from ..services.asr_service import recognize_text, is_configured as asr_configured
from .students import get_current_student_id

router = APIRouter(prefix="/api/curiosity", tags=["好奇心管理"])


@router.post("/events", response_model=CuriosityEventResponse)
def create_curiosity_event(
    body: CuriosityEventCreate,
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    return create_event(
        db,
        event_date=body.event_date,
        raw_text=body.raw_text,
        keywords=body.keywords,
        tags=body.tags,
        cleaned_text=body.cleaned_text,
        parent_event_id=body.parent_event_id,
        student_id=student_id,
    )


@router.post("/voice-question", response_model=CuriosityEventResponse)
async def voice_question(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """语音提问：接收录音文件 → ASR识别 → 创建好奇心事件 → 异步提取标签"""
    if not asr_configured():
        raise HTTPException(
            status_code=503,
            detail="语音识别服务未配置。请设置 XFYUN_APP_ID / XFYUN_API_KEY / XFYUN_API_SECRET",
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="录音文件为空")

    try:
        recognized_text = await recognize_text(audio_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音识别失败: {e}")

    if not recognized_text or not recognized_text.strip():
        raise HTTPException(status_code=422, detail="未能识别到有效文本")

    # 创建好奇心事件（同步，快速返回）
    event = create_event(
        db,
        event_date=date.today(),
        raw_text=recognized_text.strip(),
        tags=[],
        cleaned_text=recognized_text.strip(),
        student_id=student_id,
    )

    # 后台异步提取标签
    background_tasks.add_task(extract_tags_background, event.id)

    return event


@router.get("/events", response_model=CuriosityListResponse)
def list_events(
    answered: bool | None = Query(None, description="筛选已回答/未回答"),
    tag: str | None = Query(None, description="按标签筛选"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    items = get_events(db, answered=answered, tag=tag, limit=limit, offset=offset)
    tags = get_tags_summary(db)
    unanswered_count = sum(1 for e in get_events(db, answered=False) if not tag or (e.tags_json and tag in e.tags_json))
    return {
        "total": len(items),
        "unanswered": unanswered_count,
        "items": items,
        "tags_summary": tags,
    }


@router.get("/events/{event_id}", response_model=CuriosityEventResponse)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = get_event_by_id(db, event_id)
    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="事件不存在")
    return event


@router.patch("/events/{event_id}", response_model=CuriosityEventResponse)
def update_curiosity_event(event_id: int, body: CuriosityEventUpdate, db: Session = Depends(get_db)):
    payload = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    event = update_event(db, event_id, **payload)
    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="事件不存在")
    return event


@router.post("/events/{event_id}/link-article/{article_id}", response_model=CuriosityEventResponse)
def link_event_to_article(event_id: int, article_id: int, db: Session = Depends(get_db)):
    event = link_article(db, event_id, article_id)
    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="事件不存在")
    return event


@router.delete("/events/{event_id}")
def remove_event(event_id: int, db: Session = Depends(get_db)):
    ok = delete_event(db, event_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="事件不存在")
    return {"ok": True}


@router.get("/events/{event_id}/thread")
def get_thread(event_id: int, db: Session = Depends(get_db)):
    """Get a question + all follow-up questions (thread)."""
    event = get_event_by_id(db, event_id)
    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="事件不存在")

    root_id = event_id
    current = event
    while current.parent_event_id:
        current = get_event_by_id(db, current.parent_event_id)
        if current:
            root_id = current.id

    thread = [e for e in get_events(db, limit=200)
              if e.id == root_id or e.parent_event_id in {root_id} | {e2.id for e2 in get_events(db) if e2.parent_event_id == root_id}]

    thread_ids = {root_id}
    children = [e for e in get_events(db, limit=200) if e.parent_event_id == root_id]
    thread_ids.update(e.id for e in children)
    for child in children:
        grandchildren = [e for e in get_events(db, limit=200) if e.parent_event_id == child.id]
        thread_ids.update(e.id for e in grandchildren)

    return [e for e in get_events(db, limit=200) if e.id in thread_ids]


# ===== Answer Generation =====

class GenerateAnswerResponse(BaseModel):
    event: CuriosityEventResponse
    article: dict


@router.post("/events/{event_id}/generate-answer", response_model=GenerateAnswerResponse)
def generate_answer(
    event_id: int,
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """一键生成文章回答问题：提取生字 → 记忆上下文 → AI生成 → 保存 → 关联 → 写入今日生字"""
    result = generate_answer_for_event(db, event_id, student_id)
    if not result:
        raise HTTPException(status_code=404, detail="事件不存在")
    if isinstance(result, str):
        raise HTTPException(status_code=409, detail=result)
    return result


@router.get("/suggestions")
def get_topic_suggestions(db: Session = Depends(get_db)):
    """获取好奇心驱动的主题建议，供文章生成页面使用"""
    unanswered = get_events(db, answered=False, limit=5)
    hot = get_hot_interests(db, limit=5)
    declining = get_interest_tags(db, trend="declining", min_intensity=0.2)

    return {
        "from_unanswered": [
            {"id": e.id, "event_date": e.event_date.isoformat(), "raw_text": e.raw_text, "tags": e.tags_json or []}
            for e in unanswered
        ],
        "from_hot_interests": [
            {"tag_name": t.tag_name, "mention_count": t.mention_count, "intensity_score": t.intensity_score}
            for t in hot
        ],
        "from_declining": [
            {"tag_name": t.tag_name, "mention_count": t.mention_count}
            for t in declining[:3]
        ],
    }


@router.get("/badge")
def get_badge(db: Session = Depends(get_db)):
    """轻量查询未回答的好奇心问题数"""
    unanswered = get_events(db, answered=False)
    return {"unanswered_count": len(unanswered)}


# ===== Difficulty Feedback =====

class DifficultyFeedbackRequest(BaseModel):
    article_id: int
    feedback: str  # "too_easy" | "too_hard"
    topic: str = ""


@router.post("/feedback")
def submit_difficulty_feedback(
    body: DifficultyFeedbackRequest,
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """提交文章难度反馈，用于校准认知等级"""
    feedback = DifficultyFeedback(
        student_id=student_id,
        article_id=body.article_id,
        feedback=body.feedback,
        topic=body.topic,
    )
    db.add(feedback)
    db.commit()

    # 检查是否需要升降认知等级
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {"ok": True, "action": "none"}

    # 统计最近同类反馈
    recent = db.query(DifficultyFeedback).filter(
        DifficultyFeedback.student_id == student_id,
        DifficultyFeedback.feedback == body.feedback,
    ).order_by(DifficultyFeedback.created_at.desc()).limit(
        EDUCATION_CONFIG.COGNITION_UPGRADE_TOO_EASY_COUNT
    ).all()

    action = "none"
    if len(recent) >= EDUCATION_CONFIG.COGNITION_UPGRADE_TOO_EASY_COUNT:
        if body.feedback == "too_easy" and student.cognition_level < EDUCATION_CONFIG.COGNITION_MAX_LEVEL:
            student.cognition_level += 1
            action = f"upgraded_to_{student.cognition_level}"
        elif body.feedback == "too_hard" and student.cognition_level > 1:
            student.cognition_level -= 1
            action = f"downgraded_to_{student.cognition_level}"
        db.commit()

    return {"ok": True, "action": action, "current_level": student.cognition_level}


# ===== Interest Evolution =====

@router.get("/interests", response_model=list[InterestEvolutionResponse])
def list_interests(
    trend: str | None = Query(None, description="筛选趋势: rising/stable/declining"),
    min_intensity: float | None = Query(None, ge=0, le=1, description="最低兴趣强度"),
    db: Session = Depends(get_db),
):
    return get_interest_tags(db, trend=trend, min_intensity=min_intensity)


@router.get("/interests/hot", response_model=list[InterestEvolutionResponse])
def hot_interests(limit: int = Query(5, ge=1, le=20), db: Session = Depends(get_db)):
    return get_hot_interests(db, limit=limit)


@router.get("/recommend")
def recommend(
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """综合推荐：未回答问题 + 兴趣演化 + 字库匹配 → 今日推荐主题"""
    return recommend_topics(db, student_id=student_id, limit=limit)


# ===== 好奇心对话系统 =====

class ConversationTurnRequest(BaseModel):
    session_id: int
    user_input: str


@router.post("/conversation/start")
def start_conversation_endpoint(
    event_id: int = Query(..., description="好奇心事件ID"),
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """基于好奇心事件开启对话，返回第一条引导回复"""
    result = start_conversation(db, event_id, student_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/conversation/turn")
def conversation_turn_endpoint(
    body: ConversationTurnRequest,
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """处理孩子的新一轮输入，返回大模型回复"""
    result = conversation_turn(db, body.session_id, body.user_input, student_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/conversation/generate-article")
def complete_conversation_endpoint(
    session_id: int = Query(..., description="会话ID"),
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    """结束对话，根据整个对话历史生成定制文章"""
    result = complete_conversation(db, session_id, student_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ===== LangGraph 状态图 API — 统一答案生成 =====

@router.post("/answer/{event_id}")
def answer_one_shot(
    event_id: int,
    student_id: int = Depends(get_current_student_id),
):
    """图模式 one_shot: 直接生成回答文章"""
    result = run_answer_one_shot(event_id, student_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/answer/{event_id}/conversation/start")
def answer_conversation_start(
    event_id: int,
    student_id: int = Depends(get_current_student_id),
):
    """图模式 conversation: 开启对话"""
    result = run_conversation_start(event_id, student_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/answer/{event_id}/conversation/turn")
def answer_conversation_turn(
    event_id: int,
    body: ConversationTurnRequest,
    student_id: int = Depends(get_current_student_id),
):
    """图模式 conversation: 处理新一轮输入"""
    result = run_conversation_turn(event_id, body.user_input, student_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/answer/{event_id}/conversation/generate")
def answer_conversation_generate(
    event_id: int,
    student_id: int = Depends(get_current_student_id),
):
    """图模式 conversation: 结束对话，生成文章"""
    result = run_conversation_generate(event_id, student_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class SeriesNextRequest(BaseModel):
    want_next: bool = True


@router.post("/answer/{event_id}/series/start")
def answer_series_start(
    event_id: int,
    student_id: int = Depends(get_current_student_id),
):
    """图模式 series: 拆解主题 + 生成第一章"""
    result = run_series_start(event_id, student_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/answer/{event_id}/series/next")
def answer_series_next(
    event_id: int,
    body: SeriesNextRequest,
    student_id: int = Depends(get_current_student_id),
):
    """图模式 series: 下一章 / 放弃"""
    result = run_series_next(event_id, body.want_next, student_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
