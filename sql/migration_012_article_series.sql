-- Migration 012: 文章系列 + 章节追踪
CREATE TABLE IF NOT EXISTS article_series (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID',
    topic VARCHAR(200) NOT NULL COMMENT '系列主题',
    curiosity_event_id INT DEFAULT NULL COMMENT '关联的好奇心事件',
    total_chapters INT NOT NULL DEFAULT 3 COMMENT '计划总章数',
    current_chapter INT NOT NULL DEFAULT 0 COMMENT '已生成的章数',
    chapter_titles_json JSON COMMENT '章节标题列表',
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress' COMMENT 'in_progress / completed / abandoned',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_student (student_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文章系列';

-- 检查列是否存在
SET @col1 = (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'daily_articles' AND COLUMN_NAME = 'series_id');
SET @col2 = (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'daily_articles' AND COLUMN_NAME = 'chapter_number');

SET @sql1 = IF(@col1 = 0, 'ALTER TABLE daily_articles ADD COLUMN series_id INT DEFAULT NULL COMMENT ''所属系列ID''', 'SELECT ''series_id exists''');
SET @sql2 = IF(@col2 = 0, 'ALTER TABLE daily_articles ADD COLUMN chapter_number INT DEFAULT NULL COMMENT ''章序号''', 'SELECT ''chapter_number exists''');
SET @sql3 = IF(@col1 = 0, 'ALTER TABLE daily_articles ADD INDEX idx_series (series_id)', 'SELECT ''idx_series exists''');

PREPARE stmt1 FROM @sql1; EXECUTE stmt1; DEALLOCATE PREPARE stmt1;
PREPARE stmt2 FROM @sql2; EXECUTE stmt2; DEALLOCATE PREPARE stmt2;
PREPARE stmt3 FROM @sql3; EXECUTE stmt3; DEALLOCATE PREPARE stmt3;
