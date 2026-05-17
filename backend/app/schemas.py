from datetime import date, datetime
from pydantic import BaseModel, Field


# ===== DailyCharacter =====
class CharacterCreate(BaseModel):
    record_date: date
    characters: list[str] = Field(..., min_length=1, description="生字列表")
    pinyin: list[str] = Field(default_factory=list, description="拼音列表")
    category: str = Field(default="chinese", pattern="^(chinese|math)$", description="分类: chinese/math")


class CharacterResponse(BaseModel):
    id: int
    record_date: date
    character: str
    pinyin: str | None
    category: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CharacterListResponse(BaseModel):
    date: date
    characters: list[CharacterResponse]


# ===== DailyArticle =====
class ArticleGenerate(BaseModel):
    record_date: date
    topic: str = Field(..., min_length=1, max_length=100, description="文章主题/孩子的问题")
    characters: list[str] = Field(..., description="要融入的生字列表")
    min_chars: int = Field(default=200, ge=20)
    max_chars: int = Field(default=800, le=5000)
    category: str = Field(default="story", pattern="^(story|answer)$", description="生成模式: story=故事式, answer=百科回答式")
    memory_context: str | None = Field(default=None, description="记忆上下文（为空时后端自动拉取）")
    curiosity_event_id: int | None = Field(default=None, description="关联的好奇心事件ID（生成后自动关联）")


class ArticleCreate(BaseModel):
    record_date: date
    topic: str
    content: str
    source: str = "manual"
    category: str = "story"


class ArticleResponse(BaseModel):
    id: int
    record_date: date
    topic: str
    content: str
    character_count: int
    source: str
    category: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== ForgottenCharacter =====
class ForgottenRecord(BaseModel):
    date: date
    characters: list[str] = Field(..., description="遗忘字列表")
    pinyin: list[str] = Field(default_factory=list)
    category: str = "chinese"
    learned_days_ago: list[int | None] = Field(default_factory=list, description="每字的学习距今天数: 0=当天,1-7=一周内,8+=历史,null=未学过")


class ForgottenResponse(BaseModel):
    id: int
    character: str
    pinyin: str | None
    forget_count: int
    first_forgotten_date: date | None
    last_forgotten_date: date | None
    level: str
    category: str
    learned_days_ago: int | None = None

    model_config = {"from_attributes": True}


class ForgottenListResponse(BaseModel):
    total: int
    items: list[ForgottenResponse]
    level_counts: dict[str, int]


# ===== CuriosityEvent =====
class CuriosityEventCreate(BaseModel):
    event_date: date
    raw_text: str = Field(..., min_length=1, max_length=500)
    cleaned_text: str | None = None
    keywords: list[str] | None = None
    tags: list[str] | None = None
    parent_event_id: int | None = None


class CuriosityEventUpdate(BaseModel):
    cleaned_text: str | None = None
    keywords: list[str] | None = None
    tags: list[str] | None = None
    is_answered: bool | None = None
    linked_article_id: int | None = None
    parent_event_id: int | None = None


class CuriosityEventResponse(BaseModel):
    id: int
    event_date: date
    raw_text: str
    cleaned_text: str | None
    keywords_json: list[str] | list | None
    tags_json: list[str] | list | None
    is_answered: bool
    linked_article_id: int | None
    parent_event_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CuriosityListResponse(BaseModel):
    total: int
    unanswered: int
    items: list[CuriosityEventResponse]
    tags_summary: dict[str, int]


# ===== InterestEvolution =====
class InterestEvolutionResponse(BaseModel):
    id: int
    tag_name: str
    first_mentioned_date: date | None
    last_mentioned_date: date | None
    mention_count: int
    intensity_score: float | None
    trend: str | None

    model_config = {"from_attributes": True}


# ===== KnowledgeNode =====
class KnowledgeNodeCreate(BaseModel):
    node_name: str = Field(..., min_length=1, max_length=100)
    category: str | None = None


class KnowledgeNodeResponse(BaseModel):
    id: int
    node_name: str
    category: str | None
    first_appearance_date: date | None
    last_review_date: date | None
    total_articles: int

    model_config = {"from_attributes": True}


class KnowledgeLinkResponse(BaseModel):
    id: int
    node_a_id: int
    node_b_id: int
    link_type: str
    strength: int
    discovered_date: date | None

    model_config = {"from_attributes": True}


class KnowledgeGraphResponse(BaseModel):
    nodes: list[KnowledgeNodeResponse]


# ===== KnowledgeEntry =====

class KnowledgeEntryResponse(BaseModel):
    id: int
    student_id: int
    category: str
    subject: str
    grade_level: str
    textbook_version: str
    lesson: str
    title: str
    content: str
    keywords_json: list[str] | None = None
    source: str
    auto_approved: bool
    used_count: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TextbookConfigResponse(BaseModel):
    configured: bool = False
    id: int | None = None
    textbook_version: str | None = None
    current_grade: str | None = None
    current_semester: str | None = None
    links: list[KnowledgeLinkResponse]


# ===== VoiceProfile =====
class VoiceProfileResponse(BaseModel):
    id: int
    name: str
    sample_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== Dashboard =====
class DashboardResponse(BaseModel):
    today: date
    today_characters: list[str]
    today_math_characters: list[str]
    today_article: ArticleResponse | None
    forgotten_stats: dict[str, int]
    total_characters_learned: int
    total_math_characters: int
    recent_questions: list[CuriosityEventResponse]
    hot_interests: list[InterestEvolutionResponse]
