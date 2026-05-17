"""
好奇心状态图 —— 基于 LangGraph 的显式状态机。

处理三种模式:
  one_shot:    提问 → 生成回答文章 → 结束
  conversation: 开启对话 → 多轮交互 → 生成定制文章 → 结束
  series:      拆解主题 → 逐章生成 → 等待阅读 → 下一章? → 继续/完结

状态图就是文档。每个节点只做一件事，边定义流转规则。
"""
import logging
from typing import TypedDict, Annotated, Literal
from datetime import date

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

logger = logging.getLogger(__name__)

# ===== 状态定义 =====

class CuriosityState(TypedDict, total=False):
    """好奇心处理全流程状态，在图的每个节点间流转"""

    # --- 输入 ---
    event_id: int | None
    student_id: int
    raw_text: str                     # 初始问题
    tags: list[str]                   # 兴趣标签

    # --- 模式选择 ---
    mode: str                         # "one_shot" | "conversation" | "series"

    # --- 认知等级 ---
    base_cognition: int               # 学生当前的认知等级
    effective_cognition: int          # 实际使用的等级（可能被高级词汇提升）

    # --- 对话状态 (conversation mode) ---
    session_id: int | None
    conversation_history: list[dict]  # [{role, content}, ...]
    last_child_input: str
    child_wants_more: bool | None     # 孩子是否想继续对话

    # --- 系列状态 (series mode) ---
    series_id: int | None
    chapter_titles: list[dict]        # [{ch, title, summary}, ...]
    current_chapter: int              # 当前正在生成/等待的章节
    child_wants_next_chapter: bool | None  # 读完一章后是否继续

    # --- 输出 ---
    article_id: int | None
    article_content: str
    paragraphs: list                  # 拼音段落
    error: str                        # 错误信息
    done: bool                        # 流程是否结束


# ===== 节点函数 =====

def node_load_event(state: CuriosityState, db_factory) -> CuriosityState:
    """加载好奇心事件，提取基础信息"""
    from ..models import CuriosityEvent, Student
    db = db_factory()
    try:
        e = db.query(CuriosityEvent).filter(CuriosityEvent.id == state.get("event_id")).first()
        if not e:
            return {"error": "事件不存在", "done": True}

        student = db.query(Student).filter(Student.id == state.get("student_id", 1)).first()
        base_cog = student.cognition_level if student else 1
        raw = e.raw_text or ""
        tags = e.tags_json or []

        # 检测高级词汇
        from ..config import EDUCATION_CONFIG
        effective_cog = base_cog
        if any(kw in raw for kw in EDUCATION_CONFIG.ADVANCED_KEYWORDS):
            effective_cog = min(base_cog + 1, EDUCATION_CONFIG.COGNITION_MAX_LEVEL)

        return {
            "event_id": e.id,
            "raw_text": raw,
            "tags": tags,
            "base_cognition": base_cog,
            "effective_cognition": effective_cog,
            "student_id": state.get("student_id", 1),
            "current_chapter": state.get("current_chapter", 0),
            "chapter_titles": state.get("chapter_titles", []),
            "series_id": state.get("series_id"),
        }
    finally:
        db.close()


