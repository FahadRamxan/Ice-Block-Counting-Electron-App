"""SQLite database and schema for NVRs and run results."""
import os
import sqlite3

DB_PATH = os.environ.get('ICE_DB_PATH')
if not DB_PATH:
    _backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(_backend, 'data', 'ice_factory.db')

def get_db_path():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return DB_PATH

def get_conn():
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS nvrs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ip TEXT NOT NULL,
                port INTEGER NOT NULL DEFAULT 37777,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS run_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nvr_id INTEGER NOT NULL,
                nvr_name TEXT NOT NULL,
                channel INTEGER NOT NULL,
                record_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                ice_block_count INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                video_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (nvr_id) REFERENCES nvrs(id)
            );
        """)
        conn.commit()
    finally:
        conn.close()
