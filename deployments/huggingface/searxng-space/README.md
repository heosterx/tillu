---
title: TILLU SearXNG
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
license: mit
short_description: SearXNG meta-search engine with JSON API for TILLU AI
---

# TILLU SearXNG

Private SearXNG meta-search engine. Aggregates Google, Bing, DuckDuckGo, Wikipedia, Reddit, GitHub, ArXiv and more.

## JSON API

```bash
curl "https://tillu-ai-tillu-searxng.hf.space/search?q=AI+news&format=json&language=en"
```

### Parameters

| Param | Values | Description |
|-------|--------|-------------|
| `q` | string | Search query |
| `format` | `json` | Must be `json` for API use |
| `language` | `en`, `hi`, `all` | Result language |
| `categories` | `general`, `news`, `science`, `it` | Category filter |
| `engines` | `google,bing,duckduckgo` | Comma-separated engines |
| `pageno` | integer | Page number (default 1) |

## Deployment

1. Create new HuggingFace Space: `tillu-ai-tillu-searxng`
2. SDK: Docker
3. Copy files:
   - `Dockerfile`
   - `settings.yml`
   - `README.md`

## Space Secrets

None required — fully open meta-search.
