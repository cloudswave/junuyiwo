"""
执行层 — Agent 的手

调用外部 AI 工具完成实际任务。
工具集: DeepSeek(文章生成/修改), 科大讯飞(语音识别),
        edge-tts(语音合成), 智谱 CogView(图片生成)
"""

import json, time, base64, hashlib, hmac, re, asyncio, io, wave, logging
from datetime import datetime

logger = logging.getLogger(__name__)
from time import mktime
from wsgiref.handlers import format_date_time
from urllib.parse import urlencode

from ..config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    GLM_API_KEY, GLM_IMAGE_MODEL,
    XFYUN_APP_ID, XFYUN_API_KEY, XFYUN_API_SECRET,
)


class ActLayer:
    """AI 工具调用"""

    # ===== 工具1: DeepSeek — 文章生成 =====

    _STORY_SYSTEM = (
        "你是一位冒险家兼故事大王，去过世界上很多神奇的地方。"
        "你的故事像探险日记，充满惊喜和发现。"
        "故事主角是7岁小男孩「俊宜」（用「他」），他勇敢好奇喜欢探索。"
        "你只输出纯中文文章，不加拼音、不加注解。"
    )
    _ANSWER_SYSTEM = (
        "你是一位好奇心爆棚的探险家，用最简单的语言回答孩子对世界的「为什么」。"
        "主角是7岁小男孩「俊宜」（用「他」），"
        "你用讲故事的方式解释事物，像探险家分享奇妙见闻。"
        "你只输出纯中文内容，不加拼音、不加注解。"
    )

    @staticmethod
    def build_story_prompt(topic: str, characters: list[str], min_chars: int, max_chars: int,
                           behavior_context: str = "", recent_chars_context: str = "",
                           memory_context: str | None = None, zone_context: str = "") -> str:
        """构建故事式文章生成 prompt"""
        chars_str = "、".join(characters)
        memory_block = ""
        if memory_context:
            memory_block = f"\n\n【学习记忆】\n{memory_context}\n- 请呼应未解答的问题\n- 反复使用容易遗忘的字"
        difficulty_hint = ""
        if behavior_context:
            difficulty_hint = f"\n\n【自适应难度调整】\n{behavior_context}"

        # 短文章使用顺口溜风格
        rhyme_rule = ""
        if min_chars <= 100:
            rhyme_rule = (
                "3. 必须写成童谣/顺口溜形式，要求：\n"
                "   - 每行一句，行末必须押同一韵脚（如全押ang韵、全押ao韵）\n"
                "   - 像「小老鼠，上灯台，偷油吃，下不来」那样三字或五字一顿\n"
                "   - 节奏明快，读起来像打拍子\n"
            )
        else:
            rhyme_rule = "3. 每句话不超过 20 个字\n"

        return (
            f"请写一篇适合7岁小男孩阅读的短文，主角叫「俊宜」（用「他」），要求如下：\n\n"
            f"1. 字数 {min_chars}-{max_chars} 字\n"
            f"2. 主题围绕「{topic}」，内容像探险故事一样有趣\n"
            f"{rhyme_rule}"
            f"4. 语言生动，不要教科书腔调\n"
            f"5. 必须自然融入以下生字（每个至少出现1次）：{chars_str}\n"
            f"6. 只输出纯中文文章，不加拼音、翻译、英文"
            f"{memory_block}{recent_chars_context}{difficulty_hint}{zone_context}\n\n"
            f"段落之间用空行分隔，不要加标题和说明文字。"
        )

    @staticmethod
    def build_answer_prompt(topic: str, characters: list[str], min_chars: int, max_chars: int,
                            behavior_context: str = "", recent_chars_context: str = "",
                            memory_context: str | None = None, zone_context: str = "") -> str:
        """构建百科回答式 prompt"""
        chars_str = "、".join(characters)
        memory_block = ""
        if memory_context:
            memory_block = f"\n\n【学习记忆】\n{memory_context}\n- 请呼应未解答的问题"
        difficulty_hint = ""
        if behavior_context:
            difficulty_hint = f"\n\n【自适应难度调整】\n{behavior_context}"

        return (
            f"请用简单的话回答一个孩子提出的问题，要求如下：\n\n"
            f"1. 回答这个问题：「{topic}」\n"
            f"2. 字数 {min_chars}-{max_chars} 字，不要太长\n"
            f"3. 用 6-7 岁孩子能听懂的词句，像爸爸蹲下来跟孩子聊天一样\n"
            f"4. 不要用教科书腔调\n"
            f"5. 开头可以用「你知道吗？」之类的钩子\n"
            f"6. 必须自然融入以下生字（每个至少出现1次）：{chars_str}\n"
            f"7. 只输出纯中文内容，不加拼音、翻译、英文"
            f"{memory_block}{recent_chars_context}{difficulty_hint}{zone_context}\n\n"
            f"段落之间用空行分隔，不要加标题和说明文字。"
        )

    @staticmethod
    def generate_article(topic: str, characters: list[str], min_chars: int = 300,
                         max_chars: int = 800, category: str = "story",
                         behavior_context: str = "", recent_chars_context: str = "",
                         memory_context: str | None = None, zone_context: str = "",
                         known_chars: set[str] | None = None) -> str:
        """调用 DeepSeek 生成文章，如果生字比例 > 15% 自动降低难度重试"""
        from openai import OpenAI
        import httpx
        http_client = httpx.Client(timeout=60.0)
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)

        system = ActLayer._STORY_SYSTEM if category != "answer" else ActLayer._ANSWER_SYSTEM
        if category == "answer":
            prompt = ActLayer.build_answer_prompt(topic, characters, min_chars, max_chars, behavior_context, recent_chars_context, memory_context, zone_context)
        else:
            prompt = ActLayer.build_story_prompt(topic, characters, min_chars, max_chars, behavior_context, recent_chars_context, memory_context, zone_context)

        def _call(p: str) -> str:
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": p}],
                temperature=0.8, max_tokens=8192,
            )
            return (resp.choices[0].message.content or "").strip()

        try:
            content = _call(prompt)
            # DeepSeek 推理模型偶发返回空 content，自动重试（最多2次）
            for attempt in range(2):
                if content:
                    break
                logger.warning(f"DeepSeek returned empty content, retry {attempt+1}")
                content = _call(prompt)

            if not content:
                raise RuntimeError("DeepSeek returned empty content")

            # 难度检查：已知字 ≥ 10 且生字比例 > 15% → 降低难度重试
            if known_chars and len(known_chars) >= 10:
                from ..services.article_generator import estimate_difficulty
                for retry in range(2):
                    ratio = estimate_difficulty(content, known_chars)
                    if ratio <= 0.15:
                        break
                    logger.info(f"Article difficulty {ratio:.0%} > 15%, retry {retry+1}")
                    easier = prompt + f"\n\n【重要】当前生字比例{ratio:.0%}过高。请降低难度：多用简单常用字，减少生僻字，确保至少85%的汉字是常见字。"
                    content = _call(easier)
                    if not content:
                        break

            return content
        except Exception as e:
            logger.error(f"DeepSeek API call failed: {type(e).__name__}: {e}")
            raise

    @staticmethod
    def revise_article(original: str, topic: str, suggestions: str) -> str:
        """调用 DeepSeek 回炉修改文章"""
        from openai import OpenAI
        import httpx
        http_client = httpx.Client(timeout=60.0)
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)

        prompt = (
            f"请根据修改建议优化以下文章。\n\n"
            f"原文主题：{topic}\n原文内容：\n{original}\n\n"
            f"修改建议：{suggestions}\n\n"
            f"要求：保持原文主题和结构，按要求修改。"
            f"主角是7岁小男孩「俊宜」，用「他」。"
            f"每句话不超过20字，语言生动。"
            f"只输出修改后的完整文章，不要加说明文字。"
        )
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "system", "content": ActLayer._STORY_SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=4096,
        )
        content = resp.choices[0].message.content.strip()
        return content if content else original

    @staticmethod
    def generate_image_prompt(topic: str, snippet: str) -> str:
        """生成绘图提示词"""
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{
                "role": "system",
                "content": "你是一位儿童绘本插画师。写一段60字以内的中文绘图提示词。主角是7岁中国小男孩「俊宜」，短发、活泼、爱笑。要求：3D渲染风格、柔和光影、立体感强、景深效果。使用词汇：可爱小男孩、温馨、色彩鲜艳、C4D渲染、皮克斯风格、暖色调。"
            }, {
                "role": "user",
                "content": f"主题：{topic}\n片段：{snippet[:200]}\n\n写一段绘图提示词（注意主角是7岁小男孩俊宜）：",
            }],
            temperature=0.9, max_tokens=200,
        )
        prompt = resp.choices[0].message.content.strip()
        return prompt if prompt else f"可爱温馨的儿童插画，主题是{topic}，主角是7岁小男孩俊宜，短发，活泼爱笑，色彩鲜艳，暖色调"

    @staticmethod
    def generate_image(prompt: str) -> str | None:
        """调用智谱 CogView 生成配图"""
        import httpx
        if not GLM_API_KEY:
            return None
        try:
            resp = httpx.post(
                "https://open.bigmodel.cn/api/paas/v4/images/generations",
                headers={"Authorization": f"Bearer {GLM_API_KEY}", "Content-Type": "application/json"},
                json={"model": GLM_IMAGE_MODEL, "prompt": prompt},
                timeout=60,
            )
            if resp.status_code == 200:
                urls = resp.json().get("data", [])
                if urls:
                    return urls[0].get("url")
        except Exception:
            pass
        return None

    # ===== 工具2: 科大讯飞 — 语音识别 =====

    @staticmethod
    async def recognize_speech_from_wav(wav_data: bytes) -> str:
        """科大讯飞 WebSocket 语音听写"""
        pcm = ActLayer._wav_to_pcm(wav_data)
        if not pcm:
            return ""

        ws_url = ActLayer._build_xfyun_url()
        result_text = ""

        try:
            import websockets
        except ImportError:
            raise RuntimeError("请安装 websockets: pip install websockets")

        async with websockets.connect(ws_url, ping_interval=10, close_timeout=5) as ws:
            frame_size = 8000
            for i in range(0, len(pcm), frame_size):
                buf = pcm[i:i + frame_size]
                is_last = i + frame_size >= len(pcm)
                status = 2 if is_last else (0 if i == 0 else 1)

                if i == 0:
                    d = {
                        "common": {"app_id": XFYUN_APP_ID},
                        "business": {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo": 1, "vad_eos": 10000},
                        "data": {"status": 0, "format": "audio/L16;rate=16000", "audio": base64.b64encode(buf).decode(), "encoding": "raw"},
                    }
                else:
                    d = {"data": {"status": status, "format": "audio/L16;rate=16000", "audio": base64.b64encode(buf).decode(), "encoding": "raw"}}
                await ws.send(json.dumps(d))
                if is_last:
                    break

            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    if data.get("code") and data["code"] != 0:
                        raise RuntimeError(f"讯飞错误 [{data['code']}]: {data.get('message', '未知')}")
                    result = data.get("data", {}).get("result", {})
                    if result:
                        for w in result.get("ws", []):
                            for cw in w.get("cw", []):
                                result_text += cw.get("w", "")
            except (asyncio.TimeoutError, Exception):
                pass

        return result_text

    @staticmethod
    def _wav_to_pcm(wav_data: bytes) -> bytes:
        with wave.open(io.BytesIO(wav_data), 'rb') as wf:
            return wf.readframes(wf.getnframes())

    @staticmethod
    def _build_xfyun_url() -> str:
        now = datetime.now()
        date_str = format_date_time(mktime(now.timetuple()))
        signature_origin = f"host: ws-api.xfyun.cn\ndate: {date_str}\nGET /v2/iat HTTP/1.1"
        signature_sha = base64.b64encode(
            hmac.new(XFYUN_API_SECRET.encode(), signature_origin.encode(), hashlib.sha256).digest()
        ).decode()
        authorization_origin = f'api_key="{XFYUN_API_KEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
        authorization = base64.b64encode(authorization_origin.encode()).decode()
        params = {"authorization": authorization, "date": date_str, "host": "ws-api.xfyun.cn"}
        return "wss://ws-api.xfyun.cn/v2/iat?" + urlencode(params)

    # ===== 工具3: edge-tts — 语音合成 =====

    @staticmethod
    async def synthesize_speech(char: str) -> bytes:
        """用 edge-tts 合成单个汉字的语音"""
        import edge_tts
        buffer = io.BytesIO()
        communicate = edge_tts.Communicate(char, "zh-CN-XiaoxiaoNeural")
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        return buffer.getvalue()

    # ===== 拼音注音 =====

    @staticmethod
    def annotate_text(text: str) -> dict:
        """pypinyin 精准拼音注音"""
        from ..services.pinyin_service import annotate_text as _annotate
        return _annotate(text)

    @staticmethod
    def extract_characters(text: str) -> list[str]:
        """从文本提取所有汉字"""
        return list(dict.fromkeys(re.findall(r'[一-鿿]', text)))
