-- Migration 009: 知识库系统
-- 新增: student_textbook_configs, knowledge_entries

CREATE TABLE IF NOT EXISTS student_textbook_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID',
    textbook_version VARCHAR(50) NOT NULL DEFAULT '人教版' COMMENT '教材版本',
    current_grade VARCHAR(30) NOT NULL DEFAULT 'grade_1' COMMENT '当前年级',
    current_semester VARCHAR(20) NOT NULL DEFAULT 'second' COMMENT '当前学期',
    setup_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_student (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学生教材配置';

CREATE TABLE IF NOT EXISTS knowledge_entries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL DEFAULT 0 COMMENT '0=系统共享(教材), >0=家庭专属',
    category VARCHAR(30) NOT NULL DEFAULT 'school' COMMENT 'school/extracurricular',
    subject VARCHAR(50) NOT NULL DEFAULT '' COMMENT '学科/领域',
    grade_level VARCHAR(30) NOT NULL DEFAULT '' COMMENT '年级学期',
    textbook_version VARCHAR(50) NOT NULL DEFAULT '' COMMENT '教材版本',
    lesson VARCHAR(100) NOT NULL DEFAULT '' COMMENT '课文名称',
    title VARCHAR(200) NOT NULL COMMENT '知识条目标题',
    content TEXT NOT NULL COMMENT '知识内容',
    keywords_json JSON COMMENT '检索关键词',
    source VARCHAR(30) NOT NULL DEFAULT 'manual' COMMENT 'textbook_preload/auto_generated/article_backfeed/manual',
    auto_approved TINYINT(1) NOT NULL DEFAULT 1 COMMENT '自动生成的内容是否直接可用',
    used_count INT NOT NULL DEFAULT 0 COMMENT '被文章引用的次数',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_student (student_id),
    INDEX idx_grade (grade_level),
    INDEX idx_subject (subject),
    INDEX idx_source (source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库条目';
