"""
四区字库服务 — Target/Scout/Ally/Lost 的 CRUD + 迁移 + 自动晋升

自然流动规则:
  新字首次出现 → Scout
  Scout + ≥3篇已读完从未点击 → Ally (自然习得)
  已读完文章中被点击 ≥2 次 → Lost (遇到困难)
  家长录入 → Target (主动教学)
  Lost 复习成功 → Scout (重新接受自然习得检验)
"""
import re
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import (
    TargetCharacter, ScoutCharacter, AllyCharacter, LostCharacter,
    ArticleReadStatus, DailyArticle, ReadingBehavior,
)


# ============================================================
# 工具函数
# ============================================================

def extract_chinese(text: str) -> list[str]:
    """从文本提取所有唯一汉字"""
    return list(dict.fromkeys(re.findall(r'[一-鿿]', text)))


def _is_in_zone(db: Session, char: str, student_id: int) -> str | None:
    """检查字在哪个区，返回区名或 None"""
    if db.query(TargetCharacter).filter(
        TargetCharacter.character == char, TargetCharacter.student_id == student_id
    ).first():
        return "target"
    if db.query(ScoutCharacter).filter(
        ScoutCharacter.character == char, ScoutCharacter.student_id == student_id
    ).first():
        return "scout"
    if db.query(AllyCharacter).filter(
        AllyCharacter.character == char, AllyCharacter.student_id == student_id
    ).first():
        return "ally"
    if db.query(LostCharacter).filter(
        LostCharacter.character == char, LostCharacter.student_id == student_id
    ).first():
        return "lost"
    return None


# ============================================================
# 教学区 (Target)
# ============================================================

def target_add(db: Session, characters: list[str], student_id: int = 1,
                pinyin: list[str] | None = None, source: str = "manual") -> list[TargetCharacter]:
    """录入生字到教学区"""
    records = []
    for i, char in enumerate(characters):
        existing = db.query(TargetCharacter).filter(
            TargetCharacter.character == char,
            TargetCharacter.student_id == student_id,
        ).first()
        if existing:
            continue
        py = pinyin[i] if pinyin and i < len(pinyin) else None
        r = TargetCharacter(student_id=student_id, character=char, pinyin=py, source=source)
        db.add(r)
        records.append(r)

        # 如果字在侦查区，移除（已进入正式教学）
        db.query(ScoutCharacter).filter(
            ScoutCharacter.character == char,
            ScoutCharacter.student_id == student_id,
        ).delete()

    db.commit()
    return records


def target_list(db: Session, student_id: int = 1) -> list[TargetCharacter]:
    return db.query(TargetCharacter).filter(
        TargetCharacter.student_id == student_id
    ).order_by(TargetCharacter.added_at.desc()).all()


def target_delete(db: Session, character: str, student_id: int = 1):
    db.query(TargetCharacter).filter(
        TargetCharacter.character == character,
        TargetCharacter.student_id == student_id,
    ).delete()
    db.commit()


# ============================================================
# 侦查区 (Scout)
# ============================================================

def scout_add(db: Session, characters: list[str], student_id: int = 1,
              source: str = "manual", article_id: int | None = None,
              pinyin: list[str] | None = None) -> list[ScoutCharacter]:
    """添加字到侦查区（手动录入、课本导入、阅读首次遇到）"""
    records = []
    today = date.today()
    for i, char in enumerate(characters):
        # 已在任何区都不重复加
        if _is_in_zone(db, char, student_id):
            continue
        existing = db.query(ScoutCharacter).filter(
            ScoutCharacter.character == char,
            ScoutCharacter.student_id == student_id,
        ).first()
        if existing:
            existing.last_seen_date = today
            existing.source = source
        else:
            py = pinyin[i] if pinyin and i < len(pinyin) else None
            r = ScoutCharacter(
                student_id=student_id, character=char, pinyin=py,
                source=source, first_seen_article_id=article_id,
                first_seen_date=today, last_seen_date=today,
            )
            db.add(r)
            records.append(r)
    db.commit()
    return records


def scout_list(db: Session, student_id: int = 1) -> list[ScoutCharacter]:
    return db.query(ScoutCharacter).filter(
        ScoutCharacter.student_id == student_id
    ).order_by(ScoutCharacter.created_at.desc()).all()


def scout_delete(db: Session, character: str, student_id: int = 1):
    db.query(ScoutCharacter).filter(
        ScoutCharacter.character == character,
        ScoutCharacter.student_id == student_id,
    ).delete()
    db.commit()


# ============================================================
# 友军区 (Ally)
# ============================================================

