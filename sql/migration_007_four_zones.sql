-- 四区字库系统 — 建表 + 数据迁移
-- 适用: MySQL 8.2+
-- 执行: mysql -u root -p junyi_word < migration_007_four_zones.sql

USE junyi_word;

-- ============================================================
-- 1. 教学区 (Target): 系统唯一主动教的字
-- ============================================================
CREATE TABLE IF NOT EXISTS target_characters (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    student_id  INT         NOT NULL DEFAULT 1,
    `character` VARCHAR(10) NOT NULL,
    pinyin      VARCHAR(50) NULL,
    source      VARCHAR(20) NOT NULL DEFAULT 'manual' COMMENT 'manual/sync',
    added_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX ix_tc_student_char (student_id, `character`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 2. 侦查区 (Scout): 见过但不确定会不会的字
-- ============================================================
CREATE TABLE IF NOT EXISTS scout_characters (
    id                        INT AUTO_INCREMENT PRIMARY KEY,
    student_id                INT         NOT NULL DEFAULT 1,
    `character`               VARCHAR(10) NOT NULL,
    pinyin                    VARCHAR(50) NULL,
    source                    VARCHAR(30) NOT NULL DEFAULT 'reading' COMMENT 'reading/textbook/lost_recovery',
    first_seen_article_id     INT         NULL,
    first_seen_date           DATE        NULL,
    appeared_in_read_count    INT         NOT NULL DEFAULT 0 COMMENT '出现在已读完文章的次数',
    never_tapped_in_read_count INT        NOT NULL DEFAULT 0 COMMENT '在已读完文章中从未被点击的次数',
    last_seen_date            DATE        NULL,
    promoted_to_ally_at       DATETIME    NULL     COMMENT '晋升到友军区的时间',
    created_at                DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX ix_sc_student_char (student_id, `character`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 3. 友军区 (Ally): 真正掌握，不会遗忘的字
-- ============================================================
CREATE TABLE IF NOT EXISTS ally_characters (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    student_id  INT         NOT NULL DEFAULT 1,
    `character` VARCHAR(10) NOT NULL,
    pinyin      VARCHAR(50) NULL,
    source      VARCHAR(30) NOT NULL DEFAULT 'auto_promoted' COMMENT 'auto_promoted/manual',
    created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX ix_ac_student_char (student_id, `character`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 4. 战损区 (Lost): 遇到困难，待复习
-- ============================================================
CREATE TABLE IF NOT EXISTS lost_characters (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    student_id           INT         NOT NULL DEFAULT 1,
    `character`          VARCHAR(10) NOT NULL,
    pinyin               VARCHAR(50) NULL,
    tap_count            INT         NOT NULL DEFAULT 0 COMMENT '在已读完文章中的总点击次数',
    article_count        INT         NOT NULL DEFAULT 0 COMMENT '涉及多少篇已读完文章',
    first_lost_date      DATE        NULL,
    last_lost_date       DATE        NULL,
    status               VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'active/reviewing/recovered',
    recovered_to_scout_at DATETIME   NULL     COMMENT '恢复回侦查区的时间',
    created_at           DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX ix_lc_student_char (student_id, `character`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 5. 文章阅读状态
-- ============================================================
CREATE TABLE IF NOT EXISTS article_read_status (
    id                     INT AUTO_INCREMENT PRIMARY KEY,
    student_id             INT          NOT NULL DEFAULT 1,
    article_id             INT          NOT NULL,
    status                 ENUM('unread','reading','read') NOT NULL DEFAULT 'unread',
    read_paragraph_count   INT          NOT NULL DEFAULT 0,
    total_paragraph_count  INT          NOT NULL DEFAULT 0,
    started_at             DATETIME     NULL,
    finished_at            DATETIME     NULL,
    UNIQUE INDEX ix_ars_student_article (student_id, article_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 数据迁移: daily_characters → 四区
--   tier 1 (新字库)   → target_characters (正在教)
--   tier 2 (熟悉字库) → scout_characters  (巩固中 → 放入侦查区验证)
--   tier 3 (老朋友库) → ally_characters   (已掌握)
-- ============================================================

-- tier 1 → 教学区 (取每个字最新的 record_date)
INSERT IGNORE INTO target_characters (student_id, `character`, pinyin, source, added_at)
SELECT student_id, `character`, MAX(pinyin), 'migration',
       (SELECT MAX(dc2.record_date) FROM daily_characters dc2
        WHERE dc2.`character` = dc.`character` AND dc2.student_id = dc.student_id)
FROM daily_characters dc
WHERE tier = 1
GROUP BY student_id, `character`;

-- tier 2 → 侦查区
INSERT IGNORE INTO scout_characters (student_id, `character`, pinyin, source)
SELECT student_id, `character`, MAX(pinyin), 'migration'
FROM daily_characters
WHERE tier = 2
GROUP BY student_id, `character`;

-- tier 3 → 友军区
INSERT IGNORE INTO ally_characters (student_id, `character`, pinyin, source)
SELECT student_id, `character`, MAX(pinyin), 'migration'
FROM daily_characters
WHERE tier = 3
GROUP BY student_id, `character`;

-- ============================================================
-- 数据迁移: forgotten_characters → lost_characters
-- ============================================================
INSERT IGNORE INTO lost_characters (student_id, `character`, pinyin, tap_count, article_count, first_lost_date, last_lost_date, status)
SELECT student_id, hanzi, pinyin, forget_count, 1, first_forgotten_date, last_forgotten_date,
       CASE `level`
           WHEN '活跃' THEN 'active'
           WHEN '三次' THEN 'reviewing'
           WHEN '五次以上' THEN 'reviewing'
           ELSE 'active'
       END
FROM forgotten_characters;
