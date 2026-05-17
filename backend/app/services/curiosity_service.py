import logging
from datetime import date

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, EDUCATION_CONFIG
from ..models import CuriosityEvent, DailyArticle, DailyCharacter, InterestEvolution, Student, ConversationSession, ConversationTurn, ArticleSeries
from .article_generator import (
    extract_characters_from_text,
    generate_article_with_pinyin,
    build_recent_chars_context,
    build_behavior_context,
    build_zone_context,
)
from .memory_service import get_memory_context
from .knowledge_base_service import build_kb_context

logger = logging.getLogger(__name__)


def auto_tag_question(raw_text: str) -> list[str]:
    """调用 DeepSeek 从孩子的问题中自动提取 2-3 个兴趣标签"""
    try:
        from openai import OpenAI
        import httpx
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            http_client=httpx.Client(timeout=15.0),
        )
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{
                "role": "user",
                "content": f"从以下6-8岁孩子的问题中提取2-3个兴趣标签。只返回标签名，用逗号分隔。\n问题：{raw_text}",
            }],
            temperature=0.3,
            max_tokens=50,
        )
        tags_str = resp.choices[0].message.content.strip()
        tags = [t.strip() for t in tags_str.replace("，", ",").split(",") if t.strip()]
        logger.info(f"auto_tag_question: '{raw_text[:30]}...' → tags={tags}")
        return tags[:3]
    except Exception as e:
        logger.warning(f"auto_tag_question failed: {e}")
        return []


def extract_tags_background(event_id: int):
    """后台任务：异步提取标签并更新事件 + 兴趣演化"""
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        event = db.query(CuriosityEvent).filter(CuriosityEvent.id == event_id).first()
        if not event:
            return
        tags = auto_tag_question(event.raw_text)
        if tags:
            event.tags_json = tags
            _update_interest_tags(db, tags, event.event_date)
            db.commit()
    except Exception as e:
        logger.error(f"extract_tags_background failed for event {event_id}: {e}")
        db.rollback()
    finally:
        db.close()