def ally_add(db: Session, characters: list[str], student_id: int = 1,
             source: str = "manual", pinyin: list[str] | None = None) -> list[AllyCharacter]:
    """录入已知字（家长确认掌握）"""
    records = []
    for i, char in enumerate(characters):
        existing = db.query(AllyCharacter).filter(
            AllyCharacter.character == char,
            AllyCharacter.student_id == student_id,
        ).first()
        if existing:
            continue
        py = pinyin[i] if pinyin and i < len(pinyin) else None
        r = AllyCharacter(student_id=student_id, character=char, pinyin=py, source=source)
        db.add(r)
        records.append(r)

        # 从侦查区移除（已确认为掌握）
        db.query(ScoutCharacter).filter(
            ScoutCharacter.character == char,
            ScoutCharacter.student_id == student_id,
        ).delete()

    db.commit()
    return records


def ally_list(db: Session, student_id: int = 1) -> list[AllyCharacter]:
    return db.query(AllyCharacter).filter(
        AllyCharacter.student_id == student_id
    ).order_by(AllyCharacter.created_at.desc()).all()


def ally_delete(db: Session, character: str, student_id: int = 1):
    db.query(AllyCharacter).filter(
        AllyCharacter.character == character,
        AllyCharacter.student_id == student_id,
    ).delete()
    db.commit()


# ============================================================
# 战损区 (Lost)
# ============================================================

def lost_list(db: Session, student_id: int = 1) -> list[LostCharacter]:
    return db.query(LostCharacter).filter(
        LostCharacter.student_id == student_id
    ).order_by(LostCharacter.tap_count.desc()).all()


def lost_recover(db: Session, character: str, student_id: int = 1):
    """复习成功 → 移回侦查区重新检验"""
    record = db.query(LostCharacter).filter(
        LostCharacter.character == character,
        LostCharacter.student_id == student_id,
    ).first()
    if not record:
        return

    record.status = "recovered"
    record.recovered_to_scout_at = datetime.now()

    # 移回侦查区
    scout = db.query(ScoutCharacter).filter(
        ScoutCharacter.character == character,
        ScoutCharacter.student_id == student_id,
    ).first()
    if scout:
        scout.source = "lost_recovery"
        scout.last_seen_date = date.today()
    else:
        db.add(ScoutCharacter(
            student_id=student_id, character=character,
            pinyin=record.pinyin, source="lost_recovery",
            first_seen_date=date.today(), last_seen_date=date.today(),
        ))

    db.commit()


# ============================================================
# 四区总览
# ============================================================

def zone_summary(db: Session, student_id: int = 1) -> dict:
    return {
        "target": db.query(TargetCharacter).filter(
            TargetCharacter.student_id == student_id).count(),
        "scout": db.query(ScoutCharacter).filter(
            ScoutCharacter.student_id == student_id).count(),
        "ally": db.query(AllyCharacter).filter(
            AllyCharacter.student_id == student_id).count(),
        "lost": db.query(LostCharacter).filter(
            LostCharacter.student_id == student_id).count(),
    }


# ============================================================
# 阅读等级系统（自动晋升）
# ============================================================

def get_reading_level_info(db: Session, student_id: int = 1) -> dict:
    """获取学生的阅读等级信息"""
    from ..models import Student
    from ..config import EDUCATION_CONFIG

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {"level": 1, "name": "识字萌芽", "icon": "🌱", "known": 0, "articles_read": 0}

    ally_count = db.query(AllyCharacter).filter(
        AllyCharacter.student_id == student_id).count()
    scout_count = db.query(ScoutCharacter).filter(
        ScoutCharacter.student_id == student_id).count()

    level = student.reading_level
    levels = EDUCATION_CONFIG.READING_LEVELS
    current = levels[min(level - 1, len(levels) - 1)]
    _, name, icon, _, _ = current

    # 检查下一级
    next_level_info = None
    if level < len(levels):
        _, next_name, next_icon, known_th, art_th = levels[level]
        next_level_info = {
            "level": level + 1,
            "name": next_name,
            "icon": next_icon,
            "known_required": known_th,
            "known_current": ally_count + scout_count,
            "articles_required": art_th,
            "articles_current": student.total_articles_read,
        }

    return {
        "level": level,
        "name": name,
        "icon": icon,
        "known_count": ally_count + scout_count,
        "articles_read": student.total_articles_read,
        "leveled_up_at": student.leveled_up_at.isoformat() if student.leveled_up_at else None,
        "max_level": len(levels),
        "next": next_level_info,
    }


