"""学生管理"""
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Student, DailyCharacter, DailyArticle, ForgottenCharacter, CuriosityEvent, ReadingBehavior, UserWordMastery
from ..services.face_image_generator import generate_avatar

router = APIRouter(prefix="/api/students", tags=["学生管理"])


# ===== X-Student-ID 依赖注入 =====

async def get_current_student_id(x_student_id: int = Header(default=1)):
    """从请求头 X-Student-ID 获取当前学生ID，默认=1"""
    return x_student_id


# ===== Student CRUD =====

class StudentCreate(BaseModel):
    name: str
    avatar: str = ""


@router.get("")
def list_students(db: Session = Depends(get_db)):
    return db.query(Student).order_by(Student.id).all()


@router.post("")
def create_student(body: StudentCreate, db: Session = Depends(get_db)):
    s = Student(name=body.name, avatar=body.avatar or get_default_avatar(body.name))
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    s = db.query(Student).filter(Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="学生不存在")
    if student_id == 1:
        raise HTTPException(status_code=400, detail="不能删除默认学生")
    # 级联删除学习数据
    for model in [DailyCharacter, DailyArticle, ForgottenCharacter, CuriosityEvent, ReadingBehavior, UserWordMastery]:
        db.query(model).filter(model.student_id == student_id).delete()
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.post("/{student_id}/generate-avatar")
def generate_student_avatar(student_id: int, use_gpu: bool = Query(False, description="是否使用GPU生成（默认GLM-Image）"), db: Session = Depends(get_db)):
    """为指定学生生成专属卡通头像（基于 static/ref 下的参考照片）"""
    s = db.query(Student).filter(Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="学生不存在")

    url = generate_avatar(use_gpu=use_gpu)
    if not url:
        raise HTTPException(status_code=500, detail="头像生成失败")

    s.avatar = url
    db.commit()
    db.refresh(s)
    return {"id": s.id, "name": s.name, "avatar": s.avatar}


def get_default_avatar(name: str) -> str:
    emojis = ["🐯", "🦁", "🐼", "🐨", "🐰", "🦊", "🐸", "🐵", "🐶", "🐱", "🌈", "⭐", "🌟", "💫", "🎈"]
    h = sum(ord(c) for c in name)
    return emojis[h % len(emojis)]
