# src/longvue_osi/scraper.py
import scrapy
import uuid
import sqlite3
from longvue_osi.database import DB_PATH

class OsintItem(scrapy.Item):
    uuid = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    http_status = scrapy.Field()  # Added for DB insert

class OsintSpider(scrapy.Spider):
    name = "osint_spider"
    start_urls = ["https://example.com"]  # Customize as needed

    def parse(self, response):
        item = OsintItem()
        item["uuid"] = str(uuid.uuid4())
        item["title"] = response.css("title::text").get()
        item["url"] = response.url
        item["http_status"] = response.status  # Added
        yield item

class DbPipeline:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()

    def process_item(self, item, spider):
        self.cursor.execute("""
            INSERT INTO osint_data (uuid, title, url, status, http_status)
            VALUES (?, ?, ?, 'done', ?)
        """, (item["uuid"], item["title"], item["url"], item["http_status"]))  # Fixed to use item
        self.conn.commit()
        return item

    def close_spider(self, spider):
        self.conn.close()

# Run function (for main.py or direct run)
from scrapy.crawler import CrawlerProcess

def run_scraper(start_url="https://example.com"):
    process = CrawlerProcess(settings={
        "ITEM_PIPELINES": {"longvue_osi.scraper.DbPipeline": 300},
        "FEEDS": {
            "data/osint_data.json": {"format": "json"},
            "data/osint_data.csv": {"format": "csv"},
        },
    })
    process.crawl(OsintSpider, start_urls=[start_url])
    process.start()
