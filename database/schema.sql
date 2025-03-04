CREATE TABLE IF NOT EXISTS thread_name_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_name TEXT NOT NULL,
    owner_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS famima_creds (
    id INTEGER PRIMARY KEY,
    member_code TEXT UNIQUE NOT NULL,
    password TEXT UNIQUE NOT NULL,
    auto_roll_channel_id BIGINT DEFAULT NULL
);

ALTER TABLE thread_name_queue ADD COLUMN thread_id BIGINT DEFAULT NULL;
ALTER TABLE thread_name_queue ADD COLUMN created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE thread_name_queue ADD COLUMN deleted BOOLEAN DEFAULT FALSE;
