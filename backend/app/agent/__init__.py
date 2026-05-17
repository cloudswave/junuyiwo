"""
俊宜识字 Agent 模块

架构: 感知 → 决策 → 执行 → 记忆
      ↑                        │
      └──────── 闭环 ──────────┘

- perceive: 采集阅读行为数据、语音识别
- reason:   分析数据、做出决策（难度/字库/生字密度）
- act:      调用外部 AI 工具执行决策
- remember: 读写持久化记忆（字库、行为、文章）
"""

from .perceive import PerceiveLayer
from .reason import ReasonLayer
from .act import ActLayer
from .remember import RememberLayer

__all__ = ["PerceiveLayer", "ReasonLayer", "ActLayer", "RememberLayer"]