def create_event(
    db: Session,
    event_date: date,
    raw_text: str,
    keywords: list[str] | None = None,
    tags: list[str] | None = None,
    cleaned_text: str | None = None,
    parent_event_id: int | None = None,
    student_id: int = 1,
) -> CuriosityEvent:
    event = CuriosityEvent(
        student_id=student_id,
        event_date=event_date,
        raw_text=raw_text,
        cleaned_text=cleaned_text or raw_text,
        keywords_json=keywords or [],
        tags_json=tags or [],
        parent_event_id=parent_event_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    if tags:
        _update_interest_tags(db, tags, event_date)

    return event


def get_events(
    db: Session,
    answered: bool | None = None,
    tag: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CuriosityEvent]:
    q = db.query(CuriosityEvent).order_by(CuriosityEvent.event_date.desc(), CuriosityEvent.created_at.desc())
    if answered is not None:
        q = q.filter(CuriosityEvent.is_answered == answered)
    events = q.all()

    if tag:
        events = [e for e in events if e.tags_json and tag in e.tags_json]

    return events[offset : offset + limit]


def get_event_by_id(db: Session, event_id: int) -> CuriosityEvent | None:
    return db.query(CuriosityEvent).filter(CuriosityEvent.id == event_id).first()


def update_event(db: Session, event_id: int, **kwargs) -> CuriosityEvent | None:
    event = db.query(CuriosityEvent).filter(CuriosityEvent.id == event_id).first()
    if not event:
        return None

    for key, value in kwargs.items():
        if key == "keywords":
            setattr(event, "keywords_json", value)
        elif key == "tags":
            setattr(event, "tags_json", value)
        elif hasattr(event, key):
            setattr(event, key, value)

    db.commit()
    db.refresh(event)
    return event


def link_article(db: Session, event_id: int, article_id: int) -> CuriosityEvent | None:
    event = db.query(CuriosityEvent).filter(CuriosityEvent.id == event_id).first()
    if not event:
        return None
    event.linked_article_id = article_id
    event.is_answered = True
    db.commit()
    db.refresh(event)
    return event


def get_tags_summary(db: Session) -> dict[str, int]:
    events = db.query(CuriosityEvent.tags_json).all()
    counter: dict[str, int] = {}
    for (tags,) in events:
        if tags:
            for t in tags:
                counter[t] = counter.get(t, 0) + 1
    return dict(sorted(counter.items(), key=lambda x: x[1], reverse=True))


def delete_event(db: Session, event_id: int) -> bool:
    event = db.query(CuriosityEvent).filter(CuriosityEvent.id == event_id).first()
    if event:
        db.delete(event)
        db.commit()
        return True
    return False


# ===== Interest Evolution =====

def _update_interest_tags(db: Session, tags: list[str], event_date: date):
    for tag in tags:
        existing = db.query(InterestEvolution).filter(InterestEvolution.tag_name == tag).first()
        if existing:
            existing.mention_count += 1
            existing.last_mentioned_date = event_date
            recent_count = _count_recent_mentions(db, tag, 30)
            if recent_count >= 3:
                existing.trend = "rising"
                existing.intensity_score = min(1.0, recent_count / 10.0)
            elif recent_count == 0:
                existing.trend = "declining"
                existing.intensity_score = max(0.1, (existing.intensity_score or 0.5) - 0.2)
            else:
                existing.trend = "stable"
        else:
            record = InterestEvolution(
                tag_name=tag,
                first_mentioned_date=event_date,
                last_mentioned_date=event_date,
                mention_count=1,
                intensity_score=0.3,
                trend="rising",
            )
            db.add(record)
    db.commit()


def _count_recent_mentions(db: Session, tag: str, days: int) -> int:
    from datetime import timedelta
    threshold = date.today() - timedelta(days=days)
    events = db.query(CuriosityEvent).filter(
        CuriosityEvent.event_date >= threshold
    ).all()
    count = 0
    for e in events:
        if e.tags_json and tag in e.tags_json:
            count += 1
    return count


def get_interest_tags(
    db: Session,
    trend: str | None = None,
    min_intensity: float | None = None,
) -> list[InterestEvolution]:
    q = db.query(InterestEvolution).order_by(InterestEvolution.intensity_score.desc())
    if trend:
        q = q.filter(InterestEvolution.trend == trend)
    tags = q.all()
    if min_intensity is not None:
        tags = [t for t in tags if t.intensity_score and t.intensity_score >= min_intensity]
    return tags


def get_hot_interests(db: Session, limit: int = 5) -> list[InterestEvolution]:
    return (
        db.query(InterestEvolution)
        .order_by(InterestEvolution.intensity_score.desc())
        .limit(limit)
        .all()
    )


# ===== Answer Generation =====

def generate_answer_for_event(db: Session, event_id: int, student_id: int = 1) -> dict | None | str:
    """一键生成文章回答好奇心事件。

    流程: 提取生字 → 读取认知等级 → 记忆上下文 → AI生成 → 保存文章 → 关联事件 → 写入今日生字
    返回: {event, article} | None(not found) | str(conflict message)
    """
    event = db.query(CuriosityEvent).filter(
        CuriosityEvent.id == event_id,
        CuriosityEvent.student_id == student_id,
    ).first()
    if not event:
        return None
    if event.is_answered:
        return "该问题已经回答过了"

    # 读取学生认知等级，并检测问题中是否有高级词汇
    student = db.query(Student).filter(Student.id == student_id).first()
    base_level = student.cognition_level if student else 1
    effective_level = base_level

    raw_text = event.raw_text or ""
    has_advanced = any(kw in raw_text for kw in EDUCATION_CONFIG.ADVANCED_KEYWORDS)
    if has_advanced:
        effective_level = min(base_level + 1, EDUCATION_CONFIG.COGNITION_MAX_LEVEL)
        logger.info(f"Advanced keywords detected in '{raw_text[:30]}...', boosted cognition {base_level}→{effective_level}")

    topic = event.raw_text

    # 1. 从提问文本中提取汉字作为目标生字
    target_characters = extract_characters_from_text(topic)
    if not target_characters:
        return "未能从提问中提取到汉字"

    # 2. 自动拉取记忆上下文（当前没有显式的记忆上下文，在生成文章时自动获取）
    memory_ctx = get_memory_context(db, topic, target_characters)
    memory_ctx_str = memory_ctx.get("prompt_context", "") if memory_ctx else ""

    # 3. 自动拉取近期生字上下文、行为上下文、四区字库上下文
    recent_chars_ctx = build_recent_chars_context(db, days=5, student_id=student_id)
    behavior_ctx = build_behavior_context(db, days=7, student_id=student_id)
    zone_ctx = build_zone_context(db, student_id)

    # 3a. 知识库上下文
    event_tags = event.tags_json or []
    kb_ctx = build_kb_context(
        db, topic=topic, characters=target_characters,
        tags=event_tags, student_id=student_id
    )

    # 4. 调用 AI 生成文章
    try:
        article_data = generate_article_with_pinyin(
            topic=topic,
            characters=target_characters,
            min_chars=200,
            max_chars=500,
            category="answer",
            memory_context=memory_ctx_str,
            recent_chars_context=recent_chars_ctx,
            behavior_context=behavior_ctx,
            zone_context=zone_ctx,
            kb_context=kb_ctx,
            cognition_level=effective_level,
        )
    except Exception as e:
        logger.error(f"generate_answer_for_event: article generation failed: {e}")
        return f"文章生成失败: {e}"

    content = article_data.get("content", "")
    if not content:
        return "文章生成失败：AI返回了空内容"

    # 5. 保存文章到 DailyArticle
    today = date.today()
    article = DailyArticle(
        student_id=student_id,
        record_date=today,
        topic=topic,
        content=content,
        character_count=len(content),
        source="ai",
        category="answer",
    )
    db.add(article)
    db.commit()
    db.refresh(article)

    # 6. 自动关联事件到文章
    event.linked_article_id = article.id
    event.is_answered = True
    db.commit()
    db.refresh(event)

    # 7. 将生字写入今日 DailyCharacter（让首页阅读区立即可见）
    today_chars = set(
        row[0] for row in
        db.query(DailyCharacter.character)
        .filter(DailyCharacter.record_date == today, DailyCharacter.student_id == student_id)
        .all()
    )
    for ch in target_characters:
        if ch not in today_chars:
            db.add(DailyCharacter(
                student_id=student_id,
                record_date=today,
                character=ch,
                category="chinese",
            ))
    db.commit()

    # 8. 构建返回数据
    return {
        "event": {
            "id": event.id,
            "event_date": event.event_date,
            "raw_text": event.raw_text,
            "cleaned_text": event.cleaned_text,
            "keywords_json": event.keywords_json,
            "tags_json": event.tags_json,
            "is_answered": event.is_answered,
            "linked_article_id": event.linked_article_id,
            "parent_event_id": event.parent_event_id,
            "created_at": event.created_at,
        },
        "article": {
            "id": article.id,
            "record_date": str(article.record_date),
            "topic": article.topic,
            "content": article.content,
            "character_count": article.character_count,
            "source": article.source,
            "category": article.category,
            "created_at": str(article.created_at) if article.created_at else None,
            "paragraphs": article_data.get("paragraphs", []),
        },
    }


# ===== Smart Recommendation Engine =====

def recommend_topics(db: Session, student_id: int = 1, limit: int = 5) -> list[dict]:
    """综合推荐引擎：未回答问题 + 兴趣演化 + 四区字库 → Top N 推荐主题

    权重: 未回答问题(3) > 热门兴趣(2) > 字库匹配(1)
    """
    from ..models import TargetCharacter

    recommendations: list[dict] = []

    # 1. 未回答的问题（权重最高）
    unanswered = get_events(db, answered=False, limit=5)
    for e in unanswered:
        recommendations.append({
            "topic": e.raw_text[:60],
            "source": "question",
            "source_label": "未回答的问题",
            "priority": 3.0,
            "event_id": e.id,
            "tags": e.tags_json or [],
        })

    # 2. 热门兴趣
    hot_tags = get_hot_interests(db, limit=5)
    for t in hot_tags:
        score = float(t.intensity_score or 0.3) * 2.0
        recommendations.append({
            "topic": t.tag_name,
            "source": "interest",
            "source_label": "热门兴趣",
            "priority": score,
            "tag_name": t.tag_name,
            "mention_count": t.mention_count,
            "trend": t.trend,
        })

    # 3. 四区字库 — 匹配兴趣标签的生字优先
    target_chars = db.query(TargetCharacter).filter(
        TargetCharacter.student_id == student_id
    ).limit(20).all()

    if target_chars and hot_tags:
        tag_chars = {t.tag_name: [] for t in hot_tags[:3]}
        for tc in target_chars:
            tag_chars.setdefault("其他", []).append(tc.character)
        for tag_name, chars in tag_chars.items():
            if chars:
                recommendations.append({
                    "topic": f"学习关于{tag_name}的字",
                    "source": "character",
                    "source_label": "字库匹配",
                    "priority": 1.0,
                    "tag_name": tag_name,
                    "characters": chars[:5],
                })

    # 按优先级排序，去重 topic
    seen = set()
    unique: list[dict] = []
    for r in sorted(recommendations, key=lambda x: x["priority"], reverse=True):
        if r["topic"] not in seen:
            seen.add(r["topic"])
            unique.append(r)

    return unique[:limit]


# ===== 好奇心对话系统 =====

def start_conversation(db: Session, event_id: int, student_id: int = 1) -> dict:
    """基于好奇心事件开启对话，返回第一条引导回复"""
    event = db.query(CuriosityEvent).filter(
        CuriosityEvent.id == event_id,
    ).first()
    if not event:
        return {"error": "事件不存在"}
    if event.is_answered:
        return {"error": "该问题已经回答过了"}

    # 创建会话（使用事件的 student_id 保持一致）
    session_student_id = event.student_id if event.student_id else student_id
    session = ConversationSession(
        student_id=session_student_id,
        curiosity_event_id=event_id,
        status="active",
        turn_count=1,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # 生成第一条引导回复
    student = db.query(Student).filter(Student.id == student_id).first()
    base_level = student.cognition_level if student else 1
    has_advanced = any(kw in (event.raw_text or "") for kw in EDUCATION_CONFIG.ADVANCED_KEYWORDS)
    effective_level = min(base_level + 1, EDUCATION_CONFIG.COGNITION_MAX_LEVEL) if has_advanced else base_level

    reply = _generate_conversation_reply(db, session.id, event.raw_text, [], effective_level)

    # 保存初始回复到对话历史
    first_turn = ConversationTurn(session_id=session.id, role="assistant", content=reply)
    db.add(first_turn)
    db.commit()

    return {
        "session_id": session.id,
        "event": {
            "id": event.id,
            "raw_text": event.raw_text,
            "tags": event.tags_json or [],
        },
        "reply": reply,
        "turn_count": 1,
        "cognition_level": effective_level,
    }


def conversation_turn(db: Session, session_id: int, user_input: str, student_id: int = 1) -> dict:
    """处理孩子的新一轮输入，返回大模型回复"""
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
    ).first()
    if not session:
        return {"error": "会话不存在"}
    if session.status != "active":
        return {"error": "会话已结束"}

    # 保存用户输入（马上 flush 确保查询历史时可见）
    user_turn = ConversationTurn(session_id=session_id, role="user", content=user_input)
    db.add(user_turn)
    db.flush()

    # 获取对话历史（包含刚刚保存的用户输入）
    history = _get_conversation_history(db, session_id)

    # 获取初始问题
    event = db.query(CuriosityEvent).filter(CuriosityEvent.id == session.curiosity_event_id).first()
    topic = event.raw_text if event else ""

    # 获取认知等级
    student = db.query(Student).filter(Student.id == student_id).first()
    base_level = student.cognition_level if student else 1
    has_advanced = any(kw in user_input for kw in EDUCATION_CONFIG.ADVANCED_KEYWORDS)
    effective_level = min(base_level + 1, EDUCATION_CONFIG.COGNITION_MAX_LEVEL) if has_advanced else base_level

    # 生成回复
    reply = _generate_conversation_reply(db, session_id, topic, history, effective_level)

    # 保存助手的回复
    assistant_turn = ConversationTurn(session_id=session_id, role="assistant", content=reply)
    db.add(assistant_turn)
    session.turn_count = len(history) + 1
    db.commit()

    return {
        "session_id": session.id,
        "reply": reply,
        "turn_count": session.turn_count,
        "cognition_level": effective_level,
    }


def complete_conversation(db: Session, session_id: int, student_id: int = 1) -> dict:
    """结束对话，根据整个对话历史生成定制文章"""
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
    ).first()
    if not session:
        return {"error": "会话不存在"}
    if session.status == "completed" and session.final_article_id:
        return {"error": "会话已完成，文章已生成", "article_id": session.final_article_id}

    history = _get_conversation_history(db, session_id)
    if len(history) < 1:
        return {"error": "对话轮次不足"}

    event = db.query(CuriosityEvent).filter(CuriosityEvent.id == session.curiosity_event_id).first()
    topic = event.raw_text if event else ""

    # 获取认知等级
    student = db.query(Student).filter(Student.id == student_id).first()
    base_level = student.cognition_level if student else 1

    # 构建对话历史文本
    history_text = "\n".join([f"{'俊宜' if t['role'] == 'user' else '老师'}: {t['content']}" for t in history])

    # 提取生字
    from .article_generator import extract_characters_from_text
    all_text = topic + " " + " ".join([t['content'] for t in history])
    chars = extract_characters_from_text(all_text)[:8]

    # 调用 DeepSeek：先分析对话中的知识边界，再生成定制文章
    try:
        from openai import OpenAI
        import httpx
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=httpx.Client(timeout=60.0))

        cognition_guidance = EDUCATION_CONFIG.COGNITION_PROMPTS.get(
            min(base_level, EDUCATION_CONFIG.COGNITION_MAX_LEVEL),
            EDUCATION_CONFIG.COGNITION_PROMPTS[1]
        )

        prompt = f"""写一篇科普文章。以下是你要覆盖的素材。

【对话记录】
{history_text}

【写作要求】
- 标题：{topic}
- 全文450-600字，分4-5段，每段100-150字
- 段落1：回应用问题。解释基本概念，用比喻
- 段落2：深入原理。对话中孩子追问最多的方向
- 段落3：纠正误区。如果对话中孩子理解错了，温和纠正
- 段落4：延伸知识。对话中老师提到但孩子没追问的内容
- 段落5：总结。用"俊宜，今天你知道了……"收尾
- 融入生字：{'、'.join(chars)}
- 请注意：这段对话的参与者是一位老师和一个7岁孩子。老师用简单语言解释复杂概念。但你写的文章不需要刻意模仿'儿童腔'，正常写科普即可。"""

        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": "写一篇450-600字的科普文章。要有结构（段落分明）、有深度、有逻辑。不要用拼音，不要用英文。写不够450字就是不合格。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=3000,
        )
        content = resp.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"complete_conversation: article generation failed: {e}")
        return {"error": f"文章生成失败: {e}"}

    # 保存文章
    from datetime import date
    from .pinyin_service import annotate_text
    article = DailyArticle(
        student_id=student_id,
        record_date=date.today(),
        topic=topic,
        content=content,
        character_count=len(content),
        source="ai",
        category="answer",
    )
    db.add(article)
    db.commit()
    db.refresh(article)

    # 关联事件
    event.is_answered = True
    event.linked_article_id = article.id

    # 更新会话
    session.status = "completed"
    session.final_article_id = article.id
    db.commit()

    # 拼音标注
    paragraphs = annotate_text(content)

    return {
        "session_id": session.id,
        "article": {
            "id": article.id,
            "record_date": str(article.record_date),
            "topic": article.topic,
            "content": article.content,
            "character_count": article.character_count,
            "paragraphs": paragraphs,
        },
        "turn_count": session.turn_count,
    }


