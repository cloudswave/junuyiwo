import os
from pathlib import Path
from dotenv import load_dotenv

# 从项目根目录加载 .env（不管从哪里启动后端）
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
DB_NAME = os.getenv("DB_NAME", "junyi_word")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# GLM-Image (CogView) for article cover image generation
GLM_API_KEY = os.getenv("GLM_API_KEY", "")
GLM_IMAGE_MODEL = os.getenv("GLM_IMAGE_MODEL", "cogview-3")

# Pinecone vector database — 当文章积累到一定量后启用语义检索
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east-1")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "junyi-articles")
VECTOR_DB_ARTICLE_THRESHOLD = int(os.getenv("VECTOR_DB_ARTICLE_THRESHOLD", "50"))  # 文章数超过此值启用向量检索

# 孩子外貌描述（用于图片生成 prompt，根据参考照片填写）
CHILD_APPEARANCE = os.getenv("CHILD_APPEARANCE", "")

# 科大讯飞 语音识别
XFYUN_APP_ID = os.getenv("XFYUN_APP_ID", "")
XFYUN_API_KEY = os.getenv("XFYUN_API_KEY", "")
XFYUN_API_SECRET = os.getenv("XFYUN_API_SECRET", "")

# Pydantic Settings compatible (for asr_service.py)
class Settings:
    XFYUN_APP_ID = XFYUN_APP_ID
    XFYUN_API_KEY = XFYUN_API_KEY
    XFYUN_API_SECRET = XFYUN_API_SECRET


settings = Settings()


# ============ 教育相关配置 ============

class EducationConfig:
    """所有教育参数集中管理，方便调参"""

    # 遗忘曲线复习间隔（天）：第1次复习 → 第2次 → 第3次...
    REVIEW_INTERVALS = [1, 3, 7, 14, 30, 60]

    # 判定"已掌握"的掌握度阈值
    MASTERY_THRESHOLD = 0.8

    # 掌握度计算公式权重（各session_type的权重）
    MASTERY_WEIGHTS = {
        "review": 0.4,
        "follow_read": 0.3,
        "recite": 0.2,
        "recognition": 0.1,
    }

    # 刷题数量配置
    REVIEW_DAILY_LIMIT = 10       # 每天最多复习多少个字
    NEW_WORDS_DAILY_LIMIT = 3     # 每天最多学几个新字

    # Skill 等级与文章生字密度的映射（每100字插入几个生字）
    SKILL_LEVEL_DENSITY = {
        1: 5, 2: 8, 3: 12, 4: 15, 5: 18,
        6: 22, 7: 25, 8: 28, 9: 32, 10: 35,
    }

    # 好奇心追踪配置
    CURIOUSITY_WINDOW_DAYS = 30   # 分析兴趣时看最近多少天的数据
    INTEREST_TOP_N = 5            # 推荐取前几个兴趣标签

    # ============ 文章生字密度配置（家长模式可调）============
    # 根据已知字数量(友军区+侦查区)自动计算文章长度和生字密度
    # 格式: (已知字上限, 文章下限, 文章上限, 每100字生字数, 每100字战损复习数)
    ARTICLE_DENSITY_TIERS = [
        #  (已知≤,  文章min, 文章max, 生字/100字, 战损/100字)
        (30,     50,   100,   2,  0),   # 幼儿园: 一篇学1-2个字
        (80,     100,  200,   3,  1),   # 启蒙: 短句为主
        (200,    200,  350,   5,  1),   # 初学: 有基础词汇
        (500,    300,  500,   7,  2),   # 积累: 阅读能力形成
        (1000,   450,  700,   10, 2),   # 成长: 明显提升
        (2000,   600,  900,   12, 3),   # 进阶: 接近二年级
        (99999,  800,  1200,  15, 3),   # 熟练: 自主阅读
    ]

    # 单篇文章生字上限（防止轰炸）
    MAX_TARGET_CHARS_PER_ARTICLE = 35
    # 单篇文章战损复习上限
    MAX_REINFORCE_CHARS_PER_ARTICLE = 10

    # 家长自定义覆盖（默认 None，表示使用分级表自动计算）
    # 设置后忽略分级表，直接使用自定义值
    PARENT_OVERRIDE_MIN_CHARS: int | None = None     # 文章最小字数
    PARENT_OVERRIDE_MAX_CHARS: int | None = None     # 文章最大字数
    PARENT_OVERRIDE_DENSITY: int | None = None       # 每100字生字数
    PARENT_OVERRIDE_REINFORCE: int | None = None     # 每100字战损复习数

    # ============ 阅读等级系统（自动晋升）============
    # 7 级，每级对应: {name, icon, known_threshold, articles_threshold}
    READING_LEVELS = [
        # Lv, 名称, 图标, 晋级需已知字, 晋级需读完文章
        (1, "识字萌芽", "🌱", 0, 0),
        (2, "初识汉字", "🌿", 30, 5),
        (3, "词汇小匠", "🪴", 80, 15),
        (4, "阅读新星", "🌳", 200, 30),
        (5, "独立读者", "⭐", 500, 60),
        (6, "博览少年", "🌟", 1000, 120),
        (7, "阅读达人", "👑", 2000, 200),
    ]

    # 晋级条件：需同时满足 known >= threshold AND articles >= threshold
    # 每读一篇文章且标记为"已读"后自动检查

    # 晋升冷却天数（防止频繁升级）
    LEVEL_UP_COOLDOWN_DAYS = 3

    # ============ 认知水平配置 ============
    COGNITION_MAX_LEVEL = 3

    # 认知等级对应的回答 prompt 引导词
    COGNITION_PROMPTS = {
        1: "用最浅显的比喻来解释，每句话不超过15个字，不要使用专业术语。像跟幼儿园小朋友说话一样。",
        2: "可以使用'核聚变''引力''能量'等基础科学术语，但要给出简单的生活类比，帮助孩子理解。",
        3: "可以深入解释原理，使用'核聚变''引力坍缩''事件视界'等准确术语。保持逻辑清晰，用图景描述，像科学家跟小助手聊天一样认真对待。",
    }

    # 高级词汇检测 — 问题中包含这些词，临时提升 1 级认知
    ADVANCED_KEYWORDS = [
        "裂变", "引力", "能量守恒", "黑洞", "相对论", "量子", "奇点",
        "核聚变", "坍缩", "暗物质", "暗能量", "光年", "太阳系", "银河系",
        "细胞", "基因", "进化", "大气层", "地壳", "火山", "地震",
        "化学反应", "分子", "原子", "电流", "磁场", "重力",
    ]

    # 升级/降级阈值
    COGNITION_UPGRADE_TOO_EASY_COUNT = 3   # 连续3次"太简单"→升1级
    COGNITION_DOWNGRADE_TOO_HARD_COUNT = 3  # 连续3次"太难"→降1级


EDUCATION_CONFIG = EducationConfig()
