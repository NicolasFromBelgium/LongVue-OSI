import ollama
import logging
import random
import hashlib
import csv
import os
import json
import decimal
from bs4 import BeautifulSoup
import requests
import mysql.connector
import time
import nltk
from datetime import datetime
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from transformers import pipeline
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Download NLTK data
nltk.download("punkt", quiet=True)
nltk.download("stopwords", quiet=True)
stop_words = set(stopwords.words("english"))

# --- Config MySQL ---
db = mysql.connector.connect(host="localhost", user="root", password="", database="")
cursor = db.cursor()

# Create processed_batches table for caching
cursor.execute("""
    CREATE TABLE IF NOT EXISTS processed_batches (
        batch_hash VARCHAR(64) PRIMARY KEY,
        ollama_results JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# Create dashboard_analysis table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS dashboard_analysis (
        id INT AUTO_INCREMENT PRIMARY KEY,
        analysis_id INT NOT NULL,
        overall_sentiment DECIMAL(5,2),
        top_topics JSON,
        advised_stance TEXT,
        market_context VARCHAR(50),
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (analysis_id) REFERENCES sentiment_analysis(id) ON DELETE CASCADE
    )
""")

# Create dynamic_rsi table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS dynamic_rsi (
        id INT AUTO_INCREMENT PRIMARY KEY,
        analysis_id INT NOT NULL,
        rsi_value DECIMAL(5,2),
        buy_threshold DECIMAL(5,2),
        sell_threshold DECIMAL(5,2),
        sentiment_score DECIMAL(5,2),
        global_impact DECIMAL(5,2),
        adjustment_factor DECIMAL(5,2),
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (analysis_id) REFERENCES sentiment_analysis(id) ON DELETE CASCADE
    )
""")

# Create sentiment_index table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS sentiment_index (
        id INT AUTO_INCREMENT PRIMARY KEY,
        analysis_day DATE,
        market_context VARCHAR(50),
        avg_sentiment_score DECIMAL(5,2),
        weighted_sentiment_index DECIMAL(5,2),
        headlines_analyzed INT,
        analysis_id INT NOT NULL,
        FOREIGN KEY (analysis_id) REFERENCES sentiment_analysis(id) ON DELETE CASCADE
    )
""")

# Clean old cache entries (older than 7 days)
cursor.execute("DELETE FROM processed_batches WHERE created_at < NOW() - INTERVAL 7 DAY")
db.commit()

# Create output directory
output_dir = "./dashboard_analysis"
os.makedirs(output_dir, exist_ok=True)

# --- Config ---
sources = [
    {
        "name": "Reuters",
        "url": "https://www.reuters.com/business/",
        "css": "a[data-testid='Heading']",
        "selenium": True,
    },
    {
        "name": "CoinDesk",
        "url": "https://www.coindesk.com/",
        "css": "h2, .article__title",
        "selenium": True,
    },
    {
        "name": "Cointelegraph",
        "url": "https://cointelegraph.com/",
        "css": "h2.post-preview-title, .post-title, .post-card__title",
        "selenium": True,
    },
    {
        "name": "The Block",
        "url": "https://www.theblock.co/",
        "css": "a.sh-text-md, .article__title",
        "selenium": True,
    },
    {
        "name": "Crypto.news",
        "url": "https://crypto.news",
        "css": "h2, h3, .post-title, .entry-title, .news-title, a.post-card__title",
        "selenium": True,
    },
    {
        "name": "CNBC Business",
        "url": "https://www.cnbc.com/business/",
        "css": "h3[data-testid='CardHeadline'], .Card-title",
        "selenium": True,
    },
    {
        "name": "Financial Times",
        "url": "https://www.ft.com/markets",
        "css": ".o-teaser__heading, .story-body__headline h2",
        "selenium": True,
    },
    {
        "name": "Bloomberg Markets",
        "url": "https://www.bloomberg.com/markets",
        "css": "h2, h3, .story-link, .headline, h1, a[data-testid='story-title']",
        "selenium": True,
    },
]
max_headlines = 50
delay = 0.5
all_sources = " + ".join([s["name"] for s in sources])
relevant_topics = "financial, markets, geopolitical context, crypto regulations"
batch_size = 20

# User-Agent rotation
user_agents = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

# Proxy (disabled)
proxies = {}


# --- Selenium Fallback ---
def get_selenium_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={random.choice(user_agents)}")
    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=options)