# ===== 对话策略核心 =====

def _generate_conversation_reply(db: Session, session_id: int, topic: str, history: list[dict], cognition_level: int) -> str:
    """核心对话生成器 — 根据认知等级和对话历史生成回复"""
    try:
        from openai import OpenAI
        import httpx
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=httpx.Client(timeout=30.0))

        cognition_guidance = EDUCATION_CONFIG.COGNITION_PROMPTS.get(
            min(cognition_level, EDUCATION_CONFIG.COGNITION_MAX_LEVEL),
            EDUCATION_CONFIG.COGNITION_PROMPTS[1]
        )

        history_text = ""
        if history:
            history_text = "对话历史：\n" + "\n".join([
                f"俊宜: {t['content']}" if t['role'] == 'user' else f"老师: {t['content']}"
                for t in history[-6:]  # 只取最近6轮
            ])

        first_turn = len(history) == 0

        if first_turn:
            prompt = f"""俊宜问了一个问题：「{topic}」

你是俊宜的科普老师。请给他一个有启发的回答，要求：
1. {cognition_guidance}
2. 回答最后，反问一个引导性的问题，鼓励他继续思考。比如"你知道星星为什么会发光吗？"
3. 每句话不超过20字，多举例，少抽象定义
4. 总共100-200字"""
        else:
            # 对话继续：上面是完整的对话记录，最后一条永远是俊宜说的
            prompt = f"""初始问题：「{topic}」

对话记录（最后一条是俊宜刚说的）：
{history_text}

上面是你们正在进行的对话。你是俊宜的科普老师，请回复俊宜**刚刚说的最后一句话**。

对话规则：
1. 必须先回应俊宜最新那句话——不能忽略它、不能重复之前的开场白
2. 如果他说错了（比如"星星不发光是反射的"），温和地纠正并解释正确的原理
3. 如果他用了专业术语，用更深的科学知识回应他
4. 记住之前聊过什么，可以自然地引用（"像我们刚才说的核聚变..."）
5. {cognition_guidance}
6. 偶尔反问引导他深入思考，但不是每次都必须问
7. 不超过150字，保持对话的节奏感"""

        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600,
        )
        reply = resp.choices[0].message.content.strip()
        logger.info(f"_generate_conversation_reply: session={session_id}, turn={len(history)}, level={cognition_level}, reply={len(reply)} chars")
        return reply

    except Exception as e:
        logger.error(f"_generate_conversation_reply failed: {e}")
        return "这个问题真棒！让我想想怎么回答你...你能再多说一点你觉得黑洞是什么吗？"


