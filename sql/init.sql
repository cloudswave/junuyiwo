-- 俊宜识字系统 - 数据库初始化脚本
-- 适用: MySQL 8.2+
-- 执行: mysql -u root -p < init.sql

CREATE DATABASE IF NOT EXISTS junyi_word
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE junyi_word;

-- 1. 每日生字记录（三层字库系统）
CREATE TABLE IF NOT EXISTS daily_characters (
    id                       INT AUTO_INCREMENT PRIMARY KEY,
    record_date              DATE        NOT NULL COMMENT '最近学习/确认日期',
    character                VARCHAR(10) NOT NULL COMMENT '生字',
    pinyin                   VARCHAR(50) NULL     COMMENT '拼音',
    category                 VARCHAR(20) NOT NULL DEFAULT 'chinese' COMMENT '分类: chinese/math',
    tier                     INT         NOT NULL DEFAULT 1 COMMENT '字库层级: 1=新字库,2=工作库,3=永久库',
    confirm_count            INT         NOT NULL DEFAULT 0 COMMENT '当前层级的确认次数，满3次晋升',
    last_confirm_article_id  INT         NULL     COMMENT '最近确认的文章ID，用于跨文章去重',
    created_at               DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_record_date (record_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 每日文章
CREATE TABLE IF NOT EXISTS daily_articles (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    record_date     DATE         NOT NULL COMMENT '日期',
    topic           VARCHAR(100) NOT NULL COMMENT '主题',
    content         TEXT         NOT NULL COMMENT '文章内容',
    character_count INT          NOT NULL COMMENT '文章字数',
    source          VARCHAR(20)  NOT NULL DEFAULT 'ai' COMMENT '来源: manual / ai',
    category        VARCHAR(20)  NOT NULL DEFAULT 'story' COMMENT '生成模式: story=故事式 / answer=百科回答式',
    image_url       VARCHAR(500) NULL     COMMENT '封面图片URL',
    images_json     JSON         NULL     COMMENT '内嵌图片列表 [{url, after_para}]',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_record_date (record_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. 遗忘字跟踪
CREATE TABLE IF NOT EXISTS forgotten_characters (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    hanzi                VARCHAR(10) NOT NULL COMMENT '遗忘字',
    pinyin               VARCHAR(50) NULL     COMMENT '拼音',
    forget_count         INT         NOT NULL DEFAULT 0 COMMENT '遗忘次数',
    first_forgotten_date DATE        NULL     COMMENT '首次遗忘日期',
    last_forgotten_date  DATE        NULL     COMMENT '最近遗忘日期',
    level                VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '遗忘等级: active / 3次 / 5次+ / learned',
    category             VARCHAR(20) NOT NULL DEFAULT 'chinese' COMMENT '分类: chinese/math',
    learned_days_ago     INT         NULL     COMMENT '首次遗忘时的学习距今天数: 0=当天,1-7=一周内,8+=历史,null=未学过',
    created_at           DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX ix_hanzi (hanzi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. 好奇心事件（提问记录）
CREATE TABLE IF NOT EXISTS curiosity_events (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    event_date        DATE         NOT NULL COMMENT '提问日期',
    raw_text          VARCHAR(500) NOT NULL COMMENT '孩子原话',
    cleaned_text      VARCHAR(500) NULL     COMMENT '清洗后文本',
    keywords_json     JSON         NULL     COMMENT '关键词列表',
    tags_json         JSON         NULL     COMMENT '兴趣标签',
    is_answered       TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否已生成文章回应',
    linked_article_id INT          NULL     COMMENT '回应的文章ID',
    parent_event_id   INT          NULL     COMMENT '关联的上一次话题（追问）',
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. 兴趣演变追踪
CREATE TABLE IF NOT EXISTS interest_evolution (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    tag_name              VARCHAR(50) NOT NULL COMMENT '兴趣标签',
    first_mentioned_date  DATE        NULL     COMMENT '首次提及日期',
    last_mentioned_date   DATE        NULL     COMMENT '最近提及日期',
    mention_count         INT         NOT NULL DEFAULT 1 COMMENT '提及次数',
    intensity_score       DECIMAL(3,2) NULL    COMMENT '兴趣强度 (0.00-1.00)',
    trend                 ENUM('rising','stable','declining') NULL COMMENT '兴趣趋势'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. 知识图谱节点
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    node_name             VARCHAR(100) NOT NULL COMMENT '知识点名称',
    category              VARCHAR(50)  NULL     COMMENT '分类',
    first_appearance_date DATE         NULL     COMMENT '首次出现日期',
    last_review_date      DATE         NULL     COMMENT '最近复习日期',
    total_articles        INT          NOT NULL DEFAULT 0 COMMENT '涉及该知识点的文章数'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. 知识图谱关系
CREATE TABLE IF NOT EXISTS knowledge_links (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    node_a_id       INT  NOT NULL COMMENT '节点A',
    node_b_id       INT  NOT NULL COMMENT '节点B',
    link_type       ENUM('similar','cause_effect','part_of','opposite','story_connection') NOT NULL COMMENT '关联类型',
    strength        INT  NOT NULL DEFAULT 1 COMMENT '关联强度',
    discovered_date DATE NULL     COMMENT '发现日期',
    FOREIGN KEY (node_a_id) REFERENCES knowledge_nodes(id),
    FOREIGN KEY (node_b_id) REFERENCES knowledge_nodes(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. 学习行为流水记录
CREATE TABLE IF NOT EXISTS learning_records (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    user_id            VARCHAR(50)  NOT NULL DEFAULT 'default' COMMENT '孩子ID',
    `character`        VARCHAR(10)  NOT NULL COMMENT '哪个字',
    session_type       ENUM('review','recite','follow_read','writing','recognition') NOT NULL COMMENT '学习类型',
    score              DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT '得分 0-1',
    is_correct         TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否正确',
    context            JSON         NULL     COMMENT '上下文',
    duration_seconds   INT          NULL     COMMENT '耗时(秒)',
    review_schedule_id INT          NULL     COMMENT '关联复习计划ID',
    created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发生时间',
    INDEX ix_lr_user_id (user_id),
    INDEX ix_lr_character (`character`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. 用户生字掌握度
CREATE TABLE IF NOT EXISTS user_word_mastery (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    user_id              VARCHAR(50)  NOT NULL DEFAULT 'default' COMMENT '孩子ID',
    `character`          VARCHAR(10)  NOT NULL COMMENT '生字',
    mastery_level        DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT '综合掌握度 0-1',
    stability            DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT '记忆稳定性',
    next_review_date     DATE         NULL     COMMENT '下次应复习日期',
    review_interval_days INT          NOT NULL DEFAULT 1 COMMENT '当前复习间隔(天)',
    review_count         INT          NOT NULL DEFAULT 0 COMMENT '已复习次数',
    total_attempts       INT          NOT NULL DEFAULT 0 COMMENT '总学习次数',
    correct_count        INT          NOT NULL DEFAULT 0 COMMENT '正确次数',
    streak_correct       INT          NOT NULL DEFAULT 0 COMMENT '连续正确次数',
    last_studied_at      DATETIME     NULL     COMMENT '上次学习时间',
    skill_level          INT          NOT NULL DEFAULT 1 COMMENT '当前所属能力等级 1-10',
    last_updated         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_uwm_user_id (user_id),
    INDEX ix_uwm_character (`character`),
    UNIQUE INDEX ix_user_char (user_id, `character`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. 声音克隆样版
CREATE TABLE IF NOT EXISTS voice_profiles (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL COMMENT '样版名称，如"李老师"',
    prompt_text VARCHAR(500) NULL     COMMENT '参考文本，用于声音克隆',
    sample_path VARCHAR(500) NULL     COMMENT '声音克隆样本音频路径',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
