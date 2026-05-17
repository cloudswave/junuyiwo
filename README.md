# 俊宜识字系统 — AI Agent 实践项目

> 本项目为学习 AI Agent 架构期间的工程实践。以"孩子识字阅读"为场景，完整实现了 Agent 的感知→决策→执行→记忆闭环。详见 [Agent 架构](#agent-架构) 章节。

基于 AI 的小学语文识字学习平台，专为一年级（6-8岁）儿童设计。通过 AI 生成带拼音的趣味短文，结合遗忘曲线复习机制和掌握度追踪，让孩子在阅读中快乐识字。支持 PC 浏览器和平板 APK。

## 核心功能

- **AI 文章生成** — 根据已学生字，DeepSeek 自动生成适合一年级阅读的文章，支持两种生成模式：
  - 故事式：围绕主题写一篇有趣的短文，像讲故事一样，融入生字
  - 百科回答式：用简单的话回答孩子的问题，可一键生成或通过深入对话精准生成
  - 主题支持语音输入，边说边填
- **课本式拼音注音** — pypinyin 精准注音，22号字体课本排版，拼音在汉字上方
- **★ 沉浸式互动阅读** — 段落入场动画、点字音效反馈、发声光晕、阅读进度条、读完庆祝飘屏、涟漪扩散、全文朗读（暂停/继续/停止），纯 CSS + Web API 实现
- **多孩子支持** — 支持多个孩子独立数据（字库、文章、遗忘记录、好奇心等），侧边栏一键切换，数据完全隔离
- **★ 专属卡通头像** — 本地 Stable Diffusion + IP-Adapter FaceID 基于参考照片生成人脸一致头像，无 GPU 降级智谱 CogView
- **三层字库晋升** — 新鲜字库(1)→熟悉字库(2)→老朋友字库(3)，3次确认晋升，跨文章去重
- **点字自动降级** — 阅读中点击生字即发声引读，同时自动标记"不认识"触发字库降级，无需家长手动判断
- **隐式反馈自适应** — 采集点字行为自动分析难度，下次生成文章时动态调整难度和生字密度
- **文章回炉修改** — 输入修改建议，AI 根据建议优化已有文章，原地更新无需跳转
- **遗忘曲线复习** — 基于艾宾浩斯遗忘曲线，自动排期下次复习时间，6 级间隔 (1/3/7/14/30/60 天)
- **语音录入（科大讯飞）** — 基于科大讯飞 语音听写 WebSocket API，说出词语自动提取生字，国内网络流畅
- **文章配图（智谱 CogView）** — 自动生成封面和内嵌插图，主角为 7 岁小男孩俊宜
- **点字发声（edge-tts）** — 点击汉字即听发音，基于 Microsoft Edge TTS，平板/PC 均可
- **真人录音** — 逐字录制真人发音，点字优先播放录音，支持多声音档案
- **★ 好奇心系统** — 完整的好奇心驱动阅读闭环，详见 [好奇心模块](#好奇心模块)
- **★ 知识库系统** — 双层知识体系：校内教材知识（人教版一年级上下册预置，按课文+知识点结构化）+ 校外科普知识（兴趣驱动 AI 自动生成 + 家长手动录入），AI 生成文章时自动引用知识库内容
- **★ 分支安全护栏** — Git pre-commit hook 阻止 master 分支提交 + 一键救援脚本 `rescue-from-master.sh` + Claude Code 会话启动检查
- **Android 平板支持** — 基于 Capacitor 打包 APK，适配学而思等学习平板

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 + Zustand |
| 后端 | Python FastAPI + SQLAlchemy + pymysql |
| AI 文章 | DeepSeek（文章生成） |
| AI 配图 | 智谱 CogView-3-Plus + Stable Diffusion + IP-Adapter FaceID（人脸一致性配图） |
| 语音识别 | 科大讯飞 语音听写 API（WebSocket 流式版） |
| 语音合成 | Microsoft Edge TTS（edge-tts，免费不限量） |
| 移动端 | Capacitor + Android WebView（APK 打包） |
| 拼音 | pypinyin（非 AI 生成，保证准确） |
| 数据库 | MySQL 8.2 |

## Agent 架构

本项目是在学习 AI Agent 期间构建的实践项目，体现了完整的 Agent 四要素闭环：

```
感知 (Perceive) → 决策 (Reason) → 执行 (Act) → 记忆 (Remember)
     ↑                                            │
     └────────────────── 闭环 ─────────────────────┘
```

### 感知层 — Agent 的眼睛和耳朵

| 能力 | 采集数据 | 实现 |
|------|----------|------|
| 点字行为追踪 | 孩子点击了哪个字、点了几次 | `ArticleReader` → `behaviorApi.report()` → `reading_behaviors` 表 |
| 字库自动降级 | 点字=不认识，自动触发降级 | `handleCharTap` → `reviewApi.recordForgotten()` |
| 语音识别输入 | 孩子说出的生字/问题 | `asr_service.py` → 科大讯飞 WebSocket API |

### 决策层 — Agent 的大脑

| 决策 | 依据 | 实现 |
|------|------|------|
| 文章难度自适应 | 近 7 天点字频率 | `build_behavior_context()` → 动态注入生成 prompt |
| 生字密度调整 | 高频点击字 → 降低密度 | 减少生字数量、缩短句子 |
| 三层字库晋升/降级 | 连续认识→升库，点字→降级 | `mark_character_known()` |

### 执行层 — Agent 的手

| 工具 | 调用方式 | 用途 |
|------|----------|------|
| DeepSeek | OpenAI 兼容 API | 文章生成、回炉修改、好奇心回答 |
| Stable Diffusion + IP-Adapter | 本地 GPU (4080S) | 人脸一致性配图/头像生成 |
| 智谱 CogView-3-Plus | HTTP REST API | 配图/头像降级方案（无 GPU 时自动切换） |
| 科大讯飞 语音听写 | WebSocket 流式 API | 语音转文字 |
| Edge TTS | `edge-tts` 库 | 汉字发音合成 |
| Web Speech API | 浏览器内置 | 点字发声降级方案、全文朗读 |

### 记忆层 — Agent 的内外部记忆

| 记忆类型 | 存储 | 内容 |
|------|------|------|
| 短期记忆 | `reading_behaviors` | 近 7 天点字频率 |
| 长期记忆 | `daily_characters` (tier 1/2/3) | 三层字库状态 |
| 情景记忆 | `curiosity_events` / `daily_articles` | 提问记录、阅读历史 |
| 语义记忆 | `knowledge_nodes` / `knowledge_links` | 知识图谱 |
| 偏好记忆 | Phase 2 规划中 | 主题偏好、阅读完成率 |

### 闭环示例

```
孩子读文章 → 点「春」字听发音
     ↓
感知：behaviorApi.report({char:"春", action:"char_tap"})
     ↓
记忆：reading_behaviors 表累计 "春" 点击 3 次
     ↓
决策：build_behavior_context() 发现高频点击
     │   注入 prompt："「春」被点击 3 次，请加强重复"
     ↓
执行：DeepSeek 生成新文章，难度降低，多重复"春"
     ↓
感知：孩子不再点"春" → 标记认识 → 字库晋升
```

## 好奇心模块

好奇心是整个系统的"内容引擎"——孩子提出问题，系统捕捉后转化为个性化阅读文章。核心理念是"让孩子的好奇心驱动识字阅读"。

### 问题捕捉

| 入口 | 方式 | 说明 |
|------|------|------|
| **语音提问** | AppLayout 全局浮动麦克风 | 孩子说 → 科大讯飞 ASR → 自动建事件 → DeepSeek 后台提取标签 |
| **阅读中提问** | ArticleReader 工具栏"提问"按钮 | 读到不懂的地方即时提问，自动关联当前文章 |
| **手动录入** | CuriosityPage 表单 | 家长代为输入或粘贴孩子的问题 |

### 兴趣演化追踪

- 每个问题创建后，DeepSeek 异步提取 2-3 个兴趣标签（天文、科学、动植物等），自动更新 `interest_evolution` 表
- 30 天窗口内统计标签提及频率，计算兴趣强度（0-1）和趋势（rising / stable / declining）
- 仪表盘实时展示热门兴趣和最近问题

### 智能推荐引擎

三源融合推荐 (`GET /api/curiosity/recommend`)：

```
未回答问题（权重 3）→ 最优先解答孩子已经提出的疑问
热门兴趣   （权重 2）→ 基于 30 天兴趣追踪推荐方向
四区字库   （权重 1）→ 匹配教学区生字，让新字学习有情境
```

返回 Top 5 推荐主题，家长一键生成文章。

### 文章回答生成（两种模式）

**一键生成** (`generate_answer_for_event`)：
```
提取生字 → 记忆上下文 → 知识库检索 → 认知水平适配 → DeepSeek → 保存文章 → 链接事件 → 写入今日生字
```

**深入对话**（新增）：
```
开启对话 → 多轮交互探测知识边界 → 认知等级动态升降 → 生成定制文章 → 回哺知识库
```

对话机制的核心价值：传统一键回答是"猜孩子知道多少"，对话是"实时探测"。孩子说出专业术语（如"裂变""引力坍缩"），系统立即提升回答深度；孩子表示困惑，系统降回比喻。

### 认知水平自适应

| 等级 | 名称 | 触发条件 | 回答策略 |
|------|------|---------|---------|
| L1 | 启蒙 | 默认 | 最浅显比喻，避免专业术语 |
| L2 | 进阶 | 问题中出现高级词汇（裂变、引力、核聚变等 30+ 词） | 可用基础科学术语 + 生活类比 |
| L3 | 深入 | 连续 3 次"太简单"反馈 | 深入解释原理，使用准确术语 |

升级机制：
- **自动检测**：问题中的高级词汇（如"裂变""能量守恒"）自动提升 1 级
- **反馈驱动**：文章底部"太简单了 👶 / 太难了 🧠"按钮，连续 3 次触发升降
- **家长手动**：直接修改学生 `cognition_level`

### 数据模型

| 表 | 说明 |
|---|---|
| `curiosity_events` | 问题记录（原始文本、标签、回答状态、关联文章） |
| `interest_evolution` | 兴趣标签演变（首次提及、强度、趋势） |
| `conversation_sessions` | 对话会话（关联事件、状态、轮次、最终文章） |
| `conversation_turns` | 对话轮次（角色、内容、时间） |
| `difficulty_feedback` | 难度反馈（too_easy / too_hard，用于校准认知等级） |

## 开发与生产隔离

同一份代码，通过数据库隔离生产/开发环境：

```
同一份代码 ─┬─ 生产环境: DB=junyi_word, 端口 8000
            └─ 开发环境: DB=junyi_word_dev, 端口 8001
```

### 开发流程

```bash
# 1. 开新分支
git checkout -b feature-xxx

# 2. 改代码...

# 3. 启动开发环境测试（独立数据库，可随便折腾）
start-dev.bat

# 4. 确认没问题后合并
git checkout master
git merge feature-xxx

# 5. 重启生产后端上线
```

### 清空开发数据库

```bash
# 清空开发库数据重新来过
cd backend
set DB_NAME=junyi_word_dev
python -c "from app.main import app; from app.database import init_db, Base, engine; [Base.metadata.drop_all(bind=engine, tables=[t]) for t in reversed(Base.metadata.sorted_tables) if t.name != 'students']; from app.database import init_db; init_db()"
```

⚠️ 生产库 `junyi_word` 和开发库 `junyi_word_dev` 物理隔离，互不影响。

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.2

### 后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 初始化数据库（全新安装）
mysql -u root -p < ../sql/init.sql

# 如果已有数据，需要升级数据库结构：
# Windows: 双击项目根目录的 update_db.bat
# 其他平台: 依次运行 sql/migration_*.sql

# ⚠️ 多孩子支持数据库升级（v2.0）：
# 直接执行 sql/migration_005_multi_student.sql
mysql -u root -p junyi_word < ../sql/migration_005_multi_student.sql

# 配置 .env（填入 API 密钥）
cp .env.example .env

# 启动
python run.py
```

### 前端

```bash
cd frontend

npm install
npm run dev
```

### .env 配置

```env
# DeepSeek API（文章生成）
DEEPSEEK_API_KEY=your_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# GLM-Image（文章封面图）
GLM_API_KEY=your_key
GLM_IMAGE_MODEL=GLM-Image

# Pinecone 向量数据库（可选，文章>50篇后启用语义检索）
PINECONE_API_KEY=your_key
PINECONE_ENV=us-east-1
PINECONE_INDEX_NAME=junyi-articles
VECTOR_DB_ARTICLE_THRESHOLD=50

# 科大讯飞 语音识别
XFYUN_APP_ID=your_app_id
XFYUN_API_KEY=your_api_key
XFYUN_API_SECRET=your_api_secret

# MySQL
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=junyi_word
```

## 数据库表

| 表名 | 说明 |
|---|---|
| `daily_characters` | 每日生字记录（三层字库: tier 1/2/3，支持语文/数学分类） |
| `daily_articles` | AI 生成的文章（支持封面图+内嵌图） |
| `forgotten_characters` | 遗忘字跟踪（活跃→三次→五次以上） |
| `learning_records` | 学习行为流水（复习/跟读/背诵/写字/认读） |
| `user_word_mastery` | 生字掌握度（掌握度/稳定性/Skill等级/复习排期） |
| `curiosity_events` | 孩子提问记录 |
| `interest_evolution` | 兴趣标签演变（上升/稳定/下降趋势） |
| `knowledge_nodes` | 知识图谱节点 |
| `knowledge_links` | 知识图谱关系（相似/因果/包含/反义/故事关联） |
| `voice_profiles` | 声音样版（老师/家长真人录音） |
| `students` | 多孩子管理（独立数据隔离） |
| `reading_behaviors` | Agent 隐式阅读行为采集（点字频率） |
| `knowledge_entries` | 知识库条目（校内教材+校外科普，系统共享 student_id=0） |
| `student_textbook_configs` | 学生教材配置（版本+年级+学期） |
| `article_read_status` | 文章阅读状态追踪（未读/阅读中/已读完） |

## 教育参数配置

所有教育参数集中在 `backend/app/config.py` 的 `EducationConfig` 中管理：

- **复习间隔**: [1, 3, 7, 14, 30, 60] 天（6级渐增）
- **掌握度阈值**: 0.8 判定为已掌握
- **Session 权重**: review(0.4) / follow_read(0.3) / recite(0.2) / recognition(0.1)
- **每日限额**: 复习 10 字 / 新字 3 字
- **Skill 等级**: 1-10 级，每级对应不同生字密度（L1=5字/100字 → L10=35字/100字）

## 项目结构

```
junyiwold/
├── backend/
│   ├── app/
│   │   ├── agent/                     # AI Agent 模块 ★
│   │   │   ├── __init__.py            # 模块入口
│   │   │   ├── perceive.py            # 感知层：点字采集、语音输入
│   │   │   ├── reason.py              # 决策层：难度自适应、字库晋升
│   │   │   ├── act.py                 # 执行层：DeepSeek/讯飞/CogView/edge-tts
│   │   │   ├── remember.py            # 记忆层：字库/行为/文章 CRUD
│   │   │   └── loop.py               # AgentLoop 主循环
│   │   ├── routers/                  # API 路由 (12个模块)
│   │   │   ├── dashboard.py          # 仪表盘 + 统计导出
│   │   │   ├── articles.py           # 文章生成/查询/拼音标注 + 好奇心自动关联
│   │   │   ├── characters.py         # 生字增删改查 + 三层字库标记
│   │   │   ├── recent_chars.py       # 近期生字查询（字库级别 + 天数）
│   │   │   ├── review.py             # 遗忘字标记/复习管理
│   │   │   ├── curiosity.py          # 好奇心事件/兴趣演变/一键生成回答/话题建议
│   │   │   ├── knowledge.py          # 知识图谱节点/关系
│   │   │   ├── memory.py             # 记忆上下文（AI 生成辅助）
│   │   │   ├── students.py           # 学生管理 + 专属头像生成
│   │   │   └── voice.py              # 声音样版（录音上传/管理）
│   │   ├── services/                 # 业务逻辑 (10个服务)
│   │   │   ├── article_generator.py  # DeepSeek 文章生成 + GLM/SD 配图
│   │   │   ├── face_image_generator.py # ★ 人脸一致性图片生成（SD + IP-Adapter FaceID）
│   │   │   ├── pinyin_service.py     # pypinyin 精准拼音注音
│   │   │   ├── review_service.py     # 遗忘字统计/复习逻辑
│   │   │   ├── learning_record_service.py # 学习行为记录/统计
│   │   │   ├── mastery_service.py    # 掌握度计算/Skill 晋级
│   │   │   ├── review_scheduler.py   # 基于遗忘曲线排期复习
│   │   │   ├── curiosity_service.py  # 好奇心/兴趣追踪/一键回答生成
│   │   │   ├── knowledge_service.py  # 知识图谱构建
│   │   │   └── memory_service.py     # 记忆上下文引擎
│   │   └── memory/                   # 向量检索引擎
│   │       └── retrieval_engine.py   # Pinecone + sentence-transformers 语义检索
│   │   ├── models.py                 # 10 张表 SQLAlchemy 模型
│   │   ├── schemas.py                # Pydantic 请求/响应模型
│   │   ├── config.py                 # 环境变量 + EducationConfig
│   │   └── database.py               # 数据库连接
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   └── src/
│       ├── pages/                    # 9 个页面
│       │   ├── HomePage.tsx          # 首页仪表盘
│       │   ├── WordsPage.tsx         # 生字本
│       │   ├── AddWordsPage.tsx      # 录入生字（语音+粘贴+手动）
│       │   ├── ReviewPage.tsx        # 复习页
│       │   ├── ArticleHistoryPage.tsx # 历史文章
│       │   ├── CuriosityPage.tsx     # 好奇心追踪
│       │   ├── KnowledgePage.tsx     # 知识图谱
│       │   ├── StatsPage.tsx         # 学习统计
│       │   └── VoiceManagePage.tsx   # 声音样版（录音/上传/管理）
│       ├── components/               # 组件
│       │   ├── ArticleReader.tsx     # ★ 沉浸式课本阅读器（入场动画/音效/光晕/进度/庆祝/朗读）
│       │   └── AppLayout.tsx         # 布局（学生切换/头像生成/好奇心徽标）
│       ├── services/api.ts           # API 层
│       ├── store/useStore.ts         # Zustand 状态管理
│       └── styles/global.less        # 全局样式
├── sql/
│   ├── init.sql                      # 数据库初始化脚本
│   ├── migration_001~008              # 历次迁移
│   └── migration_009_knowledge_base.sql # 知识库系统建表
├── seed_data/textbooks/              # ★ 预置教材数据
│   └── 人教版/grade_1_second/        # 一年级下册语文+数学
├── scripts/                          # ★ 工具脚本
│   ├── guard-master.sh               # 分支安全守卫
│   └── rescue-from-master.sh         # 一键救援脚本
├── backend/scripts/
│   └── import_textbooks.py           # 教材数据导入脚本
└── docs/
    └── 使用指南.md                     # 详细使用文档
```

## 相关文档

- [使用指南](docs/使用指南.md) — 安装教程、功能详解、常见问题
- [API 路由参考](backend/app/routers/) — 15 个路由模块共 100+ 接口
- [数据库设计](sql/init.sql) — 18 张表完整建表语句

## 未来规划：成长度驱动的惊喜视频

> 以下为设计讨论阶段，暂不落地实现。等技术成本下降后启动。

### 核心理念

系统在孩子不知道的时候，就已经把礼物准备好了。他打开系统，看到新视频，觉得"哇，今天又有惊喜"——不知道这是算法在庆祝他的成长。

**奖励机制**：万相图生视频，生成俊宜自己的冒险故事。

**核心逻辑**：阅读积累 → 数据筛选 → 主题聚合 → 视频生成。他读得多、读得好，视频就精彩丰富；他读得少、随便应付，视频就平淡。他是自己视频的"编剧"。

### 成长度多维度评分

系统每日凌晨批处理，计算每个孩子的成长度分数，比对预设里程碑阈值：

```
成长度 = w1×阅读分 + w2×识字分 + w3×好奇心分 + w4×行为分

阅读分   = 0.3×ln(累计读完数) + 0.2×连续阅读天数 + 0.2×总阅读时长 + 0.3×本周阅读量
识字分   = 0.4×四区总字数 + 0.3×本周新字速度 + 0.3×(1 - 战损率)
好奇心分 = 0.3×累计提问数 + 0.3×本周提问频率 + 0.4×话题多样性
行为分   = 0.4×(1 - 点字率) + 0.3×每篇停留稳定性 + 0.3×朗读模式使用率
```

| 维度 | 数据来源 | 含义 |
|------|---------|------|
| 阅读量 | `article_read_status`、reading sessions | 累计读完文章数、连续阅读天数、总阅读时长 |
| 识字量 | 四区字库、`learning_records` | 各区字量、本周新字掌握速度、战损率 |
| 好奇心 | `curiosity_events` | 提问数量、频率、话题多样性（tag 熵值） |
| 行为 | `reading_behaviors`、点字/朗读动作 | 依赖点击的减少、阅读节奏的稳定性、是否开声音 |

### 里程碑示例

| 里程碑 | 条件 | 奖励 |
|--------|------|------|
| 阅读新星 | 累计读完 10 篇 | 音频贺卡 |
| 识字达人 | 四区总字数 ≥ 200 | 静态插图+故事 |
| 好奇宝宝 | 提问 ≥ 20 个 | 知识卡片合集 |
| 阅读先锋 | 连续 7 天阅读 | 勋章+音效 |
| 成长飞跃 | 成长度综合 ≥ 80 | **万相图生视频** |

### 视频生成技术链路

```
已生成文章、插图(PV/插图集合)  ——┐
角色设定图片（确保主角一致性）   ——┼──► 万相图生视频 API
故事脚本（由里程碑主题聚合）     ——┘
```

输入 → 万相 → 输出：
- 1-3 张场景图/插图（从已生成文章中筛选高质量配图）
- 1 张角色设定图（固定 prompt，确保俊宜形象一致）
- 故事脚本（DeepSeek 基于本周/本月阅读主题聚合生成）
- → 万相 API 生成 10-15 秒短视频

### 关键约束

1. **成本控制** — 不在常规课程中使用，仅作为惊喜里程碑奖励；按月配额（如每月最多 2 次）
2. **角色一致性** — 需要一张固定的角色设定图作为万相输入，保证主人公长得一样
3. **耗时容忍** — 视频生成可能需要数十秒到数分钟，后台静默生成，完成后通知
4. **安全边界** — 所有 DeepSeek 生成的故事脚本需过 prompt filter

### 分阶段落地

| 阶段 | 内容 | 前置条件 |
|------|------|---------|
| Phase 1 | 成长度评分 + 文章/音频里程碑 | 新增 `growth_scores`、`milestone_defs`、`student_milestones` 表 |
| Phase 2 | 行为信号精细化 | 新增 `reading_sessions` 表，计算趋势指标 |
| Phase 3 | 万相视频自动生成 | 确认主角一致性、成本、耗时可行 |

## 开源许可
git checkout -b feature-xxx    # 开新分支
# 改代码...
start-dev.bat                  # 开发环境测试（dev 数据库，可随便折腾）
# 确认没问题...
git checkout master
git merge feature-dev         # 合并到主分支
# 重启生产后端                  # 上线
仅供个人学习使用。