"""科大讯飞 语音听写 (ASR) 服务 — 基于官方 WebSocket demo"""
import json
import base64
import hashlib
import hmac
import asyncio
import io
import wave
from datetime import datetime
from time import mktime
from wsgiref.handlers import format_date_time
from urllib.parse import urlencode
from ..config import settings


XFYUN_APP_ID = getattr(settings, "XFYUN_APP_ID", "")
XFYUN_API_KEY = getattr(settings, "XFYUN_API_KEY", "")
XFYUN_API_SECRET = getattr(settings, "XFYUN_API_SECRET", "")

IAT_WS_URL = "wss://ws-api.xfyun.cn/v2/iat"
STATUS_FIRST = 0
STATUS_CONTINUE = 1
STATUS_LAST = 2


def is_configured() -> bool:
    return bool(XFYUN_APP_ID and XFYUN_API_KEY and XFYUN_API_SECRET)


def _build_url() -> str:
    """按官方 demo 方式生成鉴权 URL"""
    now = datetime.now()
    date = format_date_time(mktime(now.timetuple()))

    # 签名原文
    signature_origin = f"host: ws-api.xfyun.cn\ndate: {date}\nGET /v2/iat HTTP/1.1"
    signature_sha = base64.b64encode(
        hmac.new(
            XFYUN_API_SECRET.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    authorization_origin = (
        f'api_key="{XFYUN_API_KEY}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature_sha}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")

    params = {
        "authorization": authorization,
        "date": date,
        "host": "ws-api.xfyun.cn",
    }
    return IAT_WS_URL + "?" + urlencode(params)


def _wav_to_pcm_base64(wav_data: bytes) -> bytes:
    """从 WAV 提取 PCM 数据"""
    with wave.open(io.BytesIO(wav_data), 'rb') as wf:
        return wf.readframes(wf.getnframes())


async def recognize(audio_data: bytes) -> str:
    if not is_configured():
        raise RuntimeError("科大讯飞 API 未配置")
    try:
        import websockets
    except ImportError:
        raise RuntimeError("请安装 websockets: pip install websockets")

    pcm = _wav_to_pcm_base64(audio_data)
    if len(pcm) == 0:
        return ""

    ws_url = _build_url()
    result_text = ""
    result_event = asyncio.Event()
    result_container = {"text": ""}

    async with websockets.connect(ws_url, ping_interval=10, close_timeout=5) as ws:

        async def send_audio():
            frame_size = 8000
            status = STATUS_FIRST

            for i in range(0, len(pcm), frame_size):
                buf = pcm[i:i + frame_size]

                if i + frame_size >= len(pcm):
                    status = STATUS_LAST

                if status == STATUS_FIRST:
                    d = {
                        "common": {"app_id": XFYUN_APP_ID},
                        "business": {
                            "domain": "iat",
                            "language": "zh_cn",
                            "accent": "mandarin",
                            "vinfo": 1,
                            "vad_eos": 10000,
                        },
                        "data": {
                            "status": 0,
                            "format": "audio/L16;rate=16000",
                            "audio": base64.b64encode(buf).decode("utf-8"),
                            "encoding": "raw",
                        },
                    }
                    await ws.send(json.dumps(d))
                    status = STATUS_CONTINUE
                else:
                    d = {
                        "data": {
                            "status": status,
                            "format": "audio/L16;rate=16000",
                            "audio": base64.b64encode(buf).decode("utf-8"),
                            "encoding": "raw",
                        }
                    }
                    await ws.send(json.dumps(d))

                if status == STATUS_LAST:
                    break
                # 不 sleep，全速发送

        async def recv_result():
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=15)
                    data = json.loads(msg)
                    code = data.get("code")
                    if code is not None and code != 0:
                        raise RuntimeError(f"讯飞ASR错误 [{code}]: {data.get('message', '未知')}")
                    result = data.get("data", {}).get("result", {})
                    if result:
                        ws_data = result.get("ws", [])
                        for w in ws_data:
                            for cw in w.get("cw", []):
                                result_container["text"] += cw.get("w", "")
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass
            finally:
                result_event.set()

        # 并发发送和接收
        send_task = asyncio.ensure_future(send_audio())
        recv_task = asyncio.ensure_future(recv_result())
        await asyncio.wait([send_task, recv_task], timeout=30)

        result_text = result_container["text"]

    return result_text


async def recognize_text(audio_data: bytes) -> str:
    if not is_configured():
        return ""
    try:
        return await recognize(audio_data)
    except Exception as e:
        raise RuntimeError(f"语音识别失败: {e}")