def node_generate_one_shot(state: CuriosityState, db_factory) -> CuriosityState:
    """模式 one_shot: 直接生成一篇回答文章"""
    from ..services.article_generator import (
        extract_characters_from_text, generate_article_with_pinyin,
        build_recent_chars_context, build_behavior_context, build_zone_context,
    )
    from ..services.memory_service import get_memory_context
    from ..services.knowledge_base_service import build_kb_context
    from ..models import DailyArticle, DailyCharacter, CuriosityEvent

    db = db_factory()
    try:
        topic = state["raw_text"]
        student_id = state["student_id"]
        chars = extract_characters_from_text(topic)

        # 上下文
        memory_ctx = get_memory_context(db, topic, chars)
        memory_str = memory_ctx.get("prompt_context", "") if memory_ctx else ""
        recent = build_recent_chars_context(db, days=5, student_id=student_id)
        behavior = build_behavior_context(db, days=7, student_id=student_id)
        zone = build_zone_context(db, student_id)
        kb = build_kb_context(db, topic=topic, characters=chars, tags=state.get("tags", []), student_id=student_id)

        article = generate_article_with_pinyin(
            topic=topic, characters=chars, min_chars=100, max_chars=300,
            category="answer", memory_context=memory_str,
            recent_chars_context=recent, behavior_context=behavior,
            zone_context=zone, kb_context=kb,
            cognition_level=state["effective_cognition"],
        )

        # 保存文章
        today = date.today()
        a = DailyArticle(student_id=student_id, record_date=today, topic=topic,
                         content=article["content"], character_count=len(article["content"]),
                         source="ai", category="answer")
        db.add(a)
        db.commit()
        db.refresh(a)

        # 关联事件
        event = db.query(CuriosityEvent).filter(CuriosityEvent.id == state["event_id"]).first()
        if event:
            event.is_answered = True
            event.linked_article_id = a.id
            db.commit()

        # 写入今日生字
        today_chars = set(r[0] for r in db.query(DailyCharacter.character)
            .filter(DailyCharacter.record_date == today, DailyCharacter.student_id == student_id).all())
        for ch in chars:
            if ch not in today_chars:
                db.add(DailyCharacter(student_id=student_id, record_date=today, character=ch, category="chinese"))
        db.commit()

        return {"article_id": a.id, "article_content": article["content"],
                "paragraphs": article.get("paragraphs", []), "done": True}
    except Exception as e:
        logger.error(f"node_generate_one_shot: {e}")
        return {"error": str(e), "done": True}
    finally:
        db.close()


def node_start_conversation(state: CuriosityState, db_factory) -> CuriosityState:
    """模式 conversation: 开启对话，生成第一条引导回复"""
    from ..models import ConversationSession, ConversationTurn
    from ..config import EDUCATION_CONFIG

    db = db_factory()
    try:
        session = ConversationSession(
            student_id=state["student_id"],
            curiosity_event_id=state["event_id"],
            status="active", turn_count=1,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        reply = _call_deepseek_conversation(
            topic=state["raw_text"],
            history=[],
            cognition_level=state["effective_cognition"],
        )

        turn = ConversationTurn(session_id=session.id, role="assistant", content=reply)
        db.add(turn)
        db.commit()

        return {
            "session_id": session.id,
            "conversation_history": [{"role": "assistant", "content": reply}],
        }
    except Exception as e:
        logger.error(f"node_start_conversation: {e}")
        return {"error": str(e), "done": True}
    finally:
        db.close()


def node_conversation_turn(state: CuriosityState, db_factory) -> CuriosityState:
    """模式 conversation: 处理孩子的一轮输入，返回回复

    这里使用 LangGraph 的 interrupt 机制——等待前端传入 child_input 后继续。
    """
    from ..models import ConversationSession, ConversationTurn, Student
    from ..config import EDUCATION_CONFIG

    db = db_factory()
    try:
        session_id = state["session_id"]
        user_input = state.get("last_child_input", "")

        if not user_input:
            return {"error": "缺少孩子输入", "done": True}

        # 重新评估认知等级
        student = db.query(Student).filter(Student.id == state["student_id"]).first()
        base = student.cognition_level if student else 1
        eff = base
        if any(kw in user_input for kw in EDUCATION_CONFIG.ADVANCED_KEYWORDS):
            eff = min(base + 1, EDUCATION_CONFIG.COGNITION_MAX_LEVEL)

        # 保存用户输入
        user_turn = ConversationTurn(session_id=session_id, role="user", content=user_input)
        db.add(user_turn)
        db.flush()

        # 获取历史
        history = _get_turns(db, session_id)

        reply = _call_deepseek_conversation(
            topic=state["raw_text"],
            history=history,
            cognition_level=eff,
        )

        assistant_turn = ConversationTurn(session_id=session_id, role="assistant", content=reply)
        db.add(assistant_turn)

        # 更新会话轮次
        session = db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
        if session:
            session.turn_count = len(history) + 1
        db.commit()

        return {
            "conversation_history": history + [{"role": "assistant", "content": reply}],
            "effective_cognition": eff,
            "last_child_input": "",  # 清空，等待下一次输入
        }
    except Exception as e:
        logger.error(f"node_conversation_turn: {e}")
        return {"error": str(e), "done": True}
    finally:
        db.close()


def node_generate_conversation_article(state: CuriosityState, db_factory) -> CuriosityState:
    """模式 conversation: 结束对话，根据完整历史生成定制文章"""
    from ..models import ConversationSession, CuriosityEvent, DailyArticle, DailyCharacter, Student
    from ..services.article_generator import extract_characters_from_text
    from ..services.pinyin_service import annotate_text
    from ..config import EDUCATION_CONFIG

    db = db_factory()
    try:
        session_id = state["session_id"]
        history = _get_turns(db, session_id)

        event = db.query(CuriosityEvent).filter(
            CuriosityEvent.id == state["event_id"]).first()
        topic = event.raw_text if event else state.get("raw_text", "")

        all_text = topic + " " + " ".join([t["content"] for t in history])
        chars = extract_characters_from_text(all_text)[:8]

        student = db.query(Student).filter(Student.id == state["student_id"]).first()
        base_level = student.cognition_level if student else 1

        # 构建对话历史文本
        history_text = "\n".join([
            f"{'俊宜' if t['role'] == 'user' else '老师'}: {t['content']}"
            for t in history
        ])

        from ..config import EDUCATION_CONFIG as CFG
        cog_guide = CFG.COGNITION_PROMPTS.get(min(base_level, CFG.COGNITION_MAX_LEVEL), CFG.COGNITION_PROMPTS[1])

        import httpx
        from openai import OpenAI
        from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=httpx.Client(timeout=60.0))

        prompt = f"""写一篇科普文章。以下是你要覆盖的素材。

【对话记录】
{history_text}

【写作要求】
- 标题：{topic}
- 全文450-600字，分4-5段，每段100-150字
- 覆盖对话中的所有关键概念
- 使用对话中孩子理解的比喻
- 温和纠正对话中的误区
- {cog_guide}
- 融入生字：{'、'.join(chars)}
- 结尾用"俊宜，今天你知道了……"收尾"""

        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": "写一篇450-600字的科普文章。要有结构、有深度、有逻辑。不用拼音。写不够450字就是不合格。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7, max_tokens=3000,
        )
        content = resp.choices[0].message.content.strip()

        # 保存文章
        today = date.today()
        article = DailyArticle(student_id=state["student_id"], record_date=today,
                               topic=topic, content=content, character_count=len(content),
                               source="ai", category="answer")
        db.add(article)
        db.commit()
        db.refresh(article)

        if event:
            event.is_answered = True
            event.linked_article_id = article.id

        session = db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
        if session:
            session.status = "completed"
            session.final_article_id = article.id
        db.commit()

        paragraphs = annotate_text(content)

        return {"article_id": article.id, "article_content": content,
                "paragraphs": paragraphs, "done": True}
    except Exception as e:
        logger.error(f"node_generate_conversation_article: {e}")
        return {"error": str(e), "done": True}
    finally:
        db.close()


