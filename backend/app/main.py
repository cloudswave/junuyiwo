from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers import characters, articles, review, dashboard, curiosity, knowledge, memory, voice, tts, asr, reading_behaviors, students, zones, knowledge_base
from .routers.recent_chars import router as recent_chars_router

app = FastAPI(title="俊宜识字系统 API", version="1.0.0")

AUDIO_DIR = Path(__file__).resolve().parent.parent / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "generated").mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recent_chars_router)
app.include_router(characters.router)
app.include_router(articles.router)
app.include_router(review.router)
app.include_router(dashboard.router)
app.include_router(curiosity.router)
app.include_router(knowledge.router)
app.include_router(memory.router)
app.include_router(voice.router)
app.include_router(tts.router)
app.include_router(asr.router)
app.include_router(reading_behaviors.router)
app.include_router(students.router)
app.include_router(zones.router)
app.include_router(knowledge_base.router)

app.mount("/api/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}
