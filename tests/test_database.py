# tests/test_database.py
import os
import uuid
import pytest
import sqlite3

# Chemin absolu vers data.db à la racine
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data.db"))


@pytest.fixture
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


def test_database_file_exists():
    assert os.path.exists(DB_PATH), f"Database file '{DB_PATH}' does not exist."


def test_database_connection(db_connection):
    cursor = db_connection.cursor()
    cursor.execute("SELECT 1")
    assert cursor.fetchone() == (1,), "Failed to execute basic query."


def test_database_schema_exists(db_connection):
    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='osint_data'
    """)
    table_exists = cursor.fetchone()
    assert table_exists, "Table 'osint_data' does not exist."

    # Check columns and types/defaults/constraints
    cursor.execute("PRAGMA table_info(osint_data)")
    columns = cursor.fetchall()
    col_dict = {
        col[1]: {"type": col[2], "notnull": col[3], "default": col[4], "pk": col[5]}
        for col in columns
    }

    expected_columns = {
        "uuid": {"type": "TEXT", "notnull": 1, "pk": 1},  # PK, NOT NULL
        "title": {"type": "TEXT", "notnull": 0},
        "url": {"type": "TEXT", "notnull": 1},
        "source": {"type": "TEXT", "notnull": 0},
        "scraper_agent": {"type": "TEXT", "notnull": 0},
        "status": {"type": "TEXT", "notnull": 0, "default": "'new'"},
        "http_status": {"type": "INTEGER", "notnull": 0},
        "response_time_ms": {"type": "INTEGER", "notnull": 0},
        "created_at": {"type": "DATETIME", "notnull": 0, "default": "CURRENT_TIMESTAMP"},
        "updated_at": {"type": "DATETIME", "notnull": 0, "default": "CURRENT_TIMESTAMP"},
    }

    for col, props in expected_columns.items():
        assert col in col_dict, f"Missing column '{col}'."
        for prop, value in props.items():
            assert (
                col_dict[col][prop] == value
            ), f"Column '{col}' has incorrect {prop}: got {col_dict[col][prop]}, expected {value}."

    # Ensure no removed content columns
    assert "content_json" not in col_dict, "Removed column 'content_json' still exists."
    assert "content_csv" not in col_dict, "Removed column 'content_csv' still exists."

    # Check UUID is unique (implicit in PK, but verify index)
    cursor.execute("PRAGMA index_list(osint_data)")
    indexes = [idx[1] for idx in cursor.fetchall()]
    assert any(
        "sqlite_autoindex_osint_data" in idx for idx in indexes
    ), "No primary key index on uuid."


def test_insert_and_retrieve_data(db_connection):
    sample_uuid = str(uuid.uuid4())
    sample_title = "Test Title"
    sample_url = "https://example.com"
    sample_source = "web"
    sample_scraper_agent = "scrapy"
    sample_status = "new"
    sample_http_status = 200
    sample_response_time_ms = 500

    cursor = db_connection.cursor()
    cursor.execute(
        """
        INSERT INTO osint_data (
            uuid, title, url, source, scraper_agent,
            status, http_status, response_time_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            sample_uuid,
            sample_title,
            sample_url,
            sample_source,
            sample_scraper_agent,
            sample_status,
            sample_http_status,
            sample_response_time_ms,
        ),
    )
    db_connection.commit()

    cursor.execute("SELECT * FROM osint_data WHERE uuid = ?", (sample_uuid,))
    result = cursor.fetchone()
    assert result is not None, "Failed to retrieve inserted data."
    # Verify timestamps are auto-set (can't mock CURRENT_TIMESTAMP, but check they exist)
    assert len(result) == 10, "Incorrect number of columns in result."
