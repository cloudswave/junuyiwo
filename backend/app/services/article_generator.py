import logging
import re
import time
import httpx
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger(__name__)

from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, GLM_API_KEY, GLM_IMAGE_MODEL, CHILD_APPEARANCE
from .pinyin_service import annotate_text

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=httpx.Client(timeout=60.0))

# GLM-Image API
GLM_IMAGE_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"

FALLBACK_TEMPLATES = {
    "春天": "春天来了，小草从地里钻出来了。\n\n花儿开了，红红的，白白的，真好看。\n\n小鸟在树上唱歌，它们很快乐。\n\n风吹过来，暖暖的，像妈妈的手。\n\n小朋友们在公园里玩，大家都笑了。",
    "动物": "小猫和小狗是好朋友。\n\n它们一起在院子里玩。\n\n小猫会爬树，小狗会跑步。\n\n有一天，小鸟飞来了，它们三个一起玩。\n\n太阳下山了，它们都回家了。",
    "学校": "今天是开学的第一天。\n\n我背着新书包去学校。\n\n老师站在门口，笑着说：\"欢迎新同学！\"\n\n教室里有很多小朋友。\n\n我们一起读书，一起写字，真开心！",
    "家庭": "我的家有爸爸、妈妈和我。\n\n爸爸每天去上班，妈妈在家做饭。\n\n我最喜欢吃妈妈做的饺子。\n\n晚上，我们一起看电视，讲故事。\n\n我爱我的家！",
}


def build_recent_chars_context(db, days: int = 5, student_id: int = 1) -> str:
    """Build a prompt hint for recently learned characters, weighted by recency.

    Characters learned more recently get a stronger frequency hint.
    Returns a string to be appended to the article generation prompt, or empty string.
    """
    from datetime import date as date_type, timedelta

    today = date_type.today()
    recent_by_date: dict[int, list[str]] = {}

    for i in range(days):
        d = today - timedelta(days=i)
        # Import here to avoid circular
        from ..models import DailyCharacter
        chars = (
            db.query(DailyCharacter.character)
            .filter(DailyCharacter.record_date == d, DailyCharacter.student_id == student_id)
            .distinct()
            .all()
        )
        chars_list = [c[0] for c in chars]
        if chars_list:
            recent_by_date[i] = chars_list

    if not recent_by_date:
        return ""

    weight_labels = {
        0: ("今天学的", "尽量多次出现"),
        1: ("昨天学的", "多出现"),
        2: ("2-3天前学的", "适当多出现"),
        3: ("2-3天前学的", "适当多出现"),
        4: ("4-5天前学的", "可以出现"),
    }

    lines = ["\n【最近学过的生字 - 请适当增加这些字在文章中的出现频次，离今天越近越要多出现】"]
    for days_ago, chars in sorted(recent_by_date.items()):
        label, hint = weight_labels.get(days_ago, (f"{days_ago}天前", "可以出现"))
        chars_str = "、".join(chars)
        lines.append(f"- {label}：{chars_str}（{hint}）")

    return "\n".join(lines)


def build_zone_context(db, student_id: int = 1) -> str:
    """Build zone-aware context for article generation prompt.

    Tells the AI what chars the child already knows (Ally),
    which ones need reinforcement (Lost), and which are being explored (Scout).
    """
    from ..models import AllyCharacter, LostCharacter, ScoutCharacter

    ally_chars = [r[0] for r in db.query(AllyCharacter.character).filter(
        AllyCharacter.student_id == student_id).order_by(
        AllyCharacter.created_at.desc()).limit(40).all()]

    lost_chars = [r[0] for r in db.query(LostCharacter.character).filter(
        LostCharacter.student_id == student_id).order_by(
        LostCharacter.tap_count.desc()).limit(10).all()]

    if not ally_chars and not lost_chars:
        return ""

    lines = ["\n【孩子字库状况 — 帮助AI了解孩子的识字水平】"]
    if ally_chars:
        lines.append(f"- 已掌握的字（可放心使用，接近80%比例）：{'、'.join(ally_chars)}")
        lines.append("  请用这些字作为文章的主体词汇，让孩子读得顺畅有成就感")
    if lost_chars:
        lines.append(f"- 遇到困难的字（请反复出现帮助复习）：{'、'.join(lost_chars)}")
        lines.append("  请在文章中多次重复这些字，每次用在稍有不同的上下文中")

    return "\n".join(lines)