def check_reading_level_up(db: Session, student_id: int = 1) -> dict | None:
    """检查并执行阅读等级自动晋升。返回晋升信息或 None。"""
    from datetime import date as date_type, timedelta
    from ..models import Student
    from ..config import EDUCATION_CONFIG

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return None

    level = student.reading_level
    levels = EDUCATION_CONFIG.READING_LEVELS
    if level >= len(levels):
        return None  # 已满级

    # 冷却检查
    if student.leveled_up_at:
        cooldown = student.leveled_up_at.date() + timedelta(days=EDUCATION_CONFIG.LEVEL_UP_COOLDOWN_DAYS)
        if date_type.today() <= cooldown:
            return None

    # 检查晋级条件
    _, next_name, next_icon, known_threshold, articles_threshold = levels[level]

    ally_count = db.query(AllyCharacter).filter(
        AllyCharacter.student_id == student_id).count()
    scout_count = db.query(ScoutCharacter).filter(
        ScoutCharacter.student_id == student_id).count()
    known = ally_count + scout_count

    if known >= known_threshold and student.total_articles_read >= articles_threshold:
        old_level = level
        student.reading_level = level + 1
        student.leveled_up_at = datetime.now()
        db.commit()

        new_info = levels[level]  # level is now index of new level
        return {
            "promoted": True,
            "old_level": old_level,
            "old_name": levels[old_level - 1][1],
            "new_level": level + 1,
            "new_name": next_name,
            "new_icon": next_icon,
            "known_count": known,
            "articles_read": student.total_articles_read,
        }

    return None


# ============================================================
# 文章生字密度计算
# ============================================================

def calculate_article_params(db: Session, student_id: int = 1,
                              parent_override: dict | None = None) -> dict:
    """基于四区字库自动计算文章长度和生字密度。

    返回:
        article_min, article_max: 文章字数范围
        target_density: 每100字生字数
        reinforce_density: 每100字战损复习数
        target_chars: 本次推荐使用的教学区生字
        reinforce_chars: 本次推荐复习的战损区字
        familiar_chars: AI 可放心使用的高频已知字（友军区样本）
        tier_index: 当前所处的分级索引
    """
    from ..config import EDUCATION_CONFIG

    ally_count = db.query(AllyCharacter).filter(
        AllyCharacter.student_id == student_id).count()
    scout_count = db.query(ScoutCharacter).filter(
        ScoutCharacter.student_id == student_id).count()
    target_count = db.query(TargetCharacter).filter(
        TargetCharacter.student_id == student_id).count()
    lost_count = db.query(LostCharacter).filter(
        LostCharacter.student_id == student_id).count()

    known = ally_count + scout_count  # 孩子接触过的字

    # 查找当前分级
    tiers = EDUCATION_CONFIG.ARTICLE_DENSITY_TIERS
    tier_index = 0
    for i, (threshold, _, _, _, _) in enumerate(tiers):
        tier_index = i
        if known <= threshold:
            break

    _, art_min, art_max, density, reinforce = tiers[tier_index]

    # 家长自定义覆盖
    if parent_override:
        if parent_override.get("min_chars"):
            art_min = parent_override["min_chars"]
        if parent_override.get("max_chars"):
            art_max = parent_override["max_chars"]
        if parent_override.get("density"):
            density = parent_override["density"]
        if parent_override.get("reinforce"):
            reinforce = parent_override["reinforce"]

    # 计算具体字数
    target_char_count = max(1, int(art_min * density / 100))
    target_char_count = min(target_char_count, EDUCATION_CONFIG.MAX_TARGET_CHARS_PER_ARTICLE)
    target_char_count = min(target_char_count, target_count)  # 不超过库存

    reinforce_count = max(0, int(art_min * reinforce / 100))
    reinforce_count = min(reinforce_count, EDUCATION_CONFIG.MAX_REINFORCE_CHARS_PER_ARTICLE)
    reinforce_count = min(reinforce_count, lost_count)

    # 从教学区选字：最近添加优先
    target_chars = []
    if target_char_count > 0:
        rows = db.query(TargetCharacter).filter(
            TargetCharacter.student_id == student_id
        ).order_by(TargetCharacter.added_at.desc()).limit(target_char_count * 2).all()
        target_chars = [r.character for r in rows][:target_char_count]

    # 从战损区选字：点击最多优先
    reinforce_chars = []
    if reinforce_count > 0:
        rows = db.query(LostCharacter).filter(
            LostCharacter.student_id == student_id
        ).order_by(LostCharacter.tap_count.desc()).limit(reinforce_count).all()
        reinforce_chars = [r.character for r in rows]

    # 友军区取样（给 AI 做"已知字池"参考）
    familiar_chars = []
    ally_rows = db.query(AllyCharacter).filter(
        AllyCharacter.student_id == student_id
    ).order_by(func.random()).limit(30).all()
    familiar_chars = [r.character for r in ally_rows]

    return {
        "article_min": art_min,
        "article_max": art_max,
        "target_density": density,
        "reinforce_density": reinforce,
        "target_chars": target_chars,
        "reinforce_chars": reinforce_chars,
        "familiar_chars": familiar_chars,
        "known_count": known,
        "target_count": target_count,
        "scout_count": scout_count,
        "ally_count": ally_count,
        "lost_count": lost_count,
        "tier_index": tier_index,
        "has_override": bool(parent_override),
    }


