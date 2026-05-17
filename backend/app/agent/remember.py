"""
记忆层 — Agent 的长期和短期记忆读写

表映射:
  短期记忆: reading_behaviors (近7天点字)
  长期记忆: daily_characters (三层字库), user_word_mastery (掌握度)
  情景记忆: daily_articles (阅读历史), curiosity_events (提问)
  语义记忆: knowledge_nodes / knowledge_links (知识图谱)
"""

from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import (
    DailyCharacter, DailyArticle, ReadingBehavior,
    ForgottenCharacter, Student,
)


class RememberLayer:
    """Agent 记忆读写"""

    def __init__(self, db: Session, student_id: int = 1):
        self.db = db
        self.student_id = student_id

    # ===== 短期记忆：阅读行为 =====

    def save_behavior(self, article_id: int, character: str, action_type: str = "char_tap"):
        """记录一次阅读行为（前端 fire-and-forget 调用）"""
        rb = ReadingBehavior(
            student_id=self.student_id,
            article_id=article_id,
            character=character,
            action_type=action_type,
        )
        self.db.add(rb)
        self.db.commit()

    def get_recent_behaviors(self, days: int = 7):
        """获取近期行为统计: {char: tap_count}"""
        cutoff = date.today() - timedelta(days=days)
        stats = (
            self.db.query(ReadingBehavior.character, func.count(ReadingBehavior.id).label("taps"))
            .filter(
                ReadingBehavior.created_at >= cutoff,
                ReadingBehavior.action_type == "char_tap",
                ReadingBehavior.student_id == self.student_id,
            )
            .group_by(ReadingBehavior.character)
            .order_by(func.count(ReadingBehavior.id).desc())
            .limit(10)
            .all()
        )
        return {row.character: row.taps for row in stats}

    # ===== 长期记忆：四区字库 =====

    def get_target_chars(self) -> list[str]:
        """获取教学区所有字（文章生成的唯一字源）"""
        from ..models import TargetCharacter
        chars = (
            self.db.query(TargetCharacter.character)
            .filter(TargetCharacter.student_id == self.student_id)
            .order_by(TargetCharacter.added_at.desc())
            .all()
        )
        return [c[0] for c in chars]

    def get_recent_chars(self, days: int = 7):
        """获取近期教学区的字及添加时间"""
        from ..models import TargetCharacter
        cutoff = date.today() - timedelta(days=days)
        records = (
            self.db.query(TargetCharacter)
            .filter(
                TargetCharacter.added_at >= cutoff,
                TargetCharacter.student_id == self.student_id,
            )
            .order_by(TargetCharacter.added_at.desc())
            .all()
        )
        result = {}
        for r in records:
            days_ago = (date.today() - r.added_at.date()).days if r.added_at else 0
            if r.character not in result or days_ago < result[r.character]["d"]:
                result[r.character] = {"d": days_ago, "t": 1}
        return result

    def get_all_dates_with_chars(self) -> list[date]:
        rows = (
            self.db.query(DailyCharacter.record_date)
            .filter(DailyCharacter.student_id == self.student_id)
            .distinct()
            .order_by(DailyCharacter.record_date.desc())
            .all()
        )
        return [r[0] for r in rows]

    def get_daily_chars(self, d: date) -> list:
        from ..models import TargetCharacter
        return (
            self.db.query(TargetCharacter)
            .filter(func.date(TargetCharacter.added_at) == d, TargetCharacter.student_id == self.student_id)
            .all()
        )

    def count_characters(self, category: str | None = None) -> int:
        q = self.db.query(DailyCharacter).filter(DailyCharacter.student_id == self.student_id)
        if category:
            q = q.filter(DailyCharacter.category == category)
        return q.count()

    def add_characters(self, record_date: date, characters: list[str], pinyin: list[str] | None = None, category: str = "chinese"):
        """录入生字到新鲜字库"""
        records = []
        for i, char in enumerate(characters):
            py = pinyin[i] if pinyin and i < len(pinyin) else None
            existing = (
                self.db.query(DailyCharacter)
                .filter(
                    DailyCharacter.record_date == record_date,
                    DailyCharacter.character == char,
                    DailyCharacter.student_id == self.student_id,
                )
                .first()
            )
            if existing:
                continue
            r = DailyCharacter(
                student_id=self.student_id, record_date=record_date,
                character=char, pinyin=py, category=category,
            )
            self.db.add(r)
            records.append(r)
        self.db.commit()
        return records

    def delete_character(self, char: str):
        self.db.query(DailyCharacter).filter(
            DailyCharacter.character == char,
            DailyCharacter.student_id == self.student_id,
        ).delete()
        self.db.commit()

    # ===== 遗忘记忆 =====

    def record_forgotten(self, char: str, learned_days_ago: int | None = None):
        """标记一个字为遗忘（自动降级调用）"""
        existing = (
            self.db.query(ForgottenCharacter)
            .filter(ForgottenCharacter.character == char, ForgottenCharacter.student_id == self.student_id)
            .first()
        )
        today = date.today()
        if existing:
            existing.forget_count += 1
            existing.last_forgotten_date = today
            existing.level = self._compute_level(existing.forget_count)
        else:
            self.db.add(ForgottenCharacter(
                student_id=self.student_id, character=char,
                forget_count=1, first_forgotten_date=today,
                last_forgotten_date=today, level="活跃",
                learned_days_ago=learned_days_ago,
            ))
        self.db.commit()

    def get_forgotten_stats(self) -> dict:
        rows = (
            self.db.query(ForgottenCharacter.level, func.count(ForgottenCharacter.id))
            .filter(ForgottenCharacter.student_id == self.student_id)
            .group_by(ForgottenCharacter.level)
            .all()
        )
        stats = {"活跃": 0, "三次": 0, "五次以上": 0}
        for level, cnt in rows:
            stats[level] = cnt
        return stats

    def get_forgotten_list(self, level: str | None = None):
        q = (
            self.db.query(ForgottenCharacter)
            .filter(ForgottenCharacter.student_id == self.student_id)
            .order_by(ForgottenCharacter.forget_count.desc())
        )
        if level:
            q = q.filter(ForgottenCharacter.level == level)
        return q.all()

    # ===== 情景记忆：文章 =====

    def get_today_article(self):
        today = date.today()
        return (
            self.db.query(DailyArticle)
            .filter(DailyArticle.record_date == today, DailyArticle.student_id == self.student_id)
            .order_by(DailyArticle.id.desc())
            .first()
        )

    def get_article_list(self):
        return (
            self.db.query(DailyArticle)
            .filter(DailyArticle.student_id == self.student_id)
            .order_by(DailyArticle.record_date.desc())
            .all()
        )

    def save_article(self, record_date: date, topic: str, content: str,
                     char_count: int, category: str = "story") -> DailyArticle:
        article = DailyArticle(
            student_id=self.student_id, record_date=record_date,
            topic=topic, content=content, character_count=char_count,
            source="ai", category=category,
        )
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)
        return article

    def get_article_by_id(self, article_id: int) -> DailyArticle | None:
        return self.db.query(DailyArticle).filter(DailyArticle.id == article_id).first()

    def update_article_content(self, article_id: int, content: str):
        article = self.get_article_by_id(article_id)
        if article:
            article.content = content
            article.character_count = len(content)
            self.db.commit()

    # ===== 学生 =====

    def list_students(self):
        return self.db.query(Student).order_by(Student.id).all()

    @staticmethod
    def _compute_level(count: int) -> str:
        if count >= 5:
            return "五次以上"
        elif count >= 3:
            return "三次"
        return "活跃"
