CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS items (
 id TEXT PRIMARY KEY, source_path TEXT NOT NULL UNIQUE, source_hash TEXT NOT NULL, type TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, sanitizer_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS item_tags (item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE, tag TEXT NOT NULL, PRIMARY KEY(item_id, tag));
CREATE TABLE IF NOT EXISTS chunks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, safe_text TEXT NOT NULL, raw_text TEXT NOT NULL, page INTEGER, heading TEXT,
 embedding_dim INTEGER NOT NULL, embedding_model TEXT NOT NULL, embedding_version TEXT NOT NULL,
 UNIQUE(item_id, ordinal)
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(safe_text, content='chunks', content_rowid='id', tokenize='unicode61');
CREATE TABLE IF NOT EXISTS vec_chunks (chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE, embedding BLOB NOT NULL);
INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1'), ('sanitizer_version', 'v1');
