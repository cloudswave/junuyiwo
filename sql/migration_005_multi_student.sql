-- ============================================
-- 多孩子支持 数据库升级 (v2.0)
-- 执行方式: mysql -u root -p junyi_word < migration_005_multi_student.sql
-- ============================================

-- 1. 创建学生表
CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL COMMENT '孩子昵称，如俊宜、小美',
    avatar VARCHAR(200) DEFAULT '' COMMENT '头像emoji',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 插入默认学生（已有数据的归属）
INSERT INTO students (id, name, avatar) VALUES (1, '俊宜', '🐯')
ON DUPLICATE KEY UPDATE name=name;

-- 3. 各业务表增加 student_id 列
ALTER TABLE daily_characters ADD COLUMN IF NOT EXISTS student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID';
ALTER TABLE daily_articles ADD COLUMN IF NOT EXISTS student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID';
ALTER TABLE forgotten_characters ADD COLUMN IF NOT EXISTS student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID';
ALTER TABLE curiosity_events ADD COLUMN IF NOT EXISTS student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID';
ALTER TABLE reading_behaviors ADD COLUMN IF NOT EXISTS student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID';
ALTER TABLE user_word_mastery ADD COLUMN IF NOT EXISTS student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID';
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID';
ALTER TABLE knowledge_links ADD COLUMN IF NOT EXISTS student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID';
ALTER TABLE voice_profiles ADD COLUMN IF NOT EXISTS student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID';
ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID';

-- 4. 为 student_id 建立索引
CREATE INDEX IF NOT EXISTS idx_dc_student ON daily_characters(student_id);
CREATE INDEX IF NOT EXISTS idx_da_student ON daily_articles(student_id);
CREATE INDEX IF NOT EXISTS idx_fc_student ON forgotten_characters(student_id);
CREATE INDEX IF NOT EXISTS idx_ce_student ON curiosity_events(student_id);
CREATE INDEX IF NOT EXISTS idx_rb_student ON reading_behaviors(student_id);
CREATE INDEX IF NOT EXISTS idx_kn_student ON knowledge_nodes(student_id);
CREATE INDEX IF NOT EXISTS idx_vp_student ON voice_profiles(student_id);

-- 5. 遗忘字表：移除旧唯一约束（多孩子同字不冲突）
-- 如果已存在唯一索引则删除
-- ALTER TABLE forgotten_characters DROP INDEX IF EXISTS hanzi;
-- 重建为非唯一索引
CREATE INDEX IF NOT EXISTS idx_fc_hanzi ON forgotten_characters(hanzi);

SELECT 'Migration 005 (multi-student) completed.' AS status;