def _get_conversation_history(db: Session, session_id: int) -> list[dict]:
    """获取会话的对话历史"""
    turns = db.query(ConversationTurn).filter(
        ConversationTurn.session_id == session_id
    ).order_by(ConversationTurn.created_at.asc()).all()
    return [{"role": t.role, "content": t.content} for t in turns]


# ===== LangGraph 状态图 API =====

def run_answer_one_shot(event_id: int, student_id: int = 1) -> dict:
    """图模式 one_shot: 直接生成回答文章"""
    from ..agent.curiosity_graph import get_curiosity_graph
    graph = get_curiosity_graph()
    config = {"configurable": {"thread_id": f"curiosity_{event_id}"}}

    result = graph.invoke({
        "event_id": event_id,
        "student_id": student_id,
        "mode": "one_shot",
    }, config)

    if result.get("error"):
        return {"error": result["error"]}
    return {
        "article_id": result.get("article_id"),
        "article_content": result.get("article_content", ""),
        "paragraphs": result.get("paragraphs", []),
    }


def run_conversation_start(event_id: int, student_id: int = 1) -> dict:
    """图模式 conversation: 开启对话"""
    from ..agent.curiosity_graph import get_curiosity_graph
    graph = get_curiosity_graph()
    config = {"configurable": {"thread_id": f"curiosity_{event_id}"}}

    result = graph.invoke({
        "event_id": event_id,
        "student_id": student_id,
        "mode": "conversation",
    }, config)

    if result.get("error"):
        return {"error": result["error"]}
    return {
        "session_id": result.get("session_id"),
        "reply": result["conversation_history"][-1]["content"] if result.get("conversation_history") else "",
        "cognition_level": result.get("effective_cognition", 1),
    }


