from app.db.database import get_conn


SQL_SCHEMA = """

-- ====== Character Cards ======

CREATE TABLE IF NOT EXISTS character_cards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    spec TEXT DEFAULT 'chara_card_v3',
    spec_version TEXT DEFAULT '1.0',
    extensions TEXT DEFAULT '{}',
    cover_json TEXT DEFAULT '{}',
    avatar_json TEXT DEFAULT '{}',
    background_json TEXT DEFAULT '{}',
    character_json TEXT DEFAULT '{}',
    system_prompt TEXT,
    post_history_instructions TEXT,
    depth_prompt_json TEXT,
    worldbook_ids TEXT DEFAULT '[]',
    preset_name TEXT,
    preset_config_json TEXT DEFAULT '{}',
    image_config_json TEXT DEFAULT '{}',
    authors_note_json TEXT,
    quick_reply_set_ids TEXT DEFAULT '[]',
    regex_script_ids TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft',
    version INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT '',
    published_at TEXT
);

-- ====== Chat Sessions ======

CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL,
    mode TEXT DEFAULT 'play',
    name TEXT DEFAULT '',
    greeting_index INTEGER DEFAULT 0,
    model TEXT DEFAULT '',
    worldbook_ids TEXT DEFAULT '[]',
    preset_name TEXT DEFAULT '',
    background_image TEXT,
    parent_session_id TEXT,
    branch_number INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES character_cards(id)
);

-- ====== Chat Messages ======

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    content_parts_json TEXT,
    media_json TEXT DEFAULT '[]',
    idx INTEGER NOT NULL,
    round_index INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    swipes_json TEXT DEFAULT '[]',
    swipe_index INTEGER DEFAULT 0,
    has_checkpoint INTEGER DEFAULT 0,
    locked INTEGER DEFAULT 0,
    tool_calls_json TEXT DEFAULT '[]',
    tool_call_id TEXT,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id, idx);

-- ====== Story Characters (runtime) ======

CREATE TABLE IF NOT EXISTS story_characters (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    attributes_json TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    is_alive INTEGER DEFAULT 1,
    first_seen_round INTEGER DEFAULT 0,
    last_seen_round INTEGER DEFAULT 0,
    source TEXT DEFAULT 'card_definition',
    images_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_chars_session ON story_characters(session_id);

-- ====== Character Change Logs ======

CREATE TABLE IF NOT EXISTS character_change_logs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    message_index INTEGER NOT NULL,
    character_id TEXT NOT NULL,
    character_name TEXT NOT NULL,
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    changes_json TEXT DEFAULT '[]',
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_changelog_session ON character_change_logs(session_id, message_index);

-- ====== Memory Summaries ======

CREATE TABLE IF NOT EXISTS memory_summaries (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    segment_start INTEGER NOT NULL,
    segment_end INTEGER NOT NULL,
    summary TEXT DEFAULT '',
    key_events_json TEXT DEFAULT '[]',
    state_snapshot_json TEXT DEFAULT '{}',
    locked INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_summaries(session_id, segment_start);

-- ====== Memory Config ======

CREATE TABLE IF NOT EXISTS memory_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    short_term_rounds INTEGER DEFAULT 5,
    summary_interval INTEGER DEFAULT 10,
    summary_model TEXT DEFAULT 'deepseek',
    summary_template TEXT DEFAULT '[剧情摘要 - 第{start}至{end}轮]\n{summary}'
);

-- ====== Long-Term Memories ======

CREATE TABLE IF NOT EXISTS long_term_memories (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '其他',
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_ltm_session ON long_term_memories(session_id);

-- ====== WorldBook Runtime State ======

CREATE TABLE IF NOT EXISTS worldbook_runtime_state (
    session_id TEXT NOT NULL,
    worldbook_id TEXT NOT NULL,
    sticky_map_json TEXT DEFAULT '{}',
    cooldown_map_json TEXT DEFAULT '{}',
    round_count INTEGER DEFAULT 0,
    PRIMARY KEY (session_id, worldbook_id),
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

-- ====== User Personas ======

CREATE TABLE IF NOT EXISTS user_personas (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    avatar_path TEXT,
    description TEXT DEFAULT '',
    injection_depth INTEGER DEFAULT 4,
    injection_role TEXT DEFAULT 'system',
    is_default INTEGER DEFAULT 0,
    locked_chat_id TEXT,
    locked_card_id TEXT
);

-- ====== Model Configs ======

CREATE TABLE IF NOT EXISTS model_configs (
    name TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key TEXT DEFAULT '',
    temperature REAL DEFAULT 0.8,
    max_tokens INTEGER DEFAULT 2048,
    top_p REAL DEFAULT 0.95,
    frequency_penalty REAL DEFAULT 0.3,
    presence_penalty REAL DEFAULT 0.2,
    supports_vision INTEGER DEFAULT 0,
    supports_tool_calling INTEGER DEFAULT 0
);

-- ====== UI State ======

CREATE TABLE IF NOT EXISTS ui_state (
    session_id TEXT PRIMARY KEY,
    values_json TEXT DEFAULT '{}',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

-- ====== Presets (stored as JSON files, this table is for index) ======

CREATE TABLE IF NOT EXISTS presets_index (
    name TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ====== WorldBooks (stored as JSON files, this table is for index) ======

CREATE TABLE IF NOT EXISTS worldbooks_index (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def init_db():
    conn = get_conn()
    conn.executescript(SQL_SCHEMA)
    conn.commit()

    # Migrations for existing tables
    existing_cols = [
        row[1] for row in conn.execute("PRAGMA table_info(character_cards)").fetchall()
    ]
    if "background_json" not in existing_cols:
        conn.execute("ALTER TABLE character_cards ADD COLUMN background_json TEXT DEFAULT '{}'")
        conn.commit()

    # Ensure the system card exists for konata chat sessions (FK constraint)
    conn.execute("""
        INSERT OR IGNORE INTO character_cards (id, name, description, tags, created_at, updated_at)
        VALUES ('_konata_system', 'Izumi Studio 系统助手', '系统对话功能的虚拟角色卡', '[]', datetime('now'), datetime('now'))
    """)
    conn.commit()

    # Run WAL checkpoint to clear stale shared memory after unclean shutdown
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.commit()
    conn.close()
