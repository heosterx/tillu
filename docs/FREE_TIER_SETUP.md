# Free Tier LLM Setup Guide

## Quick Start

All LLM providers are now **free tier only**. No paid API keys required.

## Required API Keys (All Free)

### 1. Groq (Fastest)
- **URL**: https://console.groq.com
- **Limit**: 14.4k tokens/min
- **Setup**: Sign up → Create API key → Add to `.env`
```
GROQ_API_KEY=gsk_...
```

### 2. Together AI (Best Reasoning)
- **URL**: https://www.together.ai
- **Models**: 
  - Meta Llama 3.3 70B (free)
  - DeepSeek R1 (free)
  - FLUX.1 image generation (free)
- **Setup**: Sign up → Create API key → Add to `.env`
```
TOGETHER_API_KEY=tgp_v1_...
```

### 3. Cerebras (Deep Reasoning)
- **URL**: https://www.cerebras.ai
- **Limit**: ~500 requests/day
- **Setup**: Sign up → Create API key → Add to `.env`
```
CEREBRAS_API_KEY=csk_...
```

### 4. HuggingFace (Optional, 13 Free Models)
- **URL**: https://huggingface.co
- **Setup**: Sign up → Create token → Add to `.env`
```
HF_TOKEN=hf_...
```

### 5. Google Gemini (Optional, Multimodal)
- **URL**: https://ai.google.dev
- **Limit**: 1500 requests/day
- **Setup**: Sign up → Create API key → Add to `.env`
```
GOOGLE_API_KEY=AIzaSy...
```

### 6. OpenRouter (Optional, 200+ Models)
- **URL**: https://openrouter.ai
- **Limit**: 200 free requests/day
- **Setup**: Sign up → Create API key → Add to `.env`
```
OPENROUTER_API_KEY=sk-or-v1-...
```

## Environment Setup

Update `.env` with your free API keys:

```bash
# Required (at least one)
GROQ_API_KEY=your_groq_key
TOGETHER_API_KEY=your_together_key

# Optional but recommended
CEREBRAS_API_KEY=your_cerebras_key
HF_TOKEN=your_hf_token
GOOGLE_API_KEY=your_google_key
OPENROUTER_API_KEY=your_openrouter_key

# Remove these (no longer used)
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# COHERE_API_KEY=
```

## Port Binding

✅ Already configured:
- **Host**: `0.0.0.0` (all interfaces)
- **Port**: `8000` (HTTP)

No changes needed.

## Deployment

```bash
# 1. Update .env with free API keys
# 2. Commit changes
git add .
git commit -m "Add free-tier LLM API keys"

# 3. Push to production
git push origin main

# 4. Monitor startup logs
# Should see: "Available LLM providers: groq, together, cerebras, ..."
```

## Model Selection by Task

| Task | Primary | Secondary | Tertiary |
|------|---------|-----------|----------|
| Quick Chat | Groq 8B | Together Llama 3.3 | HF Gemma |
| Quality Chat | Groq 70B | Together Llama 3.3 | Cerebras |
| Deep Reasoning | Together DeepSeek-R1 | Cerebras | Groq 70B |
| Coding | Together Llama 3.3 | HF Qwen-Coder | Groq 70B |
| Image Generation | Together FLUX.1 | - | - |
| Multimodal | Google Gemini | - | - |

## Troubleshooting

### "No LLM provider configured"
- Add at least one API key to `.env`
- Restart application

### "Provider validation failed"
- Check API keys are valid
- Verify environment variables are loaded
- Check logs for specific provider errors

### Slow responses
- Groq is fastest (use for quick_chat)
- Together AI is balanced (use for quality_chat)
- Cerebras is slowest but best for reasoning

## Cost Breakdown

| Provider | Cost | Limit |
|----------|------|-------|
| Groq | $0 | 14.4k tok/min |
| Together AI | $0 | Generous free |
| Cerebras | $0 | ~500 req/day |
| HuggingFace | $0 | Unlimited |
| Google Gemini | $0 | 1500 req/day |
| OpenRouter | $0 | 200 req/day |

**Total Cost**: $0/month

## Next Steps

1. Sign up for free API keys (5 minutes each)
2. Add keys to `.env`
3. Deploy to production
4. Monitor logs for provider selection
5. Enjoy free LLM inference!

## Support

- Groq: https://console.groq.com/docs
- Together AI: https://docs.together.ai
- Cerebras: https://docs.cerebras.ai
- HuggingFace: https://huggingface.co/docs
- Google: https://ai.google.dev/docs
- OpenRouter: https://openrouter.ai/docs
