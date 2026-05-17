-- Migration 011: 好奇心对话系统
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL DEFAULT 1 COMMENT '所属学生ID',
    curiosity_event_id INT NOT NULL COMMENT '关联的好奇心事件',
    status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'active / completed',
    turn_count INT NOT NULL DEFAULT 0 COMMENT '对话轮次',
    final_article_id INT DEFAULT NULL COMMENT '最终生成的文章ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_student (student_id),
    INDEX idx_event (curiosity_event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话会话';

CREATE TABLE IF NOT EXISTS conversation_turns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL COMMENT '会话ID',
    role VARCHAR(20) NOT NULL COMMENT 'user / assistant',
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id),
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话轮次';
