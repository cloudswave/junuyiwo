-- Migration 010: 认知水平系统
-- 新增: students.cognition_level, difficulty_feedback

-- 先检查列是否存在，不存在则添加
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'students' AND COLUMN_NAME = 'cognition_level');

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE students ADD COLUMN cognition_level INT NOT NULL DEFAULT 1 COMMENT ''认知水平 1-3: 1=浅显比喻/2=基础术语+解释/3=深入原理''',
    'SELECT ''cognition_level already exists''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS difficulty_feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID',
    article_id INT NOT NULL COMMENT '文章ID',
    feedback VARCHAR(20) NOT NULL COMMENT 'too_easy / too_hard',
    topic VARCHAR(100) NOT NULL DEFAULT '' COMMENT '文章主题',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_student (student_id),
    INDEX idx_article (article_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文章难度反馈';