def run_conversation_turn(event_id: int, user_input: str, student_id: int = 1) -> dict:
    """图模式 conversation: 处理新一轮输入"""
    from ..agent.curiosity_graph import get_curiosity_graph
    graph = get_curiosity_graph()
    config = {"configurable": {"thread_id": f"curiosity_{event_id}"}}

    result = graph.invoke({
        "event_id": event_id,
        "student_id": student_id,
        "mode": "conversation",
        "last_child_input": user_input,
    }, config)

    if result.get("error"):
        return {"error": result["error"]}
    history = result.get("conversation_history", [])
    return {
        "session_id": result.get("session_id"),
        "reply": history[-1]["content"] if history else "",
        "cognition_level": result.get("effective_cognition", 1),
    }


def run_conversation_generate(event_id: int, student_id: int = 1) -> dict:
    """图模式 conversation: 结束对话，生成文章"""
    from ..agent.curiosity_graph import get_curiosity_graph
    graph = get_curiosity_graph()
    config = {"configurable": {"thread_id": f"curiosity_{event_id}"}}

    result = graph.invoke({
        "event_id": event_id,
        "student_id": student_id,
        "mode": "conversation",
    }, config)

    if result.get("error"):
        return {"error": result["error"]}
    return {
        "article_id": result.get("article_id"),
        "article_content": result.get("article_content", ""),
        "paragraphs": result.get("paragraphs", []),
    }


