-- 阅读等级系统 — 学生表加字段
-- 适用: MySQL 8.2+
-- 执行: mysql -u root -p junyi_word < migration_008_reading_level.sql
--
-- 如果字段已存在会报错，忽略即可（每条单独执行）

ALTER TABLE students ADD COLUMN reading_level INT NOT NULL DEFAULT 1 COMMENT '阅读等级 1-7';
ALTER TABLE students ADD COLUMN leveled_up_at DATETIME NULL COMMENT '最近升级时间';
ALTER TABLE students ADD COLUMN total_articles_read INT NOT NULL DEFAULT 0 COMMENT '累计读完文章数';
