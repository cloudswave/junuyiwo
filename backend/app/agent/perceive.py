"""
感知层 — Agent 的眼睛和耳朵

采集孩子的阅读行为数据，所有采集都是 fire-and-forget 无需家长操作。
"""

from .remember import RememberLayer


class PerceiveLayer:
    """行为感知：采集点字、遗忘、语音等信号"""

    def __init__(self, memory: RememberLayer):
        self.memory = memory

    # ===== 点字行为采集 =====

    def on_char_tap(self, article_id: int, character: str):
        """
        孩子点击了一个字听发音。
        只记录行为，不立即标记遗忘。
        战损区判定在文章读完时统一处理，避免误触误判。
        """
        self.memory.save_behavior(article_id, character, "char_tap")

    # ===== 语音输入 =====

    def on_voice_input(self, recognized_text: str) -> list[str]:
        """
        孩子通过语音说了内容 → 提取汉字
        """
        import re
        chars = re.findall(r'[一-鿿]', recognized_text)
        return list(dict.fromkeys(chars))

    # ===== 字库手动操作 =====

    def on_add_characters(self, record_date, characters: list[str],
                          pinyin: list[str] | None = None, category: str = "chinese"):
        """家长录入生字 → 进入新鲜字库"""
        return self.memory.add_characters(record_date, characters, pinyin, category)

    def on_delete_character(self, char: str):
        self.memory.delete_character(char)
