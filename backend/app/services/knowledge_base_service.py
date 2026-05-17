"""知识库服务 — 校内教材知识 + 校外科普知识的检索、生成、回哺"""
import logging
import re
from datetime import date

from sqlalchemy.orm import Session

from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from ..models import (
    KnowledgeEntry,
    StudentTextbookConfig,
    DailyArticle,
    InterestEvolution,
    TargetCharacter,
)

logger = logging.getLogger(__name__)


# ===== 检索 =====

def search_knowledge_base(
    db: Session,
    query: str = "",
    tags: list[str] | None = None,
    grade_level: str | None = None,
    student_id: int | None = None,
    limit: int = 5,
) -> list[KnowledgeEntry]:
    """多策略检索：关键词匹配 + 标签匹配 + 年级过滤"""
    tags = tags or []

    # Base query: 系统共享(0) + 本学生专属
    base = db.query(KnowledgeEntry)
    if student_id is not None:
        base = base.filter(
            KnowledgeEntry.student_id.in_([0, student_id])
        )

    # 年级过滤：只取不高于指定年级的条目
    if grade_level:
        grade_priority = _grade_order(grade_level)
        rows = base.all()
        rows = [r for r in rows if _grade_order(r.grade_level) <= grade_priority]
    else:
        rows = base.all()

    matches: list[tuple[KnowledgeEntry, float]] = []

    # 提取 query 中的中文关键词
    query_keywords = set(re.findall(r'[一-鿿]', query)) if query else set()

    for entry in rows:
        score = 0.0

        # 关键词匹配（汉字出现在 keywords 或 content 中）
        entry_keywords = set(entry.keywords_json or [])
        kw_hits = len(query_keywords & entry_keywords)
        if kw_hits > 0:
            score += kw_hits * 3.0

        # 内容匹配（query 中的词出现在 title 或 content 中）
        for kw in query_keywords:
            if kw in entry.title:
                score += 2.0
            if kw in entry.content:
                score += 1.0

        # 标签匹配
        if tags:
            for tag in tags:
                if tag == entry.subject or tag in entry.title:
                    score += 5.0

        # 加权：系统共享优先，使用次数高的优先
        if entry.student_id == 0:
            score += 1.0
        score += entry.used_count * 0.5

        if score > 0:
            matches.append((entry, score))

    # 按分数降序
    matches.sort(key=lambda x: x[1], reverse=True)

    # 更新 used_count
    for entry, _ in matches[:limit]:
        entry.used_count += 1
    db.commit()

    return [e for e, _ in matches[:limit]]


def search_by_subject(
    db: Session,
    subject: str,
    grade_level: str | None = None,
    limit: int = 10,
) -> list[KnowledgeEntry]:
    """按学科检索知识条目"""
    q = db.query(KnowledgeEntry).filter(KnowledgeEntry.subject == subject)
    if grade_level:
        q = q.filter(KnowledgeEntry.grade_level == grade_level)
    return q.order_by(KnowledgeEntry.lesson.asc()).limit(limit).all()


def get_school_entries(
    db: Session,
    student_id: int,
) -> list[KnowledgeEntry]:
    """获取当前学生的校内知识（根据 StudentTextbookConfig）"""
    config = db.query(StudentTextbookConfig).filter(
        StudentTextbookConfig.student_id == student_id
    ).first()
    if not config:
        # 默认：人教版一年级下册
        grade = "grade_1_second"
        version = "人教版"
    else:
        grade = f"{config.current_grade}_{config.current_semester}"
        version = config.textbook_version

    return db.query(KnowledgeEntry).filter(
        KnowledgeEntry.category == "school",
        KnowledgeEntry.student_id == 0,  # 系统共享
        KnowledgeEntry.textbook_version == version,
        KnowledgeEntry.grade_level <= grade,  # 包含已学学期
    ).order_by(KnowledgeEntry.grade_level.desc(), KnowledgeEntry.lesson.asc()).all()


