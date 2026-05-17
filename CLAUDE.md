# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Branch Safety Rules

- **NEVER** work on the `master` branch. All development must be on `feature-dev`.
- **NEVER** commit directly to `master`. The git pre-commit hook blocks this, and Claude Code hooks add a second layer.
- Before starting any work, verify your branch: `git branch --show-current`
- If you accidentally start working on master, run the rescue script immediately:

  ```bash
  bash scripts/rescue-from-master.sh
  ```

- If you already committed on master by mistake:

  ```bash
  git reset HEAD~1       # undo the commit, keep changes
  bash scripts/rescue-from-master.sh
  ```

## Development Commands

### Backend (Python FastAPI)

```bash
cd backend
pip install -r requirements.txt

# Production (DB=junyi_word, port 8000)
python run.py

# Development (DB=junyi_word_dev, port 8001)
$env:DB_NAME = "junyi_word_dev"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend (React + TypeScript + Vite)

```bash
cd frontend
npm install
npm run dev              # port 3000, proxies /api → 127.0.0.1:8000
# Dev mode (port 3001, proxies /api → 127.0.0.1:8001):
$env:VITE_BACKEND_PORT = "8001"; npm run dev -- --port 3001
npm run build            # TypeScript check + Vite production build
```

### Database Migrations

```bash
# New install
mysql -u root -p < sql/init.sql

# Apply migrations (idempotent, safe to re-run)
mysql -u root -p junyi_word < sql/migration_00X_xxx.sql
# Or Windows: double-click update_db.bat
```

## Architecture

This is a full-stack AI-powered Chinese literacy platform for 6-8 year old children. The backend is organized around an **AI Agent four-layer loop** (Perceive → Reason → Act → Remember) and a **LangGraph state graph** for curiosity-driven content generation.

### Layered Backend Structure

```
routers/  (15 modules) — HTTP handlers, thin: parse request → call service → return JSON
    ↓
services/ (14 modules) — Business logic, orchestrate multiple AI APIs
    ↓
agent/    (6 modules)  — Agent framework + LangGraph state machines
    ├── perceive.py           — Reading behavior tracking, voice input
    ├── reason.py             — Difficulty adaptation, tier promotion/deranking
    ├── act.py                — DeepSeek / XFYun / CogView / edge-tts tool calls
    ├── remember.py           — Character, behavior, article CRUD (the "memory" layer)
    ├── loop.py               — AgentLoop orchestrator
    └── curiosity_graph.py ★  — LangGraph state graph for curiosity module
```

- [backend/app/main.py](backend/app/main.py) — FastAPI app, registers all routers, mounts static files at `/static` and audio at `/api/audio`
- [backend/app/config.py](backend/app/config.py) — Loads `.env`, exports DB/AI keys, plus `EducationConfig` class (review intervals, skill levels, density tiers, reading levels, cognition prompts, advanced keywords)
- [backend/app/models.py](backend/app/models.py) — SQLAlchemy models (22 tables): `Student`, `DailyCharacter`, `DailyArticle`, `ForgottenCharacter`, `CuriosityEvent`, `InterestEvolution`, `KnowledgeNode`, `KnowledgeLink`, `LearningRecord`, `VoiceProfile`, `UserWordMastery`, `ReadingBehavior`, `TargetCharacter`, `ScoutCharacter`, `AllyCharacter`, `LostCharacter`, `ArticleReadStatus`, `KnowledgeEntry`, `StudentTextbookConfig`, `DifficultyFeedback`, `ConversationSession`, `ConversationTurn`, `ArticleSeries`
- [backend/app/database.py](backend/app/database.py) — SQLAlchemy engine, session, `get_db` dependency, `init_db()` (creates tables on startup)

### Curiosity State Graph (LangGraph)

The curiosity module (`curiosity_graph.py`) is a LangGraph StateGraph with 10 nodes and 3 execution paths:

```
START → node_load_event → route_by_mode
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    one_shot            conversation           series
          │                   │                   │
          ▼                   ▼                   ▼
  generate_article    start_conversation    decompose_topic
          │                   │                   │
          ▼                   ▼                   ▼
         END          wait_for_turn        generate_chapter
                       (multi-turn)              │
                          │              ┌───────┴───────┐
                          ▼              │                   │
                  generate_article   next? yes         next? no
                          │              │                   │
                          ▼              ▼                   ▼
                         END      generate_chapter    abandon_series
```

State is checkpointed via `MemorySaver` per `thread_id` (event_id), enabling pause/resume across API calls.

### Frontend Structure

- 11 pages in [frontend/src/pages/](frontend/src/pages/)
- 2 key components: `AppLayout` (sidebar, student switcher, voice FloatButton) and `ArticleReader` (interactive pinyin reader with tap-to-speak, animations, series chapter navigation)
- [frontend/src/services/api.ts](frontend/src/services/api.ts) — All API calls, types, and axios interceptor that injects `X-Student-ID` header
- [frontend/src/store/useStore.ts](frontend/src/store/useStore.ts) — Zustand global state (today's data, stats, characters, loading flags)
- [frontend/vite.config.ts](frontend/vite.config.ts) — Dev proxy: `/api` → `127.0.0.1:${VITE_BACKEND_PORT||8000}`

### Multi-Student Data Isolation

Every table has a `student_id` column. The frontend axios interceptor reads `localStorage.currentStudentId` and sends `X-Student-ID` header on every request. The backend reads this header per-request — no middleware, each router calls it explicitly.

### Key Design Patterns

- **Environment isolation**: Same code, two databases (`junyi_word` / `junyi_word_dev`), two port sets (8000/3000 vs 8001/3001). Selected via `DB_NAME` env var.
- **Config is centralized**: All education parameters live in `EducationConfig` class in config.py — review intervals, skill density, reading levels, mastery thresholds, cognition prompts. No scattered magic numbers.
- **LangGraph state graph**: Curiosity answer generation uses a StateGraph with 3 modes (one_shot / conversation / series), checkpointed per event_id for pause/resume.
- **Idempotent migrations**: All SQL migration files use `IF NOT EXISTS` / `IF EXISTS`, safe to rerun.
- **Conditional vector search**: Pinecone is optional. Below `VECTOR_DB_ARTICLE_THRESHOLD` articles, falls back to MySQL keyword search automatically.
- **Tiered character system**: Characters move through 4 zones (target/scout/ally/lost) with automated promotion logic across articles.
- **Cognitive level adaptation**: Answer depth auto-adjusts based on student's cognition_level (1-3) and advanced keyword detection in questions.

### External AI Services

| Service | Purpose | Config Keys |
|---------|---------|-------------|
| DeepSeek | Article generation, revision, curiosity answers | `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` |
| 智谱 CogView-3-Plus | Article cover images | `GLM_API_KEY`, `GLM_IMAGE_MODEL` |
| 科大讯飞 | Voice recognition (WebSocket streaming) | `XFYUN_APP_ID`, `XFYUN_API_KEY`, `XFYUN_API_SECRET` |
| edge-tts | Chinese character pronunciation (free) | No key needed |
| Pinecone | Vector semantic search (optional) | `PINECONE_API_KEY`, `PINECONE_ENV`, `PINECONE_INDEX_NAME` |
| Stable Diffusion + IP-Adapter FaceID | Student avatar generation (GPU required) | Local GPU, falls back to CogView |
