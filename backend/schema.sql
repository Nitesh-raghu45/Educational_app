-- Reference DDL for MariaDB, generated from app/models.py (the app creates these tables on startup).
-- UUIDs are stored as CHAR(32) hex by SQLAlchemy's Uuid type.

CREATE TABLE users (
	id CHAR(32) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	created_at DATETIME(6) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE chat_sections (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	title VARCHAR(200), 
	question_count INTEGER NOT NULL, 
	max_questions INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	summary TEXT, 
	summary_message_count INTEGER NOT NULL, 
	created_at DATETIME(6) NOT NULL, 
	updated_at DATETIME(6) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_sections_user_updated ON chat_sections (user_id, updated_at);

CREATE TABLE documents (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	content_type VARCHAR(100) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	storage_path VARCHAR(500) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	error TEXT, 
	chunk_count INTEGER NOT NULL, 
	created_at DATETIME(6) NOT NULL, 
	updated_at DATETIME(6) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_documents_user_created ON documents (user_id, created_at);

CREATE TABLE chat_messages (
	id CHAR(32) NOT NULL, 
	section_id CHAR(32) NOT NULL, 
	`role` VARCHAR(20) NOT NULL, 
	content TEXT NOT NULL, 
	citations JSON, 
	status VARCHAR(20) NOT NULL, 
	reply_to_id CHAR(32), 
	idempotency_key VARCHAR(100), 
	error TEXT, 
	created_at DATETIME(6) NOT NULL, 
	updated_at DATETIME(6) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_messages_idempotency UNIQUE (section_id, idempotency_key), 
	FOREIGN KEY(section_id) REFERENCES chat_sections (id) ON DELETE CASCADE, 
	FOREIGN KEY(reply_to_id) REFERENCES chat_messages (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_messages_section_created ON chat_messages (section_id, created_at);

CREATE TABLE document_chunks (
	id VARCHAR(80) NOT NULL, 
	document_id CHAR(32) NOT NULL, 
	chunk_index INTEGER NOT NULL, 
	page INTEGER, 
	text TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id);

CREATE TABLE quizzes (
	id CHAR(32) NOT NULL, 
	section_id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	topic VARCHAR(200), 
	questions JSON NOT NULL, 
	created_at DATETIME(6) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES chat_sections (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_quizzes_section_id ON quizzes (section_id);

CREATE TABLE section_documents (
	section_id CHAR(32) NOT NULL, 
	document_id CHAR(32) NOT NULL, 
	created_at DATETIME(6) NOT NULL, 
	PRIMARY KEY (section_id, document_id), 
	FOREIGN KEY(section_id) REFERENCES chat_sections (id) ON DELETE CASCADE, 
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE quiz_attempts (
	id CHAR(32) NOT NULL, 
	quiz_id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	answers JSON NOT NULL, 
	score INTEGER NOT NULL, 
	total INTEGER NOT NULL, 
	created_at DATETIME(6) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_quiz_attempts_quiz_id ON quiz_attempts (quiz_id);