def get_extracurricular_by_tags(
    db: Session,
    tags: list[str],
    limit: int = 10,
) -> list[KnowledgeEntry]:
    """获取与兴趣标签匹配的课外知识"""
    return db.query(KnowledgeEntry).filter(
        KnowledgeEntry.category == "extracurricular",
        KnowledgeEntry.subject.in_(tags),
        KnowledgeEntry.auto_approved == True,
    ).order_by(KnowledgeEntry.used_count.desc()).limit(limit).all()


def get_character_knowledge(
    db: Session,
    character: str,
    student_id: int | None = None,
) -> list[KnowledgeEntry]:
    """查找包含指定汉字的知识条目（用于文章生字关联课本知识）"""
    base = db.query(KnowledgeEntry)
    if student_id is not None:
        base = base.filter(KnowledgeEntry.student_id.in_([0, student_id]))

    rows = base.all()
    return [r for r in rows if (r.keywords_json and character in r.keywords_json)]


# ===== 上下文构建 =====

def build_kb_context(
    db: Session,
    topic: str = "",
    characters: list[str] | None = None,
    tags: list[str] | None = None,
    student_id: int | None = None,
    max_chars: int = 600,
) -> str:
    """构建注入 prompt 的知识库上下文字符串"""
    characters = characters or []
    tags = tags or []

    # 获取学生配置
    config = db.query(StudentTextbookConfig).filter(
        StudentTextbookConfig.student_id == student_id
    ).first() if student_id else None

    grade = f"{config.current_grade}_{config.current_semester}" if config else "grade_1_second"
    version = config.textbook_version if config else "人教版"

    # 策略1：按生字找对应课本知识
    char_entries: list[KnowledgeEntry] = []
    for ch in characters[:10]:
        found = get_character_knowledge(db, ch, student_id)
        char_entries.extend(found[:2])

    # 策略2：按主题关键词检索
    keyword_entries = search_knowledge_base(db, query=topic, tags=tags, grade_level=grade, student_id=student_id, limit=5) if topic else []

    # 策略3：按兴趣标签找课外知识
    tag_entries = get_extracurricular_by_tags(db, tags, limit=3) if tags else []

    # 合并去重
    seen_ids = set()
    all_entries: list[KnowledgeEntry] = []
    for e in char_entries + keyword_entries + tag_entries:
        if e.id not in seen_ids:
            seen_ids.add(e.id)
            all_entries.append(e)

    if not all_entries:
        return ""

    # 构建上下文文本
    parts: list[str] = []
    total = 0
    for e in all_entries[:8]:
        text = f"【{e.subject}·{e.lesson or e.title}】{e.content}"
        total += len(text)
        if total > max_chars:
            break
        parts.append(text)

    context = "\n\n".join(parts)
    logger.info(
        f"build_kb_context: topic='{topic[:20]}...', "
        f"chars={characters[:5]}, tags={tags[:3]}, "
        f"entries={len(parts)}, chars={len(context)}"
    )
    return context


# ===== 自动生成课外知识 =====

