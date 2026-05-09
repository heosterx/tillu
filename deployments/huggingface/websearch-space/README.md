---
title: TILLU WebSearch
emoji: 🔍
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
license: mit
short_description: Web search + scrape, Hindi/English
---

# TILLU WebSearch Service

Unified web search and scraping service for the TILLU AI system.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/status` | Service stats |
| `POST` | `/search` | Web search (Brave → DuckDuckGo fallback) |
| `POST` | `/scrape` | Scrape a URL with headless Chromium |
| `POST` | `/search-and-scrape` | Search + scrape top results in one call |

## Usage

```bash
# Search
curl -X POST https://tillu-ai-tillu-websearch.hf.space/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Delhi weather today", "lang": "auto", "max_results": 5}'

# Search + scrape
curl -X POST https://tillu-ai-tillu-websearch.hf.space/search-and-scrape \
  -H "Content-Type: application/json" \
  -d '{"query": "latest news India", "lang": "hi", "scrape_top": 3}'
```

## Space Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `BRAVE_API_KEY` | Optional | Brave Search API key — falls back to DuckDuckGo without it |

## Language Support

- Auto-detects Hindi vs English from Devanagari Unicode
- Hindi queries use `hl=hi&gl=in` locale params
- Cross-lingual search supported