# --- NLP GPU ---
sentiment_model = pipeline(
    "sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english", device=0
)
logging.info("Device set to use cuda:0")


# --- Fonction Keywords ---
def extract_keywords(texts, top_k=10):
    if not texts:
        return []
    try:
        vectorizer = TfidfVectorizer(max_features=100, stop_words=list(stop_words))
        tfidf_matrix = vectorizer.fit_transform(texts)
        feature_names = vectorizer.get_feature_names_out()
        scores = tfidf_matrix.mean(axis=0).A1
        top_indices = scores.argsort()[-top_k:][::-1]
        return [feature_names[i] for i in top_indices]
    except ValueError as e:
        logging.warning(f"Keywords extraction failed: {e}")
        return []


# --- JSON Encoder for Decimal and Datetime ---
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(CustomEncoder, self).default(obj)


# --- Fonction Scrape + NLP ---
def scrape_and_analyze(source_dict, driver=None):
    start_time = time.perf_counter()
    headlines_data = []
    try:
        if source_dict.get("selenium", False):
            logging.info(f"Using Selenium for {source_dict['name']} ({source_dict['url']})")
            driver.get(source_dict["url"])
            time.sleep(5)
            soup = BeautifulSoup(driver.page_source, "lxml")
        else:
            logging.info(f"Using requests for {source_dict['name']} ({source_dict['url']})")
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            resp = requests.get(source_dict["url"], headers=headers, proxies=proxies, timeout=10)
            logging.info(f"HTTP status for {source_dict['name']}: {resp.status_code}")
            if resp.status_code != 200:
                logging.warning(f"Failed to fetch {source_dict['name']}: Status {resp.status_code}")
                return [], int((time.perf_counter() - start_time) * 1000)
            soup = BeautifulSoup(resp.content, "lxml")

        headlines_elements = soup.select(source_dict["css"])
        logging.info(
            f"Found {len(headlines_elements)} headlines for {source_dict['name']} with selector '{source_dict['css']}'"
        )
        texts = [
            h.get_text(strip=True)
            for h in headlines_elements[:max_headlines]
            if h.get_text(strip=True) and len(h.get_text(strip=True)) >= 10
        ]
        logging.info(f"Valid headlines after filtering: {len(texts)}")
        if not texts:
            return [], int((time.perf_counter() - start_time) * 1000)

        # Removed the "new headlines" check to always process at least 3 (or all valid) headlines
        new_texts = texts  # Process all valid headlines to ensure analysis

        if not new_texts:
            logging.info(f"No headlines for {source_dict['name']}")
            return [], int((time.perf_counter() - start_time) * 1000)

        # Batch NLP processing
        results = sentiment_model(new_texts, batch_size=16)
        for text, result in zip(new_texts, results):
            label = result["label"].lower()
            score = result["score"]
            sentiment_score = score if "pos" in label else -score
            headlines_data.append(
                {
                    "text": text,
                    "sentiment_score": sentiment_score,
                    "label": label,
                    "confidence": score,
                    "source": source_dict["name"],
                }
            )
    except Exception as e:
        logging.error(f"Error in scrape_and_analyze for {source_dict['name']}: {str(e)}")
    processing_time_ms = int((time.perf_counter() - start_time) * 1000)
    logging.info(
        f"Processed {len(headlines_data)} headlines for {source_dict['name']} in {processing_time_ms}ms"
    )
    return headlines_data, processing_time_ms