def build_article_prompt(topic: str, characters: list[str], min_chars: int, max_chars: int, category: str = "story", memory_context: str | None = None, recent_chars_context: str = "", behavior_context: str = "", zone_context: str = "", kb_context: str = "", cognition_level: int = 1) -> str:
    chars_str = "、".join(characters)

    memory_block = ""
    if memory_context:
        memory_block = f"""

【孩子的学习记忆 - 请结合以下上下文写作，让新内容与孩子的已知知识产生连接】
{memory_context}
- 请在内容中自然呼应孩子未解答的问题
- 请反复使用孩子容易遗忘的字，帮助强化记忆"""

    # 知识库上下文
    kb_block = ""
    if kb_context:
        kb_block = f"""

【课本知识和科普内容 - 请在文章中使用以下真实准确的知识】
{kb_context}
- 请确保涉及上述知识点时内容准确，不要编造与课本冲突的内容
- 课外科普知识可作为文章背景自然地融入故事中"""

    # 隐式反馈自动调整
    difficulty_hint = ""
    if behavior_context:
        difficulty_hint = f"""

【自适应难度调整 - 基于近期阅读行为自动优化】
{behavior_context}"""

    # 认知水平对应的 prompt 引导词
    from ..config import EDUCATION_CONFIG
    lvl = min(max(cognition_level, 1), EDUCATION_CONFIG.COGNITION_MAX_LEVEL)
    cognition_guidance = EDUCATION_CONFIG.COGNITION_PROMPTS.get(lvl, EDUCATION_CONFIG.COGNITION_PROMPTS[1])

    if category == "answer":
        return f"""请回答一个孩子提出的问题，要求如下：

1. 回答这个问题：「{topic}」
2. 字数 {min_chars}-{max_chars} 字，不要太长
3. {cognition_guidance}
4. 不要用「首先、其次、综上所述」这种教科书腔调
5. 开头可以用「你知道吗？」「你有没有想过...」之类的钩子
6. 必须自然融入以下生字（每个至少出现 1 次）：{chars_str}
7. 只输出纯中文内容，不要加拼音、不要加翻译、不要加英文{memory_block}{kb_block}{recent_chars_context}{difficulty_hint}{zone_context}

段落之间用空行分隔，不要加标题和说明文字。"""

    # 短文章使用顺口溜风格
    rhyme_rule = ""
    if min_chars <= 100:
        rhyme_rule = ("3. 必须写成童谣/顺口溜形式，要求：\n"
                       "   - 每行一句，行末必须押同一韵脚（如全押ang韵、全押ao韵）\n"
                       "   - 像「小老鼠，上灯台，偷油吃，下不来」那样三字或五字一顿\n"
                       "   - 节奏明快，读起来像打拍子\n")
    else:
        rhyme_rule = "3. 每句话不超过 20 个字\n"

    return f"""请写一篇适合7岁小男孩阅读的短文，主角叫「俊宜」（用「他」），要求如下：

1. 字数 {min_chars}-{max_chars} 字
2. 主题围绕「{topic}」，内容像探险故事一样有趣
{rhyme_rule}4. 语言生动，像在讲一个有趣的小故事，不要教科书腔调
5. 必须自然融入以下生字（每个至少出现 1 次）：{chars_str}
6. 只输出纯中文文章，不要加拼音、不要加翻译、不要加英文{memory_block}{kb_block}{recent_chars_context}{difficulty_hint}{zone_context}

段落之间用空行分隔，不要加标题和说明文字。"""


def build_behavior_context(db, days: int = 7, student_id: int = 1) -> str:
    """根据近期阅读行为生成自适应 prompt 提示。
    数据来源: reading_behaviors 表（前端 fire-and-forget 上报）"""
    from datetime import date, timedelta
    from sqlalchemy import func
    from ..models import ReadingBehavior

    cutoff = date.today() - timedelta(days=days)
    stats = (
        db.query(ReadingBehavior.character, func.count(ReadingBehavior.id).label("taps"))
        .filter(ReadingBehavior.created_at >= cutoff, ReadingBehavior.action_type == "char_tap", ReadingBehavior.student_id == student_id)
        .group_by(ReadingBehavior.character)
        .order_by(func.count(ReadingBehavior.id).desc())
        .limit(10)
        .all()
    )

    if not stats:
        return ""

    total_taps = sum(row.taps for row in stats)
    high_freq_chars = [f"「{row.character}」(点击{row.taps}次)" for row in stats if row.taps >= 2]

    lines = []
    if total_taps >= 5:
        lines.append(f"孩子最近{days}天点字听发音{total_taps}次，文章可能偏难，请适当降低难度。")
    if high_freq_chars:
        lines.append(f"以下字被高频点击：{'、'.join(high_freq_chars)}。这些字孩子可能不熟，请多用简单词替换或加强重复。")
    if total_taps >= 3:
        lines.append("请使用更简单的词汇，每句话不超过15字。")

    return "\n".join(lines)


