from datetime import date, datetime
from sqlalchemy import String, Integer, Date, Text, DateTime, func, Boolean, JSON, Enum, ForeignKey, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="孩子昵称")
    avatar: Mapped[str] = mapped_column(String(200), default="", comment="头像emoji")
    reading_level: Mapped[int] = mapped_column(Integer, default=1, comment="阅读等级 1-7")
    cognition_level: Mapped[int] = mapped_column(Integer, default=1, comment="认知水平 1-3: 1=浅显比喻/2=基础术语+解释/3=深入原理")
    leveled_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近升级时间")
    total_articles_read: Mapped[int] = mapped_column(Integer, default=0, comment="累计读完文章数")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DailyCharacter(Base):
    __tablename__ = "daily_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="最近学习/确认日期")
    character: Mapped[str] = mapped_column(String(10), nullable=False, comment="生字")
    pinyin: Mapped[str] = mapped_column(String(50), nullable=True, comment="拼音")
    category: Mapped[str] = mapped_column(String(20), default="chinese", comment="分类: chinese/math")
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    tier: Mapped[int] = mapped_column(Integer, default=1, comment="字库层级: 1=新鲜字库,2=熟悉字库,3=老朋友字库")
    confirm_count: Mapped[int] = mapped_column(Integer, default=0, comment="当前层级的确认次数，满3次晋升")
    last_confirm_article_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="最近确认的文章ID，用于跨文章去重")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DailyArticle(Base):
    __tablename__ = "daily_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="日期")
    topic: Mapped[str] = mapped_column(String(100), nullable=False, comment="主题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="文章内容")
    character_count: Mapped[int] = mapped_column(Integer, nullable=False, comment="文章字数")
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    source: Mapped[str] = mapped_column(String(20), default="ai", comment="来源: manual/ai")
    category: Mapped[str] = mapped_column(String(20), default="story", comment="生成模式: story=故事式 / answer=百科回答式")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="封面图片URL")
    images_json: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True, comment="内嵌图片列表[{url,after_para}]")  # type: ignore[assignment]
    series_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, comment="所属系列ID")
    chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="章序号 1/2/3...")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ForgottenCharacter(Base):
    __tablename__ = "forgotten_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    character: Mapped[str] = mapped_column("hanzi", String(10), nullable=False, index=True, comment="遗忘字")
    pinyin: Mapped[str] = mapped_column(String(50), nullable=True, comment="拼音")
    forget_count: Mapped[int] = mapped_column(Integer, default=0, comment="遗忘次数")
    first_forgotten_date: Mapped[date] = mapped_column(Date, nullable=True, comment="首次遗忘日期")
    last_forgotten_date: Mapped[date] = mapped_column(Date, nullable=True, comment="最近遗忘日期")
    level: Mapped[str] = mapped_column(String(20), default="active", comment="遗忘等级: active/3次/5次+/learned")
    category: Mapped[str] = mapped_column(String(20), default="chinese", comment="分类: chinese/math")
    learned_days_ago: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="首次遗忘时的学习距今天数: 0=当天,1-7=一周内,8+=历史,null=未学过")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CuriosityEvent(Base):
    __tablename__ = "curiosity_events"

    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, comment="提问日期")
    raw_text: Mapped[str] = mapped_column(String(500), nullable=False, comment="孩子原话")
    cleaned_text: Mapped[str] = mapped_column(String(500), nullable=True, comment="清洗后文本")
    keywords_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="关键词列表")
    tags_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="兴趣标签")
    is_answered: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已生成文章回应")
    linked_article_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="回应的文章ID")
    parent_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="关联的上一次话题（追问）")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class InterestEvolution(Base):
    __tablename__ = "interest_evolution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="兴趣标签")
    first_mentioned_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="首次提及日期")
    last_mentioned_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="最近提及日期")
    mention_count: Mapped[int] = mapped_column(Integer, default=1, comment="提及次数")
    intensity_score: Mapped[float | None] = mapped_column(DECIMAL(3, 2), nullable=True, comment="兴趣强度")
    trend: Mapped[str | None] = mapped_column(Enum("rising", "stable", "declining", name="trend_enum"), nullable=True, comment="兴趣趋势")


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="知识点名称")
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="分类")
    first_appearance_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="首次出现日期")
    last_review_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="最近复习日期")
    total_articles: Mapped[int] = mapped_column(Integer, default=0, comment="涉及该知识点的文章数")