# ===== 系列模式节点 =====

def node_decompose_topic(state: CuriosityState, db_factory) -> CuriosityState:
    """模式 series: 将主题拆解为 3-5 个子章节"""
    import httpx
    from openai import OpenAI
    from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

    topic = state["raw_text"]
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=httpx.Client(timeout=30.0))
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": f"""把"「{topic}」"这个主题拆解成3-5个小章节，适合7岁孩子分次阅读。
每章250-300字，一章讲清楚一个小问题。
用JSON格式返回，不要其他内容：
[{{"ch":1,"title":"第一章标题","summary":"这一章讲什么，一句话概括"}}, ...]"""}],
            temperature=0.7, max_tokens=500,
        )
        import json
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        chapters = json.loads(raw)

        return {
            "chapter_titles": chapters,
            "current_chapter": 0,  # 尚未生成任何章
        }
    except Exception as e:
        logger.error(f"node_decompose_topic: {e}")
        # 降级：手动拆分
        return {
            "chapter_titles": [
                {"ch": 1, "title": f"什么是{topic[:10]}？", "summary": "基本概念"},
                {"ch": 2, "title": f"{topic[:10]}是怎么形成的？", "summary": "深入原理"},
                {"ch": 3, "title": f"我们能看见{topic[:10]}吗？", "summary": "观察方法"},
            ],
            "current_chapter": 0,
        }


def node_generate_chapter(state: CuriosityState, db_factory) -> CuriosityState:
    """模式 series: 生成当前章节（250-300字）"""
    from ..models import ArticleSeries, DailyArticle, CuriosityEvent
    from ..services.article_generator import extract_characters_from_text
    from ..config import EDUCATION_CONFIG

    db = db_factory()
    try:
        series_id = state.get("series_id")
        chapter_idx = state["current_chapter"]
        chapters = state.get("chapter_titles", [])

        if chapter_idx >= len(chapters):
            return {"done": True}

        ch = chapters[chapter_idx]
        ch_title = ch["title"]
        ch_summary = ch.get("summary", "")

        # 获取已知字库
        from ..services.article_generator import build_zone_context
        zone_ctx = build_zone_context(db, state["student_id"])

        # 从摘要中提取生字
        chars = extract_characters_from_text(ch_title + ch_summary)[:5]

        import httpx
        from openai import OpenAI
        from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=httpx.Client(timeout=60.0))

        cog_guide = EDUCATION_CONFIG.COGNITION_PROMPTS.get(
            min(state["effective_cognition"], EDUCATION_CONFIG.COGNITION_MAX_LEVEL),
            EDUCATION_CONFIG.COGNITION_PROMPTS[1])

        prompt = f"""写一章科普文章。

