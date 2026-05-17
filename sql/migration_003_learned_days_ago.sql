-- Add learned_days_ago column to forgotten_characters
-- Captures the learning context at the moment the child first forgot the character:
--   0        = learned today
--   1-7      = learned within the past week
--   8+       = learned historically
--   NULL     = character was never formally learned
ALTER TABLE forgotten_characters
  ADD COLUMN learned_days_ago INT NULL COMMENT '首次遗忘时的学习距今天数: 0=当天,1-7=一周内,8+=历史,null=未学过'
  AFTER category;
