# src/tdd_template/database.py
import os
import sqlite3

# Chemin absolu vers data.db à la racine du projet
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data.db'))

def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS osint_data (
            uuid TEXT PRIMARY KEY NOT NULL,
            title TEXT,
            url TEXT NOT NULL,
            source TEXT,
            scraper_agent TEXT,
            status TEXT DEFAULT 'new',
            http_status INTEGER,
            response_time_ms INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Trigger pour auto-update updated_at
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS update_osint_data_updated_at
        AFTER UPDATE ON osint_data
        FOR EACH ROW
        BEGIN
            UPDATE osint_data SET updated_at = CURRENT_TIMESTAMP WHERE uuid = OLD.uuid;
        END;
    """)
    # Indexes pour perf
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_url ON osint_data(url);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON osint_data(created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON osint_data(status);")
    conn.commit()
    conn.close()

# Appel auto (ou dans main.py)
initialize_database()
