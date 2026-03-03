# LongVue OSI

## Real-Time Strategic Intelligence & OSINT Engine

Version: 0.1 - March 2026  
Author: NicolasFromBelgium  
License: MIT

---

## Overview

LongVue OSI is an open-source Python system designed to transform open-source information into structured, actionable intelligence.

It combines:

- Ethical multi-source crawling
- Data structuring into traceable information capsules
- Local storage (JSON / CSV / Vector DB)
- Local LLM analysis via Ollama
- Probabilistic scenario generation

Goal: Provide long-term strategic visibility on geopolitical, economic and societal events with full traceability.

---

## Problem It Solves

- Information is fragmented and unstructured
- Analysis is often biased or outdated
- No open-source pipeline that combines OSINT collection + structuring + local prediction

LongVue OSI builds a modular and scalable intelligence pipeline.

---

## Architecture

### Data Collection

- OSINT sources configurable via config.yaml
- Tools: BeautifulSoup, Selenium fallback
- Ethical scraping:
  - Respect robots.txt
  - Request delays
  - Custom user-agent

Features:
- Extract title, date, content, URL
- Detect PDFs and public reports
- Basic pre-classification of topics

---

### Data Structuring

Each document is converted into a structured JSON capsule:

{
  "id": "uuid",
  "source": "example_source",
  "url": "https://...",
  "title": "Title",
  "publish_date": "2026-03-03",
  "raw_text": "Full content",
  "metadata": {
    "location": ["Paris"],
    "topics": ["economy"],
    "impact_local": 7,
    "impact_global": 4
  }
}

Storage:
- JSON
- CSV
- ChromaDB for semantic search

---

### Analysis & Prediction

- Local inference using Ollama
- Supported models: Llama, Gemma, etc.
- Scenario modeling with probabilistic scoring
- Automatic updates when new events are ingested

---

### Output

- Dashboard (Streamlit / Gradio)
- REST API
- Data export

---

## Development

Project follows Test Driven Development:

- tests/unit/
- tests/integration/
- Continuous Integration:
  - Lint
  - Type checking
  - Automated tests on push / PR

---

## Use Cases

- Strategic intelligence monitoring
- Macro-economic analysis
- OSINT research
- AI-based hypothesis generation

---

## Philosophy

- Open Source
- Privacy-first
- Ethical scraping
- Transparent data pipeline
- Fully traceable analysis

LongVue OSI is a modular intelligence engine built for research and long-term insight.

Contributions welcome via fork and pull request.
Issues tracked on GitHub.
