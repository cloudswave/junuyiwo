"""
Agent 主循环 — 感知 → 决策 → 执行 → 记忆

所有 API 路由通过此类调用 Agent 能力，保持路由层薄、逻辑在 Agent 层。
"""

from sqlalchemy.orm import Session

from .remember import RememberLayer
from .perceive import PerceiveLayer
from .reason import ReasonLayer
from .act import ActLayer


class AgentLoop:
    """
    Agent 主循环，注入数据库会话和学生ID，提供统一入口。

    用法:
        agent = AgentLoop(db, student_id)
        agent.perceive.on_char_tap(article_id, char)     # 感知
        ctx = agent.reason.build_behavior_context()       # 决策
        article = agent.act.generate_article(...)         # 执行
        agent.remember.save_article(...)                  # 记忆
    """

    def __init__(self, db: Session, student_id: int = 1):
        self.memory = RememberLayer(db, student_id)
        self.perceive = PerceiveLayer(self.memory)
        self.reason = ReasonLayer(self.memory)
        self.act = ActLayer()

    @property
    def remember(self) -> RememberLayer:
        return self.memory

    # ===== 便捷方法：点字闭环 =====

    def on_char_tap(self, article_id: int, character: str):
        """孩子点字 → 感知 + 自动降级"""
        self.perceive.on_char_tap(article_id, character)

    # ===== 便捷方法：文章生成闭环 =====

    def generate_article(self, topic: str, characters: list[str],
                         min_chars: int = 300, max_chars: int = 800,
                         category: str = "story", memory_context: str | None = None) -> str:
        """决策 + 执行：根据行为数据自适应生成文章"""
        behavior_ctx = self.reason.build_behavior_context()
        recent_ctx = self.reason.build_recent_chars_context()
        zone_ctx = self.reason.build_zone_context()
        # 构建已知字集合（友军区 + 侦查区），用于难度检查
        known_chars = self.reason.get_known_char_set()
        return self.act.generate_article(
            topic, characters, min_chars, max_chars, category,
            behavior_context=behavior_ctx, recent_chars_context=recent_ctx,
            memory_context=memory_context, zone_context=zone_ctx,
            known_chars=known_chars,
        )

    def revise_article(self, original: str, topic: str, suggestions: str) -> str:
        """执行：回炉修改文章"""
        return self.act.revise_article(original, topic, suggestions)