def get_parent_config(db: Session, student_id: int = 1) -> dict:
    """获取当前家长的密度配置"""
    from ..config import EDUCATION_CONFIG
    return {
        "tiers": [
            {"known_max": t[0], "art_min": t[1], "art_max": t[2],
             "density": t[3], "reinforce": t[4]}
            for t in EDUCATION_CONFIG.ARTICLE_DENSITY_TIERS
        ],
        "max_target_per_article": EDUCATION_CONFIG.MAX_TARGET_CHARS_PER_ARTICLE,
        "max_reinforce_per_article": EDUCATION_CONFIG.MAX_REINFORCE_CHARS_PER_ARTICLE,
        "override_min_chars": EDUCATION_CONFIG.PARENT_OVERRIDE_MIN_CHARS,
        "override_max_chars": EDUCATION_CONFIG.PARENT_OVERRIDE_MAX_CHARS,
        "override_density": EDUCATION_CONFIG.PARENT_OVERRIDE_DENSITY,
        "override_reinforce": EDUCATION_CONFIG.PARENT_OVERRIDE_REINFORCE,
    }


# ============================================================
# 阅读状态
# ============================================================

def update_read_status(db: Session, article_id: int, student_id: int,
                       status: str, read_count: int = 0,
                       total_count: int = 0) -> ArticleReadStatus:
    """上报阅读进度。当标记为已读时自动触发等级晋升检查。"""
    from ..models import Student

    record = db.query(ArticleReadStatus).filter(
        ArticleReadStatus.article_id == article_id,
        ArticleReadStatus.student_id == student_id,
    ).first()

    is_new_read = False

    if not record:
        record = ArticleReadStatus(
            student_id=student_id, article_id=article_id,
            total_paragraph_count=total_count,
        )
        db.add(record)

    record.read_paragraph_count = read_count
    if total_count:
        record.total_paragraph_count = total_count

    if status == "reading" and not record.started_at:
        record.started_at = datetime.now()
        record.status = "reading"

    if status == "read" and record.status != "read":
        is_new_read = True
        record.status = "read"
        record.finished_at = datetime.now()
        # 更新学生累计读完文章数
        student = db.query(Student).filter(Student.id == student_id).first()
        if student:
            student.total_articles_read = (student.total_articles_read or 0) + 1

    db.commit()

    # 自动检查阅读等级晋升
    if is_new_read:
        check_reading_level_up(db, student_id)

    return record


def get_read_status(db: Session, article_id: int, student_id: int = 1) -> ArticleReadStatus | None:
    return db.query(ArticleReadStatus).filter(
        ArticleReadStatus.article_id == article_id,
        ArticleReadStatus.student_id == student_id,
    ).first()


def get_articles_read_status(db: Session, article_ids: list[int],
                              student_id: int = 1) -> dict[int, str]:
    """批量查询多篇文章的阅读状态 → {article_id: status}"""
    rows = db.query(ArticleReadStatus).filter(
        ArticleReadStatus.article_id.in_(article_ids),
        ArticleReadStatus.student_id == student_id,
    ).all()
    return {r.article_id: r.status for r in rows}


# ============================================================
# 自动晋升引擎（文章读完时调用）
# ============================================================

