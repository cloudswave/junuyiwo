-- 俊宜识字系统 - 数据库迁移脚本 002
-- 适用: MySQL 8.2+
-- 执行: mysql -u root -p junyi_word < migration_002_voice_cloning.sql
--
-- 变更内容:
--   voice_profiles 表新增 sample_path 字段 — 声音克隆样本音频路径
--   删除 data/audio/ 下旧的逐字录音文件（保留目录结构）

USE junyi_word;

ALTER TABLE voice_profiles ADD COLUMN sample_path VARCHAR(500) NULL COMMENT '声音克隆样本音频路径' AFTER name;
