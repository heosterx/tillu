---
title: TILLU WebSearch
emoji: 🔍
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
license: mit
short_description: JARVIS-grade search + scrape + intelligence
---

# TILLU WebSearch v2

JARVIS-grade unified web search, scraping, and AI intelligence service.

## Search Chain (automatic fallback)

1. **SearXNG** (primary) - meta-search: Google, Bing, DDG, Wikipedia, Reddit, GitHub, ArXiv
2. **DuckDuckGo JSON** (fallback) - instant answers
3. **DuckDuckGo HTML** (fallback) - full HTML scrape
4. **Google Lite** (last resort)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Liveness probe |
| GET | /status | Engine health + stats |
| POST | /search | Web search with fallback chain |
| POST | /scrape | Playwright headless scrape |
| POST | /search-and-scrape | Search + scrape top-N |
| POST | /intelligence | **JARVIS mode**: search + scrape + AI summary |

## Deployment

1. Create new HuggingFace Space: `tillu-ai-tillu-websearch`
2. SDK: Docker
3. Copy files:
   - `Dockerfile`
   - `main.py`
   - `requirements.txt`
   - `README.md`
4. Configure Space Secrets:

## Space Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| SEARXNG_URL | Recommended | `https://tillu-ai-tillu-searxng.hf.space` |
| GROQ_API_KEY | Optional | Enables AI summarisation in /intelligence |