主题系列：{state['raw_text']}
本章标题：{ch_title}
本章概要：{ch_summary}

要求：
1. 250-300字，不要多也不要少
2. {cog_guide}
3. 优先使用常见字，每章只嵌入2-3个生字：{'、'.join(chars)}
4. 结尾留下一个悬念或问题，勾起对下一章的兴趣
5. 只输出本章内容"""

        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": "你是儿童科普作家。每章250-300字，不多不少。语言生动，像讲故事。章节结尾有悬念。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7, max_tokens=800,
        )
        content = resp.choices[0].message.content.strip()

        # 保存文章
        today = date.today()
        article = DailyArticle(
            student_id=state["student_id"], record_date=today,
            topic=ch_title, content=content, character_count=len(content),
            source="ai", category="answer",
            series_id=series_id, chapter_number=chapter_idx + 1,
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        # 如果是第一章，关联事件
        if chapter_idx == 0 and state.get("event_id"):
            event = db.query(CuriosityEvent).filter(CuriosityEvent.id == state["event_id"]).first()
            if event:
                event.is_answered = True
                event.linked_article_id = article.id

        # 更新系列进度
        series = db.query(ArticleSeries).filter(ArticleSeries.id == series_id).first()
        if series:
            series.current_chapter = chapter_idx + 1
        db.commit()

        from ..services.pinyin_service import annotate_text
        return {
            "article_id": article.id,
            "article_content": content,
            "paragraphs": annotate_text(content),
            "current_chapter": chapter_idx + 1,
            "done": True,  # 单次 invoke 只生成一章，然后结束
        }
    except Exception as e:
        logger.error(f"node_generate_chapter: {e}")
        return {"error": str(e), "done": True}
    finally:
        db.close()


def node_complete_series(state: CuriosityState, db_factory) -> CuriosityState:
    """模式 series: 标记系列完结"""
    from ..models import ArticleSeries as AS
    db = db_factory()
    try:
        series_id = state.get("series_id")
        series = db.query(AS).filter(AS.id == series_id).first()
        if series:
            series.status = "completed"
            db.commit()
        return {"done": True}
    finally:
        db.close()


def node_abandon_series(state: CuriosityState, db_factory) -> CuriosityState:
    """模式 series: 孩子放弃，标记系列中止"""
    from ..models import ArticleSeries as AS
    db = db_factory()
    try:
        series_id = state.get("series_id")
        series = db.query(AS).filter(AS.id == series_id).first()
        if series:
            series.status = "abandoned"
            db.commit()
        return {"done": True}
    finally:
        db.close()


# ===== 路由函数 =====

def route_by_mode(state: CuriosityState) -> Literal["node_generate_one_shot", "node_start_conversation", "node_decompose_topic", "node_generate_chapter"]:
    mode = state.get("mode", "one_shot")
    if mode == "conversation":
        return "node_start_conversation"
    elif mode == "series":
        # 如果已有章节列表（从 DB 传入），跳过拆解直接生成
        if state.get("chapter_titles"):
            return "node_generate_chapter"
        return "node_decompose_topic"
    return "node_generate_one_shot"


def route_after_chapter(state: CuriosityState) -> Literal["node_complete_series", "__end__"]:
    """读完一章后：如果还有更多章节且需要继续，就继续；否则结束"""
    chapters = state.get("chapter_titles", [])
    current = state["current_chapter"]

    if current >= len(chapters):
        return "node_complete_series"

    # 单次 invoke 模式：每次只生成一章就结束
    # 由外部 service 层控制"何时生成下一章"
    return "__end__"


# ===== 图构建 =====

_curiosity_graph = None  # 懒加载

def get_curiosity_graph():
    global _curiosity_graph
    if _curiosity_graph is not None:
        return _curiosity_graph

    builder = StateGraph(CuriosityState)

    # 注册节点
    builder.add_node("node_load_event", lambda s: node_load_event(s, _make_db))
    builder.add_node("node_generate_one_shot", lambda s: node_generate_one_shot(s, _make_db))
    builder.add_node("node_start_conversation", lambda s: node_start_conversation(s, _make_db))
    builder.add_node("node_conversation_turn", lambda s: node_conversation_turn(s, _make_db))
    builder.add_node("node_generate_conversation_article", lambda s: node_generate_conversation_article(s, _make_db))
    builder.add_node("node_decompose_topic", lambda s: node_decompose_topic(s, _make_db))
    builder.add_node("node_generate_chapter", lambda s: node_generate_chapter(s, _make_db))
    builder.add_node("node_complete_series", lambda s: node_complete_series(s, _make_db))
    builder.add_node("node_abandon_series", lambda s: node_abandon_series(s, _make_db))

    # 边: START → load_event → 按 mode 分发
    builder.add_edge(START, "node_load_event")
    builder.add_conditional_edges("node_load_event", route_by_mode)

    # one_shot 分支
    builder.add_edge("node_generate_one_shot", END)

    # conversation 分支
    builder.add_edge("node_start_conversation", END)     # 返回后等待前端送 turn
    builder.add_edge("node_conversation_turn", END)       # 每轮结束后等待
    # conversation → generate article（由外部 API 触发）
    builder.add_edge("node_generate_conversation_article", END)

    # series 分支
    builder.add_edge("node_decompose_topic", "node_generate_chapter")
    builder.add_conditional_edges("node_generate_chapter", route_after_chapter)
    builder.add_edge("node_complete_series", END)
    builder.add_edge("node_abandon_series", END)

    checkpointer = MemorySaver()
    _curiosity_graph = builder.compile(checkpointer=checkpointer)
    return _curiosity_graph


# ===== 数据库工厂 =====

def _make_db():
    from ..database import SessionLocal
    return SessionLocal()


# ===== 辅助 =====

def _get_turns(db, session_id: int) -> list[dict]:
    from ..models import ConversationTurn
    turns = db.query(ConversationTurn).filter(
        ConversationTurn.session_id == session_id
    ).order_by(ConversationTurn.created_at.asc()).all()
    return [{"role": t.role, "content": t.content} for t in turns]


def _call_deepseek_conversation(topic: str, history: list[dict], cognition_level: int) -> str:
    """对话回复生成"""
    import httpx
    from openai import OpenAI
    from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, EDUCATION_CONFIG

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=httpx.Client(timeout=30.0))
    cog = EDUCATION_CONFIG.COGNITION_PROMPTS.get(min(cognition_level, 3), EDUCATION_CONFIG.COGNITION_PROMPTS[1])

    if not history:
        prompt = f"""俊宜问：「{topic}」

你是俊宜的科普老师。给一个有启发的回答：
1. {cog}
2. 最后反问一个引导性问题
3. 100-200字"""
    else:
        history_text = "\n".join([
            f"{'俊宜' if t['role'] == 'user' else '老师'}: {t['content']}"
            for t in history
        ])
        prompt = f"""初始问题：「{topic}」

对话记录（最后一条是俊宜刚说的）：
{history_text}

回复俊宜刚说的最后一句话：
1. 先回应他刚才说的内容，不要忽略
2. 如果他说错了，温和纠正
3. {cog}
4. 偶尔反问引导，不强制
5. 不超过150字"""

    resp = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7, max_tokens=600,
    )
    return resp.choices[0].message.content.strip()
