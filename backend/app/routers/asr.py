"""语音识别 ASR 路由"""
from fastapi import APIRouter, HTTPException, UploadFile, File

from ..services.asr_service import recognize_text, is_configured

router = APIRouter(prefix="/api/asr", tags=["语音识别"])


@router.post("/recognize")
async def asr_recognize(file: UploadFile = File(...)):
    """上传录音文件，返回识别出的中文文本"""
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="语音识别服务未配置。请设置环境变量 XFYUN_APP_ID / XFYUN_API_KEY / XFYUN_API_SECRET"
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="录音文件为空")

    try:
        text = await recognize_text(audio_bytes)
        return {"text": text}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