class KnowledgeLink(Base):
    __tablename__ = "knowledge_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_a_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_nodes.id"), nullable=False, comment="节点A")
    node_b_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_nodes.id"), nullable=False, comment="节点B")
    link_type: Mapped[str] = mapped_column(
        Enum("similar", "cause_effect", "part_of", "opposite", "story_connection", name="link_type_enum"),
        nullable=False, comment="关联类型"
    )
    strength: Mapped[int] = mapped_column(Integer, default=1, comment="关联强度")
    discovered_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="发现日期")


class LearningRecord(Base):
    """学习记录 - 所有学习行为的统一流水表"""
    __tablename__ = "learning_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, default="default", index=True, comment="孩子ID，支持多娃")
    character: Mapped[str] = mapped_column(String(10), nullable=False, index=True, comment="哪个字")

    session_type: Mapped[str] = mapped_column(
        Enum("review", "recite", "follow_read", "writing", "recognition", name="session_type_enum"),
        nullable=False,
        comment="学习类型: review复习/recite背诵/follow_read跟读/writing写字/recognition认读"
    )

    score: Mapped[float] = mapped_column(DECIMAL(3, 2), nullable=False, default=0.0, comment="得分 0-1")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否正确")

    context: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="上下文: {article_id, audio_url, expected_pinyin, actual_pinyin, attempts}")
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="耗时(秒)")
    review_schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="关联的复习计划ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="发生时间")


class VoiceProfile(Base):
    """声音克隆样版 — 上传一段样本音频，未来通过语音克隆生成该音色朗读"""
    __tablename__ = "voice_profiles"

    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="样版名称，如'李老师'")
    prompt_text: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="参考文本，用于声音克隆")
    sample_path: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="声音克隆样本音频路径")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserWordMastery(Base):
    """用户-生字掌握度表 - 所有个性化学习的核心"""
    __tablename__ = "user_word_mastery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, default="default", index=True, comment="孩子ID")
    character: Mapped[str] = mapped_column(String(10), nullable=False, index=True, comment="生字")

    mastery_level: Mapped[float] = mapped_column(DECIMAL(3, 2), default=0.0, comment="综合掌握度 0-1")
    stability: Mapped[float] = mapped_column(DECIMAL(3, 2), default=0.0, comment="记忆稳定性 (遗忘曲线用)")

    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="下次应复习日期")
    review_interval_days: Mapped[int] = mapped_column(Integer, default=1, comment="当前复习间隔(天)")
    review_count: Mapped[int] = mapped_column(Integer, default=0, comment="已复习次数")

    total_attempts: Mapped[int] = mapped_column(Integer, default=0, comment="总学习次数")
    correct_count: Mapped[int] = mapped_column(Integer, default=0, comment="正确次数")
    streak_correct: Mapped[int] = mapped_column(Integer, default=0, comment="连续正确次数")
    last_studied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="上次学习时间")

    skill_level: Mapped[int] = mapped_column(Integer, default=1, comment="当前所属能力等级 1-10")
    last_updated: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReadingBehavior(Base):
    """隐式阅读行为采集 — 零操作自动采集，驱动生成参数自适应"""
    __tablename__ = "reading_behaviors"

    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(Integer, index=True, comment="文章ID")
    character: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True, comment="点击的汉字（char_tap）/ 阅读的句子片段")
    action_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="行为类型: char_tap 点字发声")
    position: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="文章中的字符位置")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ===== 四区字库系统 =====

class TargetCharacter(Base):
    """教学区 — 系统唯一主动教的字，仅家长/老师录入"""
    __tablename__ = "target_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    character: Mapped[str] = mapped_column(String(10), nullable=False)
    pinyin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual", comment="manual/sync")
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ScoutCharacter(Base):
    """侦查区 — 见过但不确定会不会的字，阅读中首次遇到自动进入"""
    __tablename__ = "scout_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    character: Mapped[str] = mapped_column(String(10), nullable=False)
    pinyin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="reading", comment="reading/textbook/lost_recovery")
    first_seen_article_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    appeared_in_read_count: Mapped[int] = mapped_column(Integer, default=0, comment="出现在已读完文章的次数")
    never_tapped_in_read_count: Mapped[int] = mapped_column(Integer, default=0, comment="在已读完文章中从未被点击的次数")
    last_seen_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    promoted_to_ally_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllyCharacter(Base):
    """友军区 — 真正掌握的字，不会遗忘"""
    __tablename__ = "ally_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    character: Mapped[str] = mapped_column(String(10), nullable=False)
    pinyin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="auto_promoted", comment="auto_promoted/manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LostCharacter(Base):
    """战损区 — 在已读完文章中被点击过的字，待复习"""
    __tablename__ = "lost_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    character: Mapped[str] = mapped_column(String(10), nullable=False)
    pinyin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tap_count: Mapped[int] = mapped_column(Integer, default=0, comment="在已读完文章中的总点击次数")
    article_count: Mapped[int] = mapped_column(Integer, default=0, comment="涉及多少篇已读完文章")
    first_lost_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_lost_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", comment="active/reviewing/recovered")
    recovered_to_scout_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ArticleReadStatus(Base):
    """文章阅读状态 — 追踪每篇文章每个孩子的阅读进度"""
    __tablename__ = "article_read_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    article_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="文章ID")
    status: Mapped[str] = mapped_column(Enum("unread", "reading", "read", name="read_status_enum"), default="unread")
    read_paragraph_count: Mapped[int] = mapped_column(Integer, default=0)
    total_paragraph_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ===== 知识库系统 =====

