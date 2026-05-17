import csv
import io
import json
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyArticle, DailyCharacter, ForgottenCharacter, TargetCharacter
from ..services.review_service import (
    get_daily_characters,
    get_forgotten_stats,
    get_all_dates_with_characters,
    get_today_target_chars,
    get_total_target_chars,
)
from ..services.curiosity_service import get_events, get_hot_interests
from ..services.pinyin_service import annotate_article
from .students import get_current_student_id
from ..models import TargetCharacter, ScoutCharacter, AllyCharacter, LostCharacter

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/")
def dashboard(db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    today = date.today()
    today_chars = get_daily_characters(db, today, student_id)
    today_math_chars = [c for c in today_chars if c.category == "math"]
    today_article = db.query(DailyArticle).filter(DailyArticle.record_date == today, DailyArticle.student_id == student_id).order_by(DailyArticle.id.desc()).first()

    article_data = None
    if today_article:
        annotated = annotate_article(today_article.content)
        # 字库分布分析
        import re
        article_chars = list(dict.fromkeys(re.findall(r'[\u4e00-\u9fff]', today_article.content)))
        in_target = [c for c in article_chars if db.query(TargetCharacter).filter(TargetCharacter.character==c, TargetCharacter.student_id==student_id).count()]
        in_scout = [c for c in article_chars if db.query(ScoutCharacter).filter(ScoutCharacter.character==c, ScoutCharacter.student_id==student_id).count()]
        in_ally = [c for c in article_chars if db.query(AllyCharacter).filter(AllyCharacter.character==c, AllyCharacter.student_id==student_id).count()]
        in_lost = [c for c in article_chars if db.query(LostCharacter).filter(LostCharacter.character==c, LostCharacter.student_id==student_id).count()]
        in_any = set(in_target) | set(in_scout) | set(in_ally) | set(in_lost)
        article_data = {
            "id": today_article.id,
            "record_date": today_article.record_date.isoformat(),
            "topic": today_article.topic,
            "content": today_article.content,
            "character_count": today_article.character_count,
            "source": today_article.source,
            "image_url": today_article.image_url,
            "created_at": today_article.created_at.isoformat() if today_article.created_at else None,
            "paragraphs": annotated["paragraphs"],
            "char_breakdown": {
                "total": len(article_chars),
                "from_target": sorted(in_target),
                "from_scout": sorted(in_scout),
                "from_ally": sorted(in_ally),
                "from_lost": sorted(in_lost),
                "not_in_any": sorted([c for c in article_chars if c not in in_any]),
            },
        }

    forgotten_stats = get_forgotten_stats(db, student_id)

    # Merge old DailyCharacter counts with new Target zone
    all_dates = get_all_dates_with_characters(db, student_id)
    total_old = sum(len(get_daily_characters(db, d, student_id)) for d in all_dates)
    total_target = get_total_target_chars(db, student_id)
    total_learned = max(total_old, total_target)
    total_math = db.query(DailyCharacter).filter(DailyCharacter.category == "math", DailyCharacter.student_id == student_id).count()

    # Today's chars: merge old + target
    target_today = get_today_target_chars(db, student_id)
    old_today_chars = [c.character for c in today_chars]
    merged_today = list(dict.fromkeys(old_today_chars + target_today))  # deduplicate preserving order

    recent_questions = get_events(db, answered=False, limit=5)
    hot = get_hot_interests(db, limit=5)

    # 超过3天未回答的问题计数
    from datetime import timedelta
    stale_date = today - timedelta(days=3)
    all_unanswered = get_events(db, answered=False)
    stale_unanswered = [e for e in all_unanswered if e.event_date < stale_date]

    return {
        "today": today.isoformat(),
        "today_characters": merged_today,
        "today_math_characters": [c.character for c in today_math_chars],
        "today_article": article_data,
        "forgotten_stats": forgotten_stats,
        "total_characters_learned": total_learned,
        "total_math_characters": total_math,
        "recent_questions": recent_questions,
        "hot_interests": hot,
        "stale_unanswered_count": len(stale_unanswered),
    }


@router.get("/article-review/{record_date}")
def article_char_review(record_date: str, db: Session = Depends(get_db)):
    """Cross-reference today's article characters with learned characters, grouped by learn date."""
    import re
    from collections import defaultdict

    article = db.query(DailyArticle).filter(DailyArticle.record_date == record_date).first()
    if not article:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"日期 {record_date} 没有文章")

    text_chars = set(re.findall(r'[一-鿿]', article.content))

    if not text_chars:
        return {
            "article_date": record_date,
            "article_topic": article.topic,
            "total_in_article": 0,
            "learned_count": 0,
            "not_learned_count": 0,
            "by_date": {},
            "not_learned": [],
        }

    learned = db.query(DailyCharacter).filter(
        DailyCharacter.character.in_(text_chars)
    ).order_by(DailyCharacter.record_date.asc()).all()

    by_date: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, str] = {}
    for lc in learned:
        date_key = lc.record_date.isoformat()
        if lc.character not in seen:
            seen[lc.character] = date_key
            by_date[date_key].append({
                "character": lc.character,
                "pinyin": lc.pinyin,
            })

    sorted_by_date = dict(sorted(by_date.items()))
    not_learned = sorted(text_chars - set(seen.keys()))

    return {
        "article_date": record_date,
        "article_topic": article.topic,
        "total_in_article": len(text_chars),
        "learned_count": len(seen),
        "not_learned_count": len(not_learned),
        "by_date": sorted_by_date,
        "not_learned": not_learned,
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    """Get detailed learning statistics."""
    all_dates = get_all_dates_with_characters(db, student_id)
    daily_counts = []
    total = 0
    for d in sorted(all_dates):
        chars = get_daily_characters(db, d, student_id)
        total += len(chars)
        daily_counts.append({"date": d.isoformat(), "count": len(chars), "total": total})

    forgotten = db.query(ForgottenCharacter).filter(ForgottenCharacter.student_id == student_id).all()
    forgotten_by_level = {"active": 0, "三次": 0, "五次以上": 0, "已学会": 0}
    for f in forgotten:
        forgotten_by_level[f.level] = forgotten_by_level.get(f.level, 0) + 1

    articles = db.query(DailyArticle).filter(DailyArticle.student_id == student_id).order_by(DailyArticle.record_date).all()
    article_stats = [
        {
            "date": a.record_date.isoformat(),
            "topic": a.topic,
            "character_count": a.character_count,
            "source": a.source,
        }
        for a in articles
    ]

    return {
        "total_characters_learned": total,
        "total_days": len(all_dates),
        "daily_progress": daily_counts,
        "forgotten_stats": forgotten_by_level,
        "total_forgotten": len(forgotten),
        "total_articles": len(articles),
        "articles": article_stats,
    }


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db)):
    """Export all learning data as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== 生字学习记录 ==="])
    writer.writerow(["日期", "生字", "拼音"])
    chars = db.query(DailyCharacter).order_by(DailyCharacter.record_date.asc()).all()
    for c in chars:
        writer.writerow([c.record_date.isoformat(), c.character, c.pinyin or ""])

    writer.writerow([])
    writer.writerow(["=== 遗忘字记录 ==="])
    writer.writerow(["汉字", "拼音", "遗忘次数", "首次遗忘", "最近遗忘", "等级"])
    forgotten = db.query(ForgottenCharacter).order_by(ForgottenCharacter.forget_count.desc()).all()
    for f in forgotten:
        writer.writerow([
            f.character, f.pinyin or "", f.forget_count,
            f.first_forgotten_date.isoformat() if f.first_forgotten_date else "",
            f.last_forgotten_date.isoformat() if f.last_forgotten_date else "",
            f.level,
        ])

    writer.writerow([])
    writer.writerow(["=== 文章记录 ==="])
    writer.writerow(["日期", "主题", "字数", "来源"])
    articles = db.query(DailyArticle).order_by(DailyArticle.record_date.asc()).all()
    for a in articles:
        writer.writerow([a.record_date.isoformat(), a.topic, a.character_count, a.source])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=junyi_learning_data.csv"},
    )


@router.get("/export/json")
def export_json(db: Session = Depends(get_db)):
    """Export all learning data as JSON."""
    chars = db.query(DailyCharacter).order_by(DailyCharacter.record_date.asc()).all()
    forgotten = db.query(ForgottenCharacter).order_by(ForgottenCharacter.forget_count.desc()).all()
    articles = db.query(DailyArticle).order_by(DailyArticle.record_date.asc()).all()

    data = {
        "export_date": date.today().isoformat(),
        "characters": [
            {"date": c.record_date.isoformat(), "character": c.character, "pinyin": c.pinyin}
            for c in chars
        ],
        "forgotten": [
            {
                "character": f.character,
                "pinyin": f.pinyin,
                "forget_count": f.forget_count,
                "first_forgotten_date": f.first_forgotten_date.isoformat() if f.first_forgotten_date else None,
                "last_forgotten_date": f.last_forgotten_date.isoformat() if f.last_forgotten_date else None,
                "level": f.level,
            }
            for f in forgotten
        ],
        "articles": [
            {
                "date": a.record_date.isoformat(),
                "topic": a.topic,
                "content": a.content,
                "character_count": a.character_count,
                "source": a.source,
            }
            for a in articles
        ],
    }

    return StreamingResponse(
        iter([json.dumps(data, ensure_ascii=False, indent=2)]),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=junyi_learning_data.json"},
    )