def on_article_read(db: Session, article_id: int, student_id: int = 1):
    """
    当文章被标记为"已读完"时触发:
    1. 提取文章所有汉字
    2. 新字 → 进入侦查区
    3. 读过的字 → 更新侦查区计数 (appeared_in_read_count, never_tapped)
    4. 侦查区 + ≥3篇已读完从未点击 → 晋升友军区
    5. 在本文中被点击过的字 → 移入战损区
    """
    article = db.query(DailyArticle).filter(DailyArticle.id == article_id).first()
    if not article:
        return {"error": "文章不存在"}

    chars = extract_chinese(article.content)
    if not chars:
        return {"error": "无有效汉字"}

    today = date.today()

    # 查询本文中被点击过的字
    tapped_in_article: set[str] = set()
    rows = db.query(ReadingBehavior.character).filter(
        ReadingBehavior.article_id == article_id,
        ReadingBehavior.action_type == "char_tap",
        ReadingBehavior.student_id == student_id,
    ).distinct().all()
    tapped_in_article = {r[0] for r in rows if r[0]}

    # 查询：每个字在之前已读完文章中出现过多少次且从未被点击
    read_articles = db.query(ArticleReadStatus.article_id).filter(
        ArticleReadStatus.status == "read",
        ArticleReadStatus.student_id == student_id,
        ArticleReadStatus.article_id != article_id,
    ).all()
    read_article_ids = [r[0] for r in read_articles]

    promoted_to_ally = 0
    moved_to_lost = 0
    new_to_scout = 0

    for char in chars:
        zone = _is_in_zone(db, char, student_id)

        if zone == "target":
            # 教学区的字被点击 → 移入战损区
            if char in tapped_in_article:
                _move_to_lost(db, char, student_id, today)
                moved_to_lost += 1
            continue

        if zone == "ally":
            # 友军区的字被点击 → 移入战损区（本以为掌握了但实际不会）
            if char in tapped_in_article:
                db.query(AllyCharacter).filter(
                    AllyCharacter.character == char,
                    AllyCharacter.student_id == student_id,
                ).delete()
                _move_to_lost(db, char, student_id, today)
                moved_to_lost += 1
            continue

        if zone == "lost":
            # 战损区的字，如果本文中也点击了 → 增加计数
            if char in tapped_in_article:
                lost = db.query(LostCharacter).filter(
                    LostCharacter.character == char,
                    LostCharacter.student_id == student_id,
                ).first()
                if lost:
                    lost.tap_count += 1
                    lost.last_lost_date = today
                    lost.article_count += 1
            continue

        if zone == "scout":
            scout = db.query(ScoutCharacter).filter(
                ScoutCharacter.character == char,
                ScoutCharacter.student_id == student_id,
            ).first()
            if not scout:
                continue

        # === 字在侦查区 ===
        scout = db.query(ScoutCharacter).filter(
            ScoutCharacter.character == char,
            ScoutCharacter.student_id == student_id,
        ).first()

        if not scout:
            # 完全新字 → 进入侦查区
            db.add(ScoutCharacter(
                student_id=student_id, character=char,
                source="reading", first_seen_article_id=article_id,
                first_seen_date=today, last_seen_date=today,
                appeared_in_read_count=1,
                never_tapped_in_read_count=1 if char not in tapped_in_article else 0,
            ))
            new_to_scout += 1

            # 如果在本文被点击 → 直接进战损区
            if char in tapped_in_article:
                _move_to_lost(db, char, student_id, today)
                moved_to_lost += 1
            continue

        # 已在侦查区 → 更新计数
        scout.appeared_in_read_count += 1
        scout.last_seen_date = today
        if char not in tapped_in_article:
            scout.never_tapped_in_read_count += 1

        # 在本文中被点击 → 移入战损区
        if char in tapped_in_article:
            _move_to_lost(db, char, student_id, today, pinyin=scout.pinyin)
            db.delete(scout)
            moved_to_lost += 1

    db.commit()

    # === 批量晋升：侦查区 → 友军区 ===
    # 在 ≥3 篇已读完文章中从未被点击
    candidates = db.query(ScoutCharacter).filter(
        ScoutCharacter.student_id == student_id,
        ScoutCharacter.never_tapped_in_read_count >= 3,
    ).all()

    for s in candidates:
        db.add(AllyCharacter(
            student_id=student_id, character=s.character,
            pinyin=s.pinyin, source="auto_promoted",
        ))
        s.promoted_to_ally_at = datetime.now()
        promoted_to_ally += 1

    db.commit()

    return {
        "total_chars": len(chars),
        "new_to_scout": new_to_scout,
        "promoted_to_ally": promoted_to_ally,
        "moved_to_lost": moved_to_lost,
    }


def _move_to_lost(db: Session, char: str, student_id: int,
                   today: date, pinyin: str | None = None):
    """将字移入战损区"""
    existing = db.query(LostCharacter).filter(
        LostCharacter.character == char,
        LostCharacter.student_id == student_id,
    ).first()
    if existing:
        existing.tap_count += 1
        existing.article_count += 1
        existing.last_lost_date = today
        if existing.status == "recovered":
            existing.status = "active"
    else:
        db.add(LostCharacter(
            student_id=student_id, character=char, pinyin=pinyin,
            tap_count=1, article_count=1,
            first_lost_date=today, last_lost_date=today,
            status="active",
        ))