class StudentTextbookConfig(Base):
    """学生教材配置 — 记录家长选择的教材版本和年级"""
    __tablename__ = "student_textbook_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    textbook_version: Mapped[str] = mapped_column(String(50), default="人教版", comment="教材版本: 人教版/苏教版/部编版")
    current_grade: Mapped[str] = mapped_column(String(30), default="grade_1", comment="当前年级: grade_1/grade_2/...")
    current_semester: Mapped[str] = mapped_column(String(20), default="second", comment="当前学期: first/second")
    setup_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeEntry(Base):
    """知识库条目 — 校内课本知识 + 校外科普知识"""
    __tablename__ = "knowledge_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=0, index=True, comment="0=系统共享(教材), >0=家庭专属")
    category: Mapped[str] = mapped_column(String(30), default="school", comment="分类: school/extracurricular")
    subject: Mapped[str] = mapped_column(String(50), default="", comment="学科/领域: 语文/数学/天文/地理/动植物...")
    grade_level: Mapped[str] = mapped_column(String(30), default="", comment="年级学期: grade_1_first/grade_1_second/...")
    textbook_version: Mapped[str] = mapped_column(String(50), default="", comment="教材版本: 人教版/苏教版/部编版")
    lesson: Mapped[str] = mapped_column(String(100), default="", comment="课文名称")
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="知识条目标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="知识内容")
    keywords_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="检索关键词列表")
    source: Mapped[str] = mapped_column(String(30), default="manual", comment="来源: textbook_preload/auto_generated/article_backfeed/manual")
    auto_approved: Mapped[bool] = mapped_column(Boolean, default=True, comment="自动生成的内容是否直接可用")
    used_count: Mapped[int] = mapped_column(Integer, default=0, comment="被文章引用的次数")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ArticleSeries(Base):
    """文章系列 — 将一个大主题拆解为多章连载"""
    __tablename__ = "article_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    topic: Mapped[str] = mapped_column(String(200), nullable=False, comment="系列主题")
    curiosity_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="关联的好奇心事件")
    total_chapters: Mapped[int] = mapped_column(Integer, default=3, comment="计划总章数")
    current_chapter: Mapped[int] = mapped_column(Integer, default=0, comment="已生成的章数")
    chapter_titles_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="章节标题列表 [{ch, title, summary}]")
    status: Mapped[str] = mapped_column(String(20), default="in_progress", comment="in_progress / completed / abandoned")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class DifficultyFeedback(Base):
    """文章难度反馈 — 孩子觉得太简单或太难，用于校准认知等级"""
    __tablename__ = "difficulty_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    article_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="文章ID")
    feedback: Mapped[str] = mapped_column(String(20), nullable=False, comment="反馈类型: too_easy / too_hard")
    topic: Mapped[str] = mapped_column(String(100), default="", comment="文章主题（冗余存储，方便分析）")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ===== 好奇心对话系统 =====

class ConversationSession(Base):
    """对话会话 — 基于好奇心事件的深入对话"""
    __tablename__ = "conversation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="所属学生ID")
    curiosity_event_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="关联的好奇心事件")
    status: Mapped[str] = mapped_column(String(20), default="active", comment="active / completed")
    turn_count: Mapped[int] = mapped_column(Integer, default=0, comment="对话轮次")
    final_article_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="最终生成的文章ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ConversationTurn(Base):
    """对话轮次"""
    __tablename__ = "conversation_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversation_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="user / assistant")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
