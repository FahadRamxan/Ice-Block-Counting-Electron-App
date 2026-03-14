import os
import sqlite3
from datetime import datetime, timedelta

def _db_path():
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'ice_factory.db')

def get_conn():
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS nvrs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS run_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            nvr_id INTEGER,
            nvr_name TEXT,
            channel INTEGER,
            total_unique_blocks INTEGER NOT NULL DEFAULT 0,
            left_platform INTEGER DEFAULT 0,
            still_on_platform INTEGER DEFAULT 0,
            source TEXT DEFAULT 'test_video',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_run_events_date ON run_events(run_date)')
        conn.commit()
    finally:
        conn.close()

def insert_run_event(
    run_date: str,
    total_unique_blocks: int,
    left_platform: int = 0,
    still_on_platform: int = 0,
    nvr_id=None,
    nvr_name=None,
    channel=None,
    source='test_video',
):
    conn = get_conn()
    try:
        conn.execute(
            '''INSERT INTO run_events (run_date, nvr_id, nvr_name, channel, total_unique_blocks,
               left_platform, still_on_platform, source) VALUES (?,?,?,?,?,?,?,?)''',
            (run_date, nvr_id, nvr_name, channel, total_unique_blocks, left_platform, still_on_platform, source),
        )
        conn.commit()
    finally:
        conn.close()

def seed_demo_statistics_if_empty():
    """Insert sample daily points so Statistics page is non-empty on first open."""
    conn = get_conn()
    try:
        n = conn.execute('SELECT COUNT(*) AS c FROM run_events').fetchone()['c']
        if n > 0:
            return
        today = datetime.utcnow().date()
        import random
        random.seed(42)
        for i in range(120):
            d = today - timedelta(days=i)
            ds = d.isoformat()
            # a few runs per week
            if i % 7 == 0:
                conn.execute(
                    '''INSERT INTO run_events (run_date, nvr_id, nvr_name, channel, total_unique_blocks,
                       left_platform, still_on_platform, source) VALUES (?,?,?,?,?,?,?,?)''',
                    (ds, 1, 'Demo NVR', None, random.randint(8, 45), random.randint(0, 5), random.randint(2, 20), 'demo'),
                )
            if i % 3 == 0:
                conn.execute(
                    '''INSERT INTO run_events (run_date, nvr_id, nvr_name, channel, total_unique_blocks,
                       left_platform, still_on_platform, source) VALUES (?,?,?,?,?,?,?,?)''',
                    (ds, None, None, None, random.randint(5, 30), random.randint(0, 3), random.randint(1, 12), 'demo'),
                )
        conn.commit()
    finally:
        conn.close()