def run_series_start(event_id: int, student_id: int = 1) -> dict:
    """图模式 series: 拆解主题 + 生成第一章（不用 graph checkpoint，单次 invoke）"""
    from ..agent.curiosity_graph import get_curiosity_graph
    import uuid
    graph = get_curiosity_graph()
    # 每次用新 thread_id，避免 checkpoint 污染
    config = {"configurable": {"thread_id": f"series_start_{event_id}_{uuid.uuid4().hex[:6]}"}}

    # 先创建系列记录
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        event = db.query(CuriosityEvent).filter(CuriosityEvent.id == event_id).first()
        topic = event.raw_text if event else ""
        series = ArticleSeries(
            student_id=student_id, topic=topic,
            curiosity_event_id=event_id,
            status="in_progress", current_chapter=0,
        )
        db.add(series)
        db.commit()
        db.refresh(series)
        series_id = series.id
    finally:
        db.close()

    result = graph.invoke({
        "event_id": event_id,
        "student_id": student_id,
        "mode": "series",
        "series_id": series_id,
    }, config)

    if result.get("error"):
        return {"error": result["error"]}

    # 更新系列记录
    db = SessionLocal()
    try:
        series = db.query(ArticleSeries).filter(ArticleSeries.id == series_id).first()
        if series:
            series.chapter_titles_json = result.get("chapter_titles", [])
            series.total_chapters = len(result.get("chapter_titles", []))
            series.current_chapter = 1
            db.commit()
    finally:
        db.close()

    chapters = result.get("chapter_titles", [])
    return {
        "series_id": series_id,
        "total_chapters": len(chapters),
        "current_chapter": 1,
        "chapter_titles": chapters,
        "article_id": result.get("article_id"),
        "article_content": result.get("article_content", ""),
        "paragraphs": result.get("paragraphs", []),
    }