# --- Main Loop ---
while True:
    # --- Créer lot ---
    sql_analysis = """
        INSERT INTO sentiment_analysis (bot_profile, source, headlines_count, market_context, analysis_timestamp)
        VALUES (%s, %s, %s, %s, NOW())
    """
    bot_profile = "cron_nlp_pipeline_perf"
    headlines_count = 0
    market_context = "crypto_business"
    cursor.execute(sql_analysis, (bot_profile, all_sources, headlines_count, market_context))
    analysis_id = cursor.lastrowid
    logging.info(f"Créé sentiment_analysis id={analysis_id}")

    # --- Scraper tous ---
    driver = get_selenium_driver()
    all_headlines_data = []
    total_inserted = 0
    total_processing_time_ms = 0
    for src in sources:
        data, proc_time = scrape_and_analyze(src, driver)
        all_headlines_data.extend(data)
        total_inserted += len(data)
        total_processing_time_ms += proc_time
        for item in data:
            sql_history = """
                INSERT INTO sentiment_history 
                (analysis_id, headline, source, published_at, sentiment_score, sentiment_label, confidence, language, url)
                VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, NULL)
            """
            cursor.execute(
                sql_history,
                (
                    analysis_id,
                    item["text"],
                    item["source"],
                    item["sentiment_score"],
                    item["label"],
                    item["confidence"],
                    "en",
                ),
            )

    headlines_count = total_inserted
    db.commit()

    # --- Agrégats pour sentiment_analysis ---
    if all_headlines_data:
        scores = [d["sentiment_score"] for d in all_headlines_data]
        confs = [d["confidence"] for d in all_headlines_data]
        labels = [d["label"] for d in all_headlines_data]
        avg_score = sum(scores) / len(scores)
        avg_conf = sum(confs) / len(confs)
        major_label = Counter(labels).most_common(1)[0][0] if labels else "neutral"
        texts = [d["text"] for d in all_headlines_data]
        keywords_list = extract_keywords(texts)
        keywords = json.dumps(keywords_list) if keywords_list else "[]"
        raw_data = json.dumps(all_headlines_data[:10])
        sql_update = """
            UPDATE sentiment_analysis 
            SET headlines_count=%s, sentiment_score=%s, sentiment_label=%s, confidence=%s, 
                keywords=%s, raw_data=%s, processing_time_ms=%s
            WHERE analysis_id=%s
        """
        try:
            cursor.execute(
                sql_update,
                (
                    headlines_count,
                    round(avg_score, 2),
                    major_label,
                    round(avg_conf, 2),
                    keywords,
                    raw_data,
                    total_processing_time_ms,
                    analysis_id,
                ),
            )
            db.commit()
        except mysql.connector.Error as e:
            logging.error(f"Failed to update sentiment_analysis: {e}")
            keywords = "[]"
            cursor.execute(
                sql_update,
                (
                    headlines_count,
                    round(avg_score, 2),
                    major_label,
                    round(avg_conf, 2),
                    keywords,
                    raw_data,
                    total_processing_time_ms,
                    analysis_id,
                ),
            )
            db.commit()

    driver.quit()

    # --- Ollama Integration ---
    ollama_results = []
    if all_headlines_data:
        start_time = time.perf_counter()
        headlines_texts = [d["text"] for d in all_headlines_data]
        ollama_model = "safe-70b"

        # Prompt template
        prompt_template = """
        You are an expert news analyst specializing in crypto and business markets.
        Given this list of headlines: {headlines}
        
        Perform the following:
        1. Identify 3-5 main topics from the headlines, prioritizing topics related to {relevant_topics}. If no relevant topics, provide a generic summary like "No major updates in relevant areas (financial, markets, geopolitical, crypto regulations)."
        2. For each topic:
           - Provide a 1-2 sentence summary of the headlines in that topic.
           - Sort the relevant headlines by descending order of potential market impact (most impactful first).
           - Rate local impact (1-10, e.g., effects on specific countries/regions).
           - Rate global impact (1-10, e.g., worldwide market effects).
           - Rate relevance to crypto/business (1-10).
           - Add any other ratings as JSON (e.g., {{"urgency": 7, "novelty": 5}}).
        
        Output ONLY in this JSON format. Ensure the output is valid JSON and nothing else:
        [
            {{
                "topic": "Topic Name",
                "summary": "Summary text",
                "sorted_headlines": ["headline1", "headline2", ...],
                "local_impact": 5,
                "global_impact": 8,
                "relevance_rating": 9,
                "other_ratings": {{"urgency": 7}}
            }},
            ...
        ]
        """.replace("{relevant_topics}", relevant_topics)

        # Process in batches with caching
        for i in range(0, len(headlines_texts), batch_size):
            batch = headlines_texts[i : i + batch_size]
            batch_str = json.dumps(sorted(batch))
            batch_hash = hashlib.sha256(batch_str.encode()).hexdigest()

            # Check cache
            cursor.execute(
                "SELECT ollama_results FROM processed_batches WHERE batch_hash = %s", (batch_hash,)
            )
            cached = cursor.fetchone()
            if cached:
                logging.info(f"Cache hit for batch hash {batch_hash}")
                ollama_output = json.loads(cached[0])
            else:
                try:
                    prompt = prompt_template.format(headlines="\n".join([f"- {h}" for h in batch]))
                    logging.info(
                        f"Sending batch of {len(batch)} headlines to Ollama ({ollama_model})"
                    )
                    response = ollama.generate(model=ollama_model, prompt=prompt)
                    ollama_output_str = response["response"].strip()
                    logging.debug(f"Ollama raw response: {ollama_output_str[:200]}...")
                    try:
                        if ollama_output_str.startswith("[") and ollama_output_str.endswith("]"):
                            ollama_output = json.loads(ollama_output_str)
                        else:
                            json_start = ollama_output_str.find("[")
                            json_end = ollama_output_str.rfind("]") + 1
                            if json_start != -1 and json_end != 0:
                                ollama_output_str = ollama_output_str[json_start:json_end]
                                ollama_output = json.loads(ollama_output_str)
                            else:
                                raise json.JSONDecodeError(
                                    "No valid JSON found", ollama_output_str, 0
                                )
                        cursor.execute(
                            "INSERT INTO processed_batches (batch_hash, ollama_results) VALUES (%s, %s)",
                            (batch_hash, json.dumps(ollama_output)),
                        )
                        db.commit()
                    except json.JSONDecodeError as e:
                        logging.error(
                            f"Ollama JSON parse error: {e}. Raw response: {ollama_output_str[:500]}"
                        )
                        continue
                except Exception as e:
                    logging.error(f"Ollama processing error: {e}")
                    continue

            for item in ollama_output:
                if not all(
                    key in item
                    for key in [
                        "topic",
                        "summary",
                        "sorted_headlines",
                        "local_impact",
                        "global_impact",
                        "relevance_rating",
                        "other_ratings",
                    ]
                ):
                    logging.warning(f"Invalid Ollama output structure: {item}")
                    continue
                ollama_results.append(item)

        # Insert into ollama_analysis
        for result in ollama_results:
            if result["relevance_rating"] < 5:
                result["summary"] = (
                    "Generic summary: Minor or unrelated news with low impact on crypto/business."
                )
            try:
                sql_ollama = """
                    INSERT INTO ollama_analysis 
                    (analysis_id, topic, summary, sorted_headlines, local_impact, global_impact, 
                     relevance_rating, other_ratings, ollama_model, processing_time_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                proc_time_ms = int(
                    (time.perf_counter() - start_time) * 1000 / len(ollama_results)
                    if ollama_results
                    else 1
                )
                cursor.execute(
                    sql_ollama,
                    (
                        analysis_id,
                        result["topic"][:255],
                        result["summary"],
                        json.dumps(result["sorted_headlines"]),
                        min(result["local_impact"], 10),
                        min(result["global_impact"], 10),
                        min(result["relevance_rating"], 10),
                        json.dumps(result.get("other_ratings", {})),
                        ollama_model,
                        proc_time_ms,
                    ),
                )
            except mysql.connector.Error as e:
                logging.error(f"Failed to insert into ollama_analysis: {e}. Result: {result}")
                continue

        db.commit()
        total_ollama_time_ms = int((time.perf_counter() - start_time) * 1000)
        logging.info(f"Ollama processed {len(ollama_results)} topics in {total_ollama_time_ms}ms")

        # --- Generate Advised Stance ---
        top_topics = (
            json.dumps([r["topic"] for r in ollama_results[:5]]) if ollama_results else "[]"
        )
        advised_stance = "Hold"
        explanation = "No specific advice available."
        if ollama_results:
            overall_prompt = """
            Based on these analyzed topics: {0}
            
            Provide an overall advised stance for crypto investors (e.g., 'Buy', 'Hold', 'Sell') with a 1-2 sentence explanation.
            
            Output ONLY in JSON: {{"advised_stance": "Stance", "explanation": "Text"}}
            """
            try:
                prompt = overall_prompt.format(json.dumps(ollama_results))
                response = ollama.generate(model=ollama_model, prompt=prompt)
                overall_output = json.loads(response["response"].strip())
                advised_stance = overall_output.get("advised_stance", "Hold")
                explanation = overall_output.get("explanation", "No specific advice available.")
            except Exception as e:
                logging.error(f"Failed to generate advised stance: {e}")

        # Insert into dashboard_analysis
        sql_dashboard = """
            INSERT INTO dashboard_analysis 
            (analysis_id, overall_sentiment, top_topics, advised_stance, market_context)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(
            sql_dashboard,
            (
                analysis_id,
                round(avg_score, 2) if all_headlines_data else 0,
                top_topics,
                f"{advised_stance}: {explanation}",
                market_context,
            ),
        )
        db.commit()

        # --- Dynamic RSI Calculation ---
        if all_headlines_data:
            # Get average global_impact from ollama_analysis
            cursor.execute(
                "SELECT AVG(global_impact) FROM ollama_analysis WHERE analysis_id = %s AND relevance_rating >= 5",
                (analysis_id,),
            )
            avg_global_impact = float(cursor.fetchone()[0] or 5.0)  # Convert Decimal to float

            # Adjust RSI thresholds
            default_buy_threshold = 30.0
            default_sell_threshold = 70.0
            sentiment_score = float(avg_score)  # Ensure float
            # Adjustment: sentiment_score * 5 + (avg_global_impact - 5) * 2
            adjustment_factor = sentiment_score * 5 + (avg_global_impact - 5) * 2
            adjusted_buy_threshold = max(20.0, min(40.0, default_buy_threshold - adjustment_factor))
            adjusted_sell_threshold = max(
                60.0, min(80.0, default_sell_threshold + adjustment_factor)
            )

            # Placeholder RSI value
            rsi_value = 50.0  # Replace with actual RSI from market data

            sql_rsi = """
                INSERT INTO dynamic_rsi 
                (analysis_id, rsi_value, buy_threshold, sell_threshold, sentiment_score, global_impact, adjustment_factor)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(
                sql_rsi,
                (
                    analysis_id,
                    rsi_value,
                    adjusted_buy_threshold,
                    adjusted_sell_threshold,
                    round(sentiment_score, 2),
                    round(avg_global_impact, 2),
                    round(adjustment_factor, 2),
                ),
            )
            db.commit()
            logging.info(
                f"Inserted dynamic RSI for analysis_id={analysis_id}: RSI={rsi_value}, Buy={adjusted_buy_threshold}, Sell={adjusted_sell_threshold}"
            )

    # --- Sentiment Index ---
    sql_index = """
        SELECT 
            DATE(h.created_at) AS analysis_day,
            a.market_context,
            COUNT(*) AS headlines_analyzed,
            AVG(h.sentiment_score) AS avg_sentiment_score,
            SUM(h.sentiment_score * h.confidence)/SUM(h.confidence) AS weighted_sentiment_index
        FROM sentiment_history h
        JOIN sentiment_analysis a ON h.analysis_id = a.analysis_id
        GROUP BY analysis_day, a.market_context
        ORDER BY analysis_day DESC
    """
    cursor.execute(sql_index)
    rows = cursor.fetchall()
    for row in rows:
        day, context, count, avg_score, weighted_index = row
        sql_upsert = """
            INSERT INTO sentiment_index (analysis_day, market_context, avg_sentiment_score, weighted_sentiment_index, headlines_analyzed, analysis_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                avg_sentiment_score = VALUES(avg_sentiment_score),
                weighted_sentiment_index = VALUES(weighted_sentiment_index),
                headlines_analyzed = VALUES(headlines_analyzed),
                analysis_id = VALUES(analysis_id)
        """
        cursor.execute(sql_upsert, (day, context, avg_score, weighted_index, count, analysis_id))
    db.commit()

    # --- Export all tables to JSON ---
    tables_to_export = [
        "sentiment_history",
        "dashboard_analysis",
        "dynamic_rsi",
        "ollama_analysis",
        "sentiment_analysis",
    ]
    for table in tables_to_export:
        cursor.execute(f"SELECT * FROM {table} WHERE analysis_id = %s", (analysis_id,))
        table_data = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        json_file = os.path.join(output_dir, f"{table}_{analysis_id}.json")
        try:
            with open(json_file, "w", encoding="utf-8") as f:
                json_data = [
                    dict(
                        zip(
                            columns,
                            [
                                (
                                    row[i].isoformat()
                                    if isinstance(row[i], datetime)
                                    else (
                                        float(row[i])
                                        if isinstance(row[i], decimal.Decimal)
                                        else row[i]
                                    )
                                )
                                for i in range(len(row))
                            ],
                        )
                    )
                    for row in table_data
                ]
                json.dump(json_data, f, indent=2, cls=CustomEncoder)
            logging.info(f"Exported {table} data to {json_file}")
        except Exception as e:
            logging.error(f"Failed to export {table} JSON: {e}")

    logging.info(
        f"✅ Terminé : {total_inserted} new headlines, GPU activé, table analysis complète."
    )

    # Sleep for 1 hour
    time.sleep(3590)

cursor.close()
db.close()