_STORY_SYSTEM = "你是一位冒险家兼故事大王，去过世界上很多神奇的地方。你的故事像探险日记，充满惊喜和发现。故事主角是7岁小男孩「俊宜」（用「他」），他勇敢好奇喜欢探索。你只输出纯中文文章，不加拼音、不加注解。"
_ANSWER_SYSTEM = "你是一位好奇心爆棚的探险家，用最简单的语言回答孩子对世界的「为什么」。主角是7岁小男孩「俊宜」（用「他」），你用讲故事的方式解释事物，像探险家分享奇妙见闻。你只输出纯中文内容，不加拼音、不加注解。"


def estimate_difficulty(article_text: str, known_chars: set[str]) -> float:
    """估算文章中生字比例（不认识的汉字 / 总汉字数）。"""
    words = set(re.findall(r'[\u4e00-\u9fff]', article_text))
    if not words:
        return 0.0
    new_words = words - known_chars
    return len(new_words) / len(words)


def generate_raw_article(topic: str, characters: list[str], min_chars: int = 300, max_chars: int = 800, category: str = "story", memory_context: str | None = None, recent_chars_context: str = "", behavior_context: str = "", zone_context: str = "", kb_context: str = "", known_chars: set[str] | None = None, cognition_level: int = 1) -> str:
    """Generate plain Chinese article without pinyin annotation.
    如果生字比例 > 15%，自动降低难度重试（最多 2 次）。
    """
    prompt = build_article_prompt(topic, characters, min_chars, max_chars, category, memory_context, recent_chars_context, behavior_context, zone_context, kb_context, cognition_level=cognition_level)
    system_msg = _ANSWER_SYSTEM if category == "answer" else _STORY_SYSTEM

    def _call_deepseek(p: str, s: str) -> str:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "system", "content": s}, {"role": "user", "content": p}],
            temperature=0.8, max_tokens=4096,
        )
        return response.choices[0].message.content.strip()

    try:
        content = _call_deepseek(prompt, system_msg)
        if not content:
            return get_fallback_article(topic, characters)

        # 难度检查：如果已知字够多但生字比例超 15%，降低难度重试
        if known_chars and len(known_chars) >= 10:
            for retry in range(2):
                ratio = estimate_difficulty(content, known_chars)
                if ratio <= 0.15:
                    break
                logger.info(f"Article difficulty {ratio:.0%} > 15%, retry {retry+1}")
                easier = prompt + f"\n\n【重要】当前生字比例{ratio:.0%}过高。请降低难度：多用简单常用字，减少生僻字，确保至少85%的汉字是常见字。"
                content = _call_deepseek(easier, system_msg)
                if not content:
                    break

        return content
    except Exception as e:
        logger.error(f"generate_raw_article failed: {type(e).__name__}: {e}")

    return get_fallback_article(topic, characters)


def generate_image_prompt(topic: str, article_snippet: str) -> str:
    """Generate a Chinese illustration prompt for GLM-Image."""
    snippet = article_snippet[:200]

    # 构建外貌描述
    child_desc = "主角是7岁中国小男孩「俊宜」，短发、活泼、爱笑"
    if CHILD_APPEARANCE:
        child_desc += f"，外貌特征：{CHILD_APPEARANCE}"

    system_msg = (
        f"你是一位儿童绘本插画师。写一段60字以内的中文绘图提示词。"
        f"{child_desc}。"
        f"要求：3D渲染风格、柔和光影、立体感强、景深效果。"
        f"使用词汇：可爱小男孩、温馨、色彩鲜艳、C4D渲染、皮克斯风格、暖色调。"
    )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"主题：{topic}\n片段：{snippet}\n\n写一段绘图提示词（注意主角是7岁小男孩俊宜）："},
            ],
            temperature=0.9,
            max_tokens=200,
        )
        prompt = response.choices[0].message.content.strip()
        if prompt:
            return prompt
    except Exception:
        pass
    return f"可爱温馨的儿童插画，主题是{topic}，主角是7岁小男孩俊宜，短发，活泼爱笑，色彩鲜艳，暖色调"


def revise_raw_article(original: str, topic: str, suggestions: str) -> str:
    """根据修改建议回炉优化文章。"""
    prompt = f"""请根据修改建议优化以下文章。

原文主题：{topic}
原文内容：
{original}

修改建议：{suggestions}

要求：
1. 保持原文主题和整体结构
2. 按要求修改（如改名字、调整难度、缩短长度等）
3. 主角是7岁小男孩「俊宜」，用「他」
4. 每句话不超过20字，语言生动
5. 只输出修改后的完整文章，不要加任何说明文字"""

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": _STORY_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4096,
        )
        content = response.choices[0].message.content.strip()
        if content:
            return content
    except Exception:
        pass
    return original


