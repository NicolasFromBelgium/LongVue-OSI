# src/longvue_osi/scraper.py
import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import uuid
import sqlite3
from scrapy.crawler import CrawlerProcess
from longvue_osi.database import DB_PATH


class OsintItem(scrapy.Item):
    uuid = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    http_status = scrapy.Field()


class OsintSpider(CrawlSpider):
    name = "osint_spider"
    start_urls = ["https://quotes.toscrape.com"]
    rules = (Rule(LinkExtractor(allow=("/page/")), callback="parse_item", follow=True),)

    def parse_item(self, response):
        item = OsintItem()
        item["uuid"] = str(uuid.uuid4())
        item["title"] = response.css("title::text").get()
        item["url"] = response.url
        item["http_status"] = response.status
        yield item

        for quote in response.css(".quote"):
            quote_item = OsintItem()
            quote_item["uuid"] = str(uuid.uuid4())
            quote_item["title"] = quote.css(".text::text").get()
            quote_item["url"] = response.url
            quote_item["http_status"] = response.status
            yield quote_item


class DbPipeline:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()

    def process_item(self, item, spider):
        self.cursor.execute(
            """
            INSERT INTO osint_data (uuid, title, url, status, http_status)
            VALUES (?, ?, ?, 'done', ?)
        """,
            (item["uuid"], item["title"], item["url"], item["http_status"]),
        )
        self.conn.commit()
        return item

    def close_spider(self, spider):
        self.conn.close()


def run_scraper(start_url="https://quotes.toscrape.com"):
    process = CrawlerProcess(
        settings={
            "ITEM_PIPELINES": {"longvue_osi.scraper.DbPipeline": 300},
            "FEEDS": {
                "data/osint_data.json": {"format": "json"},
                "data/osint_data.csv": {"format": "csv"},
            },
            "DEPTH_LIMIT": 2,
            "CONCURRENT_REQUESTS": 8,
        }
    )
    process.crawl(OsintSpider, start_urls=[start_url])
    process.start()
