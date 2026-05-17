import asyncio
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from pathlib import Path

router = APIRouter(prefix="/api/tts", tags=["TTS"])

AUDIO_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "audio"
TTS_CACHE = AUDIO_ROOT / "tts_cache"
TTS_CACHE.mkdir(parents=True, exist_ok=True)


def _cache_path(char: str) -> Path:
    return TTS_CACHE / f"{char}.mp3"


@router.get("/speak/{char}")
async def tts_speak(char: str):
    """默认 TTS（edge-tts XiaoyiNeural），带磁盘缓存"""
    cache = _cache_path(char)
    if cache.exists():
        return Response(content=cache.read_bytes(), media_type="audio/mpeg")

    import io
    import edge_tts

    voice = os.getenv("TTS_VOICE", "zh-CN-XiaoyiNeural")
    communicate = edge_tts.Communicate(char, voice)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    audio_bytes = buffer.getvalue()
    try:
        cache.write_bytes(audio_bytes)
    except OSError:
        pass
    return Response(content=audio_bytes, media_type="audio/mpeg")


class PreloadRequest(BaseModel):
    chars: list[str]


@router.post("/preload")
async def tts_preload(body: PreloadRequest):
    """批量预热 TTS 缓存（文章加载时调用，后台生成不阻塞）"""
    async def _gen_one(char: str):
        cache = _cache_path(char)
        if cache.exists():
            return
        try:
            import io
            import edge_tts
            voice = os.getenv("TTS_VOICE", "zh-CN-XiaoyiNeural")
            communicate = edge_tts.Communicate(char, voice)
            buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])
            cache.write_bytes(buffer.getvalue())
        except Exception:
            pass

    sem = asyncio.Semaphore(8)
    async def _with_limit(c):
        async with sem:
            await _gen_one(c)

    await asyncio.gather(*[_with_limit(c) for c in body.chars[:20]], return_exceptions=True)
    cached = [c for c in body.chars if _cache_path(c).exists()]
    return {"total": len(body.chars), "cached": len(cached)}


class SpeakTextRequest(BaseModel):
    text: str


@router.post("/speak-text")
async def tts_speak_text(body: SpeakTextRequest):
    """朗读整段文字（edge-tts）"""
    import io
    import edge_tts

    voice = os.getenv("TTS_VOICE", "zh-CN-XiaoyiNeural")
    communicate = edge_tts.Communicate(body.text, voice)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    return Response(content=buffer.getvalue(), media_type="audio/mpeg")