def generate_cover_image(topic: str, article_content: str) -> str | None:
    """Generate a cover image. 优先本地 SD+IP-Adapter(人脸一致)，降级 GLM-Image."""

    # Step 1: 尝试本地人脸一致性生成
    try:
        from .face_image_generator import generate_cover_with_face
        url = generate_cover_with_face(topic, article_content)
        if url:
            logger.info(f"Cover image generated via local SD (face-consistent): {url}")
            return url
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Local face generation failed, falling back to GLM-Image: {e}")

    # Step 2: 降级 GLM-Image
    if not GLM_API_KEY:
        return None

    prompt = generate_image_prompt(topic, article_content)

    try:
        resp = httpx.post(
            GLM_IMAGE_URL,
            headers={
                "Authorization": f"Bearer {GLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GLM_IMAGE_MODEL,
                "prompt": prompt,
            },
            timeout=60.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            urls = data.get("data", [])
            if urls:
                url = urls[0].get("url")
                if url:
                    logger.info(f"Cover image generated via GLM-Image: {url}")
                    # Download and save locally to avoid long URL / expiration issues
                    try:
                        img_resp = httpx.get(url, timeout=30.0)
                        if img_resp.status_code == 200:
                            output_dir = Path(__file__).resolve().parent.parent.parent / "static" / "generated"
                            output_dir.mkdir(parents=True, exist_ok=True)
                            filename = f"cover_{int(time.time())}.png"
                            output_path = output_dir / filename
                            output_path.write_bytes(img_resp.content)
                            local_url = f"/static/generated/{filename}"
                            logger.info(f"Cover image saved locally: {local_url}")
                            return local_url
                    except Exception as e:
                        logger.warning(f"Failed to download GLM cover image: {e}")
                    return url  # fallback to remote URL if download fails
    except Exception:
        pass

    return None


def generate_article_with_pinyin(topic: str, characters: list[str], min_chars: int = 300, max_chars: int = 800, category: str = "story", memory_context: str | None = None, recent_chars_context: str = "", behavior_context: str = "", zone_context: str = "", kb_context: str = "", known_chars: set[str] | None = None, cognition_level: int = 1) -> dict:
    """
    Generate article with accurate pinyin annotation (without image).
    Returns {topic, content, paragraphs, total_chars}.
    """
    raw = generate_raw_article(topic, characters, min_chars, max_chars, category, memory_context, recent_chars_context, behavior_context, zone_context, kb_context=kb_context, known_chars=known_chars, cognition_level=cognition_level)
    paragraphs = annotate_text(raw)
    total = sum(len([t for t in p if t.get("pinyin")]) for p in paragraphs)
    return {
        "topic": topic,
        "content": raw,
        "paragraphs": paragraphs,
        "total_chars": total,
    }


def generate_article_image(topic: str, article_content: str) -> str | None:
    """Generate cover image based on article content. Returns image URL or None."""
    return generate_cover_image(topic, article_content)


def generate_article_images(topic: str, content: str, num_paragraphs: int) -> list[dict]:
    """
    Generate multiple inline images for an article.
    Returns list of {"url": str, "after_para": int}.
    Images are generated in parallel.
    """
    if not GLM_API_KEY:
        return []

    # Calculate number of images: ~1 per 100 chars, min 2, max 5
    char_count = len(re.sub(r'[^\u4e00-\u9fff]', '', content))
    num_images = min(5, max(2, char_count // 100))

    # Split content into paragraphs
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    if not paragraphs:
        return []

    # Divide paragraphs into num_images sections, each image goes at the END of its section
    snippets = []
    positions = []
    for i in range(num_images):
        start = int(i * len(paragraphs) / num_images)
        end = int((i + 1) * len(paragraphs) / num_images)
        end = min(end, len(paragraphs))
        # Use the last 2 paragraphs of the section as the image prompt
        snippet_start = max(start, end - 2)
        snippet = '\n'.join(paragraphs[snippet_start:end])
        snippets.append(snippet)
        # Insert image after the last paragraph of this section
        positions.append(end - 1)

    # 逐张串行生成（避免 GPU/API 并发压力导致超时）
    output = []
    for i, snippet in enumerate(snippets):
        url = generate_cover_image(topic, snippet)
        if url:
            output.append({"url": url, "after_para": positions[i]})
    return output


def get_fallback_article(topic: str, characters: list[str]) -> str:
    """Return a plain-text fallback article."""
    for key in FALLBACK_TEMPLATES:
        if key in topic:
            return FALLBACK_TEMPLATES[key]

    chars_str = "、".join(characters[:10])
    return (
        f"今天是美好的一天。\n\n"
        f"我们要学习新的生字：{chars_str}。\n\n"
        f"请小朋友和家长一起读这篇文章。\n\n"
        f"（AI生成暂时不可用，这是系统预设的文章模板。请稍后再试。）"
    )


def extract_characters_from_text(text: str) -> list[str]:
    """Extract unique Chinese characters from text, removing non-Chinese chars."""
    chars = re.findall(r'[一-鿿]', text)
    seen = set()
    result = []
    for ch in chars:
        if ch not in seen:
            seen.add(ch)
            result.append(ch)
    return result
