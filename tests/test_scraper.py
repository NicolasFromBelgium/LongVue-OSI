# tests/test_scraper.py
import pytest
import sqlite3
from scrapy.http import Request
from longvue_osi.scraper import OsintSpider, DbPipeline
from longvue_osi.database import DB_PATH
from scrapy.http import HtmlResponse  # Add HtmlResponse


@pytest.fixture
def mock_response():
    body = b"""
    <html>
        <head><title>Test Title</title></head>
        <body><h1>Test Content</h1></body>
    </html>
    """
    return HtmlResponse(
        url="https://quotes.toscrape.com",
        body=body,
        encoding="utf-8",
        request=Request("https://quotes.toscrape.com"),
    )


@pytest.fixture
def mock_start_response():
    body = b"""
    <html>
        <head><title>Page 1</title></head>
        <body>
            <a href="/page/2/">Next Page</a>
        </body>
    </html>
    """
    return HtmlResponse(
        url="https://test.com", body=body, encoding="utf-8", request=Request("https://test.com")
    )


@pytest.fixture
def mock_next_response():
    body = b"""
    <html>
        <head><title>Page 2</title></head>
        <body><h1>Content 2</h1></body>
    </html>
    """
    return HtmlResponse(
        url="https://test.com/page/2/",
        body=body,
        encoding="utf-8",
        request=Request("https://test.com/page/2/"),
    )


def test_spider_init():
    spider = OsintSpider()
    assert spider.name == "osint_spider", "Spider name should be 'osint_spider'."
    assert spider.start_urls == [
        "https://quotes.toscrape.com"
    ], "Start URLs should include quotes.toscrape.com."


def test_spider_parse(mock_response):
    spider = OsintSpider()
    results = list(spider.parse_item(mock_response))  # Changed to parse_item
    assert len(results) == 1, "Should yield one item."
    item = results[0]
    assert isinstance(item["uuid"], str), "Item should have a UUID string."
    assert item["title"] == "Test Title", "Parsed title incorrect."
    assert item["url"] == "https://quotes.toscrape.com", "URL should match."
    assert item["http_status"] == 200, "HTTP status should be set."


def test_spider_inserts_to_db(mock_response):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM osint_data")
    conn.commit()
    initial_count = cursor.execute("SELECT COUNT(*) FROM osint_data").fetchone()[0]
    conn.close()

    spider = OsintSpider()
    items = list(spider.parse_item(mock_response))  # Changed to parse_item

    pipeline = DbPipeline()
    for item in items:
        pipeline.process_item(item, spider)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    new_count = cursor.execute("SELECT COUNT(*) FROM osint_data").fetchone()[0]
    assert new_count == initial_count + 1, "Item should be inserted into DB."
    conn.close()


# Add to tests/test_scraper.py

# Update fixtures

# ... (rest of the file unchanged)


def test_spider_follows_links(mock_start_response, mock_next_response):
    spider = OsintSpider()
    # Test link extraction
    requests = list(spider._requests_to_follow(mock_start_response))
    assert len(requests) == 1, "Should yield one request for next page."
    assert requests[0].url == "https://test.com/page/2/", "Next URL incorrect."
    rule_index = requests[0].meta["rule"]
    rule = spider.rules[rule_index]
    assert rule.callback == spider.parse_item.__name__, "Rule callback should be parse_item."
    # Test items from both pages
    items_start = list(spider.parse_item(mock_start_response))
    items_next = list(spider.parse_item(mock_next_response))
    assert len(items_start) == 1, "Start page should yield one item."
    assert items_start[0]["title"] == "Page 1", "Start page title incorrect."
    assert len(items_next) == 1, "Next page should yield one item."
    assert items_next[0]["title"] == "Page 2", "Next page title incorrect."


# ... (rest of the file unchanged)


def test_multi_inserts_to_db(mock_start_response, mock_next_response):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM osint_data")
    conn.commit()
    initial_count = cursor.execute("SELECT COUNT(*) FROM osint_data").fetchone()[0]
    conn.close()

    spider = OsintSpider()
    items = list(spider.parse_item(mock_start_response)) + list(
        spider.parse_item(mock_next_response)
    )  # Changed to parse_item

    pipeline = DbPipeline()
    for item in items:
        pipeline.process_item(item, spider)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    new_count = cursor.execute("SELECT COUNT(*) FROM osint_data").fetchone()[0]
    assert new_count == initial_count + len(items), "Multiple items should be inserted."
    conn.close()