def auto_generate_entry(
    db: Session,
    tag_name: str,
    student_id: int = 0,
) -> KnowledgeEntry | None:
    """根据兴趣标签，调用 DeepSeek 自动生成科普知识条目"""
    try:
        from openai import OpenAI
        import httpx

        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            http_client=httpx.Client(timeout=30.0),
        )

        prompt = (
            f"请为6-7岁儿童编写一段关于「{tag_name}」的科普知识。\n"
            f"要求：\n"
            f"1. 用简单易懂的语言，像讲故事一样\n"
            f"2. 100-300字\n"
            f"3. 包含2-3个有趣的事实\n"
            f"4. 适合一年级小学生阅读\n"
        )

        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )
        content = resp.choices[0].message.content.strip()

        entry = KnowledgeEntry(
            student_id=student_id,
            category="extracurricular",
            subject=tag_name,
            grade_level="",
            textbook_version="",
            lesson="",
            title=f"科普：{tag_name}",
            content=content,
            keywords_json=[tag_name],
            source="auto_generated",
            auto_approved=True,
            used_count=0,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        logger.info(f"auto_generate_entry: tag='{tag_name}' → id={entry.id} ({len(content)} chars)")
        return entry

    except Exception as e:
        logger.warning(f"auto_generate_entry failed for '{tag_name}': {e}")
        return None


def auto_generate_for_hot_tags(
    db: Session,
    student_id: int = 0,
    top_n: int = 5,
    cooldown_days: int = 7,
):
    """扫描兴趣标签，为热门标签自动生成课外知识（每日定时调用）"""
    from datetime import timedelta

    hot_tags = db.query(InterestEvolution).order_by(
        InterestEvolution.intensity_score.desc()
    ).limit(top_n).all()

    generated = 0
    for tag in hot_tags:
        # 检查 cooldown：最近 N 天内是否已生成过
        cutoff = date.today() - timedelta(days=cooldown_days)
        recent = db.query(KnowledgeEntry).filter(
            KnowledgeEntry.subject == tag.tag_name,
            KnowledgeEntry.source == "auto_generated",
            KnowledgeEntry.created_at >= cutoff,
        ).count()

        if recent > 0:
            continue

        entry = auto_generate_entry(db, tag.tag_name, student_id)
        if entry:
            generated += 1

    logger.info(f"auto_generate_for_hot_tags: generated {generated} new entries")
    return generated


# ===== 文章回哺 =====

def backfeed_from_article(
    db: Session,
    article_id: int,
    student_id: int = 0,
) -> KnowledgeEntry | None:
    """从已生成文章中提取知识点，回哺知识库"""
    from datetime import datetime

    article = db.query(DailyArticle).filter(DailyArticle.id == article_id).first()
    if not article:
        return None

    try:
        from openai import OpenAI
        import httpx

        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            http_client=httpx.Client(timeout=30.0),
        )

        prompt = (
            f"从以下给6-7岁儿童的文章中提取1-2个核心知识要点。\n"
            f"每个要点用一句话概括，适合小学生理解。\n"
            f"只返回要点，不要其他内容。\n\n"
            f"标题：{article.topic}\n"
            f"内容：{article.content[:500]}\n"
        )

        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=200,
        )
        knowledge_text = resp.choices[0].message.content.strip()

        import re
        keywords = list(set(re.findall(r'[一-鿿]', article.topic)))

        entry = KnowledgeEntry(
            student_id=student_id,
            category="extracurricular",
            subject=article.category,
            grade_level="",
            lesson="",
            title=f"从文章提炼：{article.topic}",
            content=knowledge_text,
            keywords_json=keywords[:10],
            source="article_backfeed",
            auto_approved=True,
            used_count=0,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        logger.info(f"backfeed_from_article: article #{article_id} → entry #{entry.id}")
        return entry

    except Exception as e:
        logger.warning(f"backfeed_from_article failed for article #{article_id}: {e}")
        return None


# ===== 辅助 =====

_GRADE_MAP = {
    "grade_1_first": 1,
    "grade_1_second": 2,
    "grade_2_first": 3,
    "grade_2_second": 4,
    "grade_3_first": 5,
    "grade_3_second": 6,
}


def _grade_order(grade_level: str) -> int:
    return _GRADE_MAP.get(grade_level, 0)


def get_or_create_config(
    db: Session,
    student_id: int,
    textbook_version: str = "人教版",
    current_grade: str = "grade_1",
    current_semester: str = "second",
) -> StudentTextbookConfig:
    """获取或创建学生教材配置"""
    config = db.query(StudentTextbookConfig).filter(
        StudentTextbookConfig.student_id == student_id
    ).first()

    if config:
        return config

    config = StudentTextbookConfig(
        student_id=student_id,
        textbook_version=textbook_version,
        current_grade=current_grade,
        current_semester=current_semester,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config
