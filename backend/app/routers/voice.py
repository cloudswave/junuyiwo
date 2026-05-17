import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import VoiceProfile
from .students import get_current_student_id

router = APIRouter(prefix="/api/voice", tags=["真人录音"])

# 统一使用 data/audio，与 main.py 的 /api/audio 静态挂载一致
AUDIO_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "audio"


def _profile_dir(profile_id: int) -> Path:
    return AUDIO_ROOT / str(profile_id)


class ProfileCreate(BaseModel):
    name: str


# ===== Profile CRUD =====

@router.get("/profiles")
def list_profiles(db: Session = Depends(get_db), student_id: int = Depends(get_current_student_id)):
    profiles = db.query(VoiceProfile).filter(VoiceProfile.student_id == student_id).order_by(VoiceProfile.created_at.desc()).all()
    result = []
    for p in profiles:
        d = _profile_dir(p.id)
        char_count = len([f for f in d.glob("*.webm") if not f.name.startswith("_")]) if d.exists() else 0
        result.append({
            "id": p.id,
            "name": p.name,
            "sample_path": p.sample_path,
            "prompt_text": p.prompt_text,
            "char_count": char_count,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return result


@router.post("/profiles")
def create_profile(body: ProfileCreate, db: Session = Depends(get_db)):
    p = VoiceProfile(name=body.name)
    db.add(p)
    db.commit()
    db.refresh(p)
    _profile_dir(p.id).mkdir(parents=True, exist_ok=True)
    return {"id": p.id, "name": p.name, "char_count": 0, "sample_path": None, "prompt_text": None, "created_at": p.created_at.isoformat()}


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    p = db.query(VoiceProfile).filter(VoiceProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="样版不存在")
    db.delete(p)
    db.commit()
    d = _profile_dir(profile_id)
    if d.exists():
        shutil.rmtree(d)
    return {"ok": True}


# ===== Per-character recording =====

@router.put("/profiles/{profile_id}/chars/{char}")
def upload_char_audio(profile_id: int, char: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """为某个字上传/录制真人发音"""
    p = db.query(VoiceProfile).filter(VoiceProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="样版不存在")

    d = _profile_dir(profile_id)
    d.mkdir(parents=True, exist_ok=True)

    path = d / f"{char}.webm"
    with open(path, "wb") as f:
        f.write(file.file.read())

    # 标记 profile 已使用
    if not p.sample_path:
        p.sample_path = str(d)
        db.commit()

    return {"profile_id": profile_id, "char": char, "size": path.stat().st_size}


@router.get("/profiles/{profile_id}/chars")
def list_recorded_chars(profile_id: int, db: Session = Depends(get_db)):
    """列出某样版已录音的所有字"""
    p = db.query(VoiceProfile).filter(VoiceProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="样版不存在")
    d = _profile_dir(profile_id)
    if not d.exists():
        return []
    return sorted([f.stem for f in d.glob("*.webm") if not f.name.startswith("_")])


@router.delete("/profiles/{profile_id}/chars/{char}")
def delete_char_audio(profile_id: int, char: str, db: Session = Depends(get_db)):
    """删除某个字的真人发音"""
    p = db.query(VoiceProfile).filter(VoiceProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="样版不存在")
    path = _profile_dir(profile_id) / f"{char}.webm"
    if path.exists():
        os.remove(path)
    return {"ok": True}


@router.post("/profiles/{profile_id}/batch-check")
def batch_check_chars(profile_id: int, body: "BatchCheckRequest", db: Session = Depends(get_db)):
    """批量检查哪些字已有录音"""
    p = db.query(VoiceProfile).filter(VoiceProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="样版不存在")
    result = {}
    for c in body.chars:
        result[c] = (_profile_dir(profile_id) / f"{c}.webm").exists()
    return result


class BatchCheckRequest(BaseModel):
    chars: list[str]


# ===== Reference audio (for future voice cloning) =====

@router.put("/profiles/{profile_id}/reference")
async def upload_reference(profile_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传参考音频（预留）"""
    p = db.query(VoiceProfile).filter(VoiceProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="样版不存在")
    d = _profile_dir(profile_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "_reference.webm"
    with open(path, "wb") as f:
        f.write(await file.read())
    return {"profile_id": profile_id, "size": path.stat().st_size}
