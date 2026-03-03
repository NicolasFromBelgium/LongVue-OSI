# tests/test_scraper.py
import pytest
import sqlite3
from scrapy.http import TextResponse, Request
from longvue_osi.scraper import OsintSpider, DbPipeline
from longvue_osi.database import DB_PATH


@pytest.fixture
def mock_response():
    """Fixture for mock HTML response using TextResponse."""
    body = b"""
    <html>
        <head><title>Test Title</title></head>
        <body><h1>Test Content</h1></body>
    </html>
    """
    return TextResponse(
        url="https://example.com",
        body=body,
        encoding="utf-8",
        request=Request("https://example.com"),
    )


def test_spider_init():
    spider = OsintSpider()
    assert spider.name == "osint_spider", "Spider name should be 'osint_spider'."
    assert spider.start_urls == ["https://example.com"], "Start URLs should include example.com."


def test_spider_parse(mock_response):
    spider = OsintSpider()
    results = list(spider.parse(mock_response))
    assert len(results) == 1, "Should yield one item."
    item = results[0]
    assert isinstance(item["uuid"], str), "Item should have a UUID string."
    assert item["title"] == "Test Title", "Parsed title incorrect."
    assert item["url"] == "https://example.com", "URL should match."
    assert item["http_status"] == 200, "HTTP status should be set."


def test_spider_inserts_to_db(mock_response):
    # Clear DB for clean test (or use a temp DB in real prod; here simple delete)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM osint_data")
    conn.commit()
    initial_count = cursor.execute("SELECT COUNT(*) FROM osint_data").fetchone()[0]
    conn.close()

    spider = OsintSpider()
    items = list(spider.parse(mock_response))  # Run parse to get items

    pipeline = DbPipeline()
    for item in items:
        pipeline.process_item(item, spider)

    # Check insertion
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    new_count = cursor.execute("SELECT COUNT(*) FROM osint_data").fetchone()[0]
    assert new_count == initial_count + 1, "Item should be inserted into DB."
    conn.close()
