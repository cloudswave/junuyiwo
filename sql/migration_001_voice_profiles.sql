-- 俊宜识字系统 - 数据库迁移脚本 001
-- 适用: MySQL 8.2+
-- 执行: mysql -u root -p junyi_word < migration_001_voice_profiles.sql
--
-- 变更内容:
--   新增 voice_profiles 表 — 声音样版（老师/家长真人录音）

USE junyi_word;

-- 10. 声音样版
CREATE TABLE IF NOT EXISTS voice_profiles (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL COMMENT '样版名称，如"李老师"',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
