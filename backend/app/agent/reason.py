"""
决策层 — Agent 的大脑

根据感知到的行为数据，做出生成参数的自动调整决策。
"""

from .remember import RememberLayer


class ReasonLayer:
    """行为分析 + 自适应决策"""

    def __init__(self, memory: RememberLayer):
        self.memory = memory

    # ===== 难度自适应决策 =====

    def build_behavior_context(self, days: int = 7) -> str:
        """
        分析近期点字行为，生成自适应 prompt 指令。

        规则:
        - 总点击 ≥ 5 次 → 降低难度
        - 某字点击 ≥ 2 次 → 该字偏难，用简单词替换
        - 总点击 ≥ 3 次 → 缩短句子
        """
        taps = self.memory.get_recent_behaviors(days)
        if not taps:
            return ""

        total_taps = sum(taps.values())
        high_freq = [f"「{c}」(点击{n}次)" for c, n in taps.items() if n >= 2]

        lines = []
        if total_taps >= 5:
            lines.append(f"孩子最近{days}天点字听发音{total_taps}次，文章可能偏难，请适当降低难度。")
        if high_freq:
            lines.append(f"以下字被高频点击：{'、'.join(high_freq)}。这些字孩子可能不熟，请多用简单词替换或加强重复。")
        if total_taps >= 3:
            lines.append("请使用更简单的词汇，每句话不超过15字。")

        return "\n".join(lines)

    def build_recent_chars_context(self, days: int = 5) -> str:
        """构建近期生字提示，用于文章生成时强化"""
        from datetime import date as date_type, timedelta

        today = date_type.today()
        recent_by_date: dict[int, list[str]] = {}
        for i in range(days):
            d = today - timedelta(days=i)
            chars = self.memory.get_daily_chars(d)
            if chars:
                recent_by_date[i] = [c.character for c in chars]

        if not recent_by_date:
            return ""

        weight_labels = {
            0: ("今天", "必须反复出现（至少3次）"),
            1: ("昨天", "应该出现2-3次"),
            2: ("2天前", "应该出现1-2次"),
            3: ("3天前", "可以出现"),
            4: ("4天前", "可以出现"),
        }
        lines = ["\n【近期已学生字—用于强化记忆】"]
        for days_ago in sorted(recent_by_date.keys()):
            chars = recent_by_date[days_ago]
            label, hint = weight_labels.get(days_ago, (f"{days_ago}天前", "可以出现"))
            lines.append(f"- {label}：{'、'.join(chars)}（{hint}）")
        return "\n".join(lines)

    # ===== 已知字集合 =====

    def get_known_char_set(self) -> set[str]:
        """获取孩子认识的字（友军区 + 侦查区），用于难度检查"""
        from ..models import AllyCharacter, ScoutCharacter
        ally = self.memory.db.query(AllyCharacter.character).filter(
            AllyCharacter.student_id == self.memory.student_id).all()
        scout = self.memory.db.query(ScoutCharacter.character).filter(
            ScoutCharacter.student_id == self.memory.student_id).all()
        return {r[0] for r in ally} | {r[0] for r in scout}

    # ===== 四区字库上下文 =====

    def build_zone_context(self) -> str:
        """构建四区字库上下文，告诉 AI 孩子认识哪些字、哪些需要复习"""
        from ..models import AllyCharacter, LostCharacter, ScoutCharacter

        ally = self.memory.db.query(AllyCharacter.character).filter(
            AllyCharacter.student_id == self.memory.student_id
        ).order_by(AllyCharacter.created_at.desc()).limit(40).all()

        lost = self.memory.db.query(LostCharacter.character).filter(
            LostCharacter.student_id == self.memory.student_id
        ).order_by(LostCharacter.tap_count.desc()).limit(10).all()

        if not ally and not lost:
            return ""

        lines = ["\n【孩子字库状况 — 帮助AI了解孩子的识字水平】"]
        if ally:
            ally_str = "、".join([r[0] for r in ally])
            lines.append(f"- 已掌握的字（可放心使用，接近80%比例）：{ally_str}")
            lines.append("  请用这些字作为文章的主体词汇，让孩子读得顺畅有成就感")
        if lost:
            lost_str = "、".join([r[0] for r in lost])
            lines.append(f"- 遇到困难的字（请反复出现帮助复习）：{lost_str}")
            lines.append("  请在文章中多次重复这些字，每次用在稍有不同的上下文中")

        return "\n".join(lines)

    # ===== 字库晋升决策 =====

    def decide_tier_change(self, character: str, action: str, article_id: int | None = None) -> dict:
        """
        决定字库升降。

        规则:
        - 新鲜字库(tier1): 连续3次"认识" → 熟悉字库
        - 熟悉字库(tier2): 3篇不同文章中确认 → 老朋友字库
        - 老朋友字库(tier3): 永久掌握
        - 点字发声 → 自动标记遗忘 → 降级
        """
        from ..models import DailyCharacter

        existing = (
            self.memory.db.query(DailyCharacter)
            .filter(
                DailyCharacter.character == character,
                DailyCharacter.student_id == self.memory.student_id,
            )
            .first()
        )

        from datetime import date as date_type
        if not existing:
            rec = self.memory.add_characters(date_type.today(), [character], category="chinese")
            if rec:
                rec[0].tier = 1
                rec[0].confirm_count = 1
                self.memory.db.commit()
            return {"character": character, "tier": 1, "message": "已加入新鲜字库"}

        if existing.tier == 3:
            return {"character": character, "tier": 3, "message": "已在老朋友字库"}

        if existing.tier == 1:
            existing.confirm_count += 1
            if existing.confirm_count >= 3:
                existing.tier = 2
                existing.confirm_count = 0
                self.memory.db.commit()
                return {"character": character, "tier": 2, "promoted": True, "message": "升入熟悉字库！"}
            self.memory.db.commit()
            return {"character": character, "tier": 1, "promoted": False,
                    "message": f"新鲜字库 已确认{existing.confirm_count}次"}

        if existing.tier == 2:
            if article_id and article_id == existing.last_confirm_article_id:
                return {"character": character, "tier": 2, "message": "本篇已确认过"}
            existing.confirm_count += 1
            existing.last_confirm_article_id = article_id
            if existing.confirm_count >= 3:
                existing.tier = 3
                self.memory.db.commit()
                return {"character": character, "tier": 3, "promoted": True, "message": "升入老朋友字库！"}
            self.memory.db.commit()
            return {"character": character, "tier": 2,
                    "message": f"熟悉字库 已确认{existing.confirm_count}/3篇"}

        return {"character": character, "message": "未知状态"}