def run_series_next(event_id: int, want_next: bool, student_id: int = 1) -> dict:
    """图模式 series: 下一章 / 放弃（每次独立 invoke，DB 是状态源）"""
    from ..database import SessionLocal as SL
    from ..models import ArticleSeries as AS
    import uuid

    # 先从 DB 读取当前状态
    db = SL()
    try:
        s = db.query(AS).filter(
            AS.curiosity_event_id == event_id,
            AS.student_id == student_id,
        ).order_by(AS.id.desc()).first()
        if not s:
            return {"error": "未找到系列"}
        series_id = s.id
        db_chapter = s.current_chapter  # 已生成到第几章
        db_total = s.total_chapters
        db_titles = s.chapter_titles_json or []
        db_topic = s.topic

        if not want_next:
            s.status = "abandoned"
            db.commit()
            return {"status": "abandoned", "series_id": series_id}
    finally:
        db.close()

    if db_chapter >= db_total:
        return {"series_id": series_id, "current_chapter": db_chapter,
                "total_chapters": db_total, "completed": True}

    # 用单次 graph invoke 生成下一章
    from ..agent.curiosity_graph import get_curiosity_graph
    graph = get_curiosity_graph()
    config = {"configurable": {"thread_id": f"series_ch_{series_id}_{db_chapter}_{uuid.uuid4().hex[:6]}"}}

    result = graph.invoke({
        "event_id": event_id,
        "student_id": student_id,
        "mode": "series",
        "series_id": series_id,
        "raw_text": db_topic,
        "current_chapter": db_chapter,  # DB 是权威来源
        "chapter_titles": db_titles,
        "child_wants_next_chapter": True,
    }, config)

    if result.get("error"):
        return {"error": result["error"]}

    # 更新 DB
    new_chapter = db_chapter + 1
    is_done = new_chapter >= db_total
    db2 = SL()
    try:
        series = db2.query(AS).filter(AS.id == series_id).first()
        if series:
            series.current_chapter = new_chapter
            if is_done:
                series.status = "completed"
            db2.commit()
    finally:
        db2.close()

    return {
        "series_id": series_id,
        "article_id": result.get("article_id"),
        "article_content": result.get("article_content", ""),
        "paragraphs": result.get("paragraphs", []),
        "current_chapter": new_chapter,
        "total_chapters": db_total,
        "completed": is_done,
    }
