from datetime import date, timedelta
from sqlalchemy.orm import Session

from ..models import DailyArticle, DailyCharacter, CuriosityEvent, ForgottenCharacter
from ..memory.retrieval_engine import is_vector_search_enabled, search_similar_articles


def _find_related_mysql(db: Session, topic: str, characters: list[str], cutoff: date) -> list[dict]:
    """MySQL 关键词匹配（文章少时的回退方案）。"""
    recent_articles = (
        db.query(DailyArticle)
        .filter(DailyArticle.record_date >= cutoff)
        .order_by(DailyArticle.record_date.desc())
        .limit(15)
        .all()
    )

    related_articles = []
    topic_lower = topic.lower()
    for a in recent_articles:
        score = 0
        if topic_lower in a.topic.lower() or any(t in a.topic for t in topic_lower.split()):
            score += 3
        for ch in characters:
            if ch in a.content:
                score += 1
        if score > 0:
            snippet = a.content[:80].replace("\n", " ")
            related_articles.append({
                "id": a.id,
                "record_date": a.record_date.isoformat(),
                "topic": a.topic,
                "snippet": snippet + ("..." if len(a.content) > 80 else ""),
                "relevance": min(score, 5),
            })

    related_articles.sort(key=lambda x: x["relevance"], reverse=True)
    return related_articles[:3]


def _find_related_vector(db: Session, topic: str, characters: list[str], cutoff: date) -> list[dict]:
    """Pinecone 语义检索 + MySQL 补充 record_date。"""
    query = f"{topic} {' '.join(characters)}"
    matches = search_similar_articles(query, top_k=5)

    if not matches:
        return []

    # 从 MySQL 补全 record_date
    ids = [m["id"] for m in matches]
    articles = (
        db.query(DailyArticle)
        .filter(DailyArticle.id.in_(ids))
        .all()
    )
    date_map = {a.id: a.record_date.isoformat() for a in articles}

    result = []
    for m in matches:
        result.append({
            "id": m["id"],
            "record_date": date_map.get(m["id"], ""),
            "topic": m["topic"],
            "snippet": m["snippet"],
            "relevance": min(int(m["score"] * 5), 5),
        })
    return result


def get_memory_context(
    db: Session,
    topic: str,
    characters: list[str],
    lookback_days: int = 30,
) -> dict:
    """Build a memory profile of the child's learning history relevant to the given topic."""

    today = date.today()
    cutoff = today - timedelta(days=lookback_days)

    # 1. Related articles — 按文章量阈值自动选择检索方式
    total_articles = db.query(DailyArticle).count()

    if is_vector_search_enabled(total_articles):
        recent_article_summary = _find_related_vector(db, topic, characters, cutoff)
    else:
        recent_article_summary = _find_related_mysql(db, topic, characters, cutoff)

    # 2. Unanswered curiosity questions
    recent_questions = (
        db.query(CuriosityEvent)
        .filter(
            CuriosityEvent.event_date >= cutoff,
            CuriosityEvent.is_answered == False,
        )
        .order_by(CuriosityEvent.event_date.desc())
        .limit(10)
        .all()
    )

    question_summary = [
        {
            "id": q.id,
            "event_date": q.event_date.isoformat(),
            "raw_text": q.raw_text,
            "tags": q.tags_json or [],
        }
        for q in recent_questions[:5]
    ]

    # 3. Forgotten characters that overlap with learned chars
    all_learned = (
        db.query(DailyCharacter.character)
        .distinct()
        .all()
    )
    learned_chars = set(c[0] for c in all_learned)

    forgotten = (
        db.query(ForgottenCharacter)
        .filter(ForgottenCharacter.character.in_(learned_chars))
        .order_by(ForgottenCharacter.forget_count.desc())
        .limit(10)
        .all()
    )

    forgotten_summary = [
        {
            "character": f.character,  # Python attribute, maps to hanzi column
            "pinyin": f.pinyin,
            "forget_count": f.forget_count,
            "level": f.level,
        }
        for f in forgotten
    ]

    # 4. Build human-readable summary
    summary_parts = []

    if recent_article_summary:
        for a in recent_article_summary[:2]:
            days_ago = (today - date.fromisoformat(a["record_date"])).days
            when = f"{days_ago}天前" if days_ago > 0 else "今天"
            if days_ago >= 7:
                weeks = days_ago // 7
                when = f"{weeks}周前"
            elif days_ago > 1:
                when = f"{days_ago}天前"
            elif days_ago == 1:
                when = "昨天"

            summary_parts.append(f"{when}读过《{a['topic']}》")

    if question_summary:
        for q in question_summary[:3]:
            summary_parts.append("孩子曾问过：" + q["raw_text"])
        if len(question_summary) > 3:
            summary_parts[-1] += "等" + str(len(question_summary)) + "个问题"

    if forgotten_summary:
        forget_high = [f["character"] for f in forgotten_summary if f["forget_count"] >= 2]
        if forget_high:
            summary_parts.append(f"有{len(forget_high)}个高频遗忘字：{'、'.join(forget_high[:8])}")

    if summary_parts:
        summary_text = "。\n".join(summary_parts) + "。\n是否把这些元素融入新文章？"
    else:
        summary_text = "这是第一次生成文章，没有历史学习记录可参考。"

    # 5. Build prompt context for AI
    memory_context_for_prompt = []
    if recent_article_summary:
        memory_context_for_prompt.append("【孩子近期读过的文章】")
        for a in recent_article_summary[:3]:
            memory_context_for_prompt.append(f"- 《{a['topic']}》")

    if question_summary:
        memory_context_for_prompt.append("【孩子未解答的问题】")
        for q in question_summary[:3]:
            memory_context_for_prompt.append(f"- {q['raw_text']}")

    if forgotten_summary:
        memory_context_for_prompt.append("【容易遗忘的字，请在新文章中强化】")
        chars = [f["character"] for f in forgotten_summary if f["forget_count"] >= 2]
        memory_context_for_prompt.append("、".join(chars[:10]))

    return {
        "related_articles": recent_article_summary,
        "forgotten_chars": forgotten_summary,
        "unanswered_questions": question_summary,
        "summary_text": summary_text,
        "prompt_context": "\n".join(memory_context_for_prompt) if memory_context_for_prompt else "",
        "has_memory": len(summary_parts) > 0,
    }
