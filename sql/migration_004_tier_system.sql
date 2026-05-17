-- Migration 004: Three-tier character library system
-- Replace source/discover_count with tier/confirm_count/last_confirm_article_id

ALTER TABLE daily_characters
  ADD COLUMN tier INT DEFAULT 1 COMMENT '字库层级: 1=新字库(学习中),2=工作库(巩固中),3=永久库(已掌握)',
  ADD COLUMN confirm_count INT DEFAULT 0 COMMENT '当前层级的确认次数，满3次晋升',
  ADD COLUMN last_confirm_article_id INT NULL COMMENT '最近确认的文章ID，用于跨文章去重';

-- Migrate existing data:
-- source='formal' → tier=1 (新字库), keep discover_count as confirm_count
-- source='discovered' → tier=2 (工作库), keep discover_count as confirm_count
UPDATE daily_characters SET tier = 1, confirm_count = COALESCE(discover_count, 0) WHERE source = 'formal';
UPDATE daily_characters SET tier = 2, confirm_count = COALESCE(discover_count, 0) WHERE source = 'discovered';

ALTER TABLE daily_characters
  DROP COLUMN source,
  DROP COLUMN discover_count;
