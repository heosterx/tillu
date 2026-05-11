# Cloudflare Workers AI Integration

## Overview

Cloudflare Workers AI provides free access to powerful language models through their edge network. This integration adds Cloudflare as a fallback provider in the TILLU LLM router.

## Models Available

### Free Tier Models
- **@cf/meta/llama-2-7b-chat-int8** - Fast, lightweight chat model
- **@cf/mistral/mistral-7b-instruct-v0.1** - Quality reasoning model

## Setup Instructions

### 1. Create Cloudflare Account
- Visit: https://dash.cloudflare.com
- Sign up for free account
- Verify email

### 2. Get API Credentials

**Account ID:**
1. Go to https://dash.cloudflare.com
2. Click on your account name (bottom left)
3. Copy "Account ID"

**API Token:**
1. Go to https://dash.cloudflare.com/profile/api-tokens
2. Click "Create Token"
3. Use template: "Edit Cloudflare Workers"
4. Grant permissions:
   - Account > Workers AI > Edit
   - Account > Account Settings > Read
5. Copy the token

### 3. Update Environment Variables

Add to `.env`:
```bash
CLOUDFLARE_API_TOKEN=your_api_token_here
CLOUDFLARE_ACCOUNT_ID=your_account_id_here
```

### 4. Verify Integration

```bash
# Check if Cloudflare is detected
python scripts/verify_models_static.py

# Should show:
# Cloudflare: 3 models
#   fast    → @cf/meta/llama-2-7b-chat-int8
#   quality → @cf/mistral/mistral-7b-instruct-v0.1
#   coding  → @cf/mistral/mistral-7b-instruct-v0.1
```

## Model Specifications

### Llama 2 7B Chat (Int8)
- **Model ID**: `@cf/meta/llama-2-7b-chat-int8`
- **Type**: Fast, lightweight chat
- **Use Case**: Quick responses, small payloads
- **Latency**: ~500-800ms
- **Context**: 4K tokens

### Mistral 7B Instruct v0.1
- **Model ID**: `@cf/mistral/mistral-7b-instruct-v0.1`
- **Type**: Quality reasoning
- **Use Case**: Balanced quality and speed
- **Latency**: ~800-1200ms
- **Context**: 8K tokens

## Task Routing

Cloudflare is integrated into the fallback chain:

```
quick_chat:
  1. Groq (fastest)
  2. Together AI
  3. Cloudflare (Llama 2)
  4. HuggingFace

quality_chat:
  1. Groq (70B)
  2. Together AI (70B)
  3. Cloudflare (Mistral)
  4. HuggingFace

coding:
  1. Together AI
  2. HuggingFace
  3. Groq
```

## API Endpoint

```
POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}

Headers:
  Authorization: Bearer {api_token}
  Content-Type: application/json

Body:
{
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "max_tokens": 1024,
  "temperature": 0.75
}
```

## Pricing

**Free Tier:**
- 10,000 requests/day
- No credit card required
- Unlimited model access

**Paid Tier:**
- $0.50 per 1M tokens
- Higher rate limits
- Priority support

## Limitations

- Max 10,000 requests/day (free tier)
- Max 2048 tokens per request
- No streaming support
- Rate limited to 100 req/min

## Testing

### Test Cloudflare Integration

```python
import asyncio
from app.providers.llm_router import invoke

async def test_cloudflare():
    result = await invoke(
        messages=[{"role": "user", "content": "Hello, how are you?"}],
        task="quick_chat",
        provider_override="cloudflare",
        model_override="@cf/meta/llama-2-7b-chat-int8"
    )
    print(f"Response: {result['content']}")
    print(f"Latency: {result['latency_ms']}ms")

asyncio.run(test_cloudflare())
```

## Troubleshooting

### "Invalid API Token"
- Verify token is correct
- Check token hasn't expired
- Regenerate token if needed

### "Account ID not found"
- Verify account ID format (usually 32 hex characters)
- Check you're using correct account

### "Rate limit exceeded"
- Free tier: 10,000 requests/day
- Wait until next day or upgrade to paid
- Implement request queuing

### "Model not found"
- Verify model ID is correct
- Check Cloudflare Workers AI availability in your region
- Try alternative model

## Monitoring

Monitor Cloudflare usage:
1. Go to https://dash.cloudflare.com
2. Navigate to Workers > AI
3. View request metrics and usage

## Best Practices

1. **Use as Fallback**: Cloudflare should be fallback, not primary
2. **Monitor Quota**: Track daily request usage
3. **Batch Requests**: Group requests when possible
4. **Cache Responses**: Implement response caching
5. **Error Handling**: Gracefully handle rate limits

## Comparison with Other Providers

| Provider | Speed | Quality | Cost | Limit |
|----------|-------|---------|------|-------|
| Groq | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Free | 14.4k tok/min |
| Cloudflare | ⭐⭐⭐ | ⭐⭐⭐ | Free | 10k req/day |
| Together AI | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Free | Generous |
| Cerebras | ⭐⭐ | ⭐⭐⭐⭐⭐ | Free | 500 req/day |

## Next Steps

1. ✅ Get API credentials
2. ✅ Add to `.env`
3. ✅ Test integration
4. ✅ Monitor usage
5. ✅ Optimize routing

## Resources

- Cloudflare Workers AI: https://developers.cloudflare.com/workers-ai/
- API Documentation: https://developers.cloudflare.com/workers-ai/platform/api/
- Models Available: https://developers.cloudflare.com/workers-ai/models/
- Pricing: https://developers.cloudflare.com/workers-ai/platform/pricing/

## Support

For issues:
1. Check Cloudflare status: https://www.cloudflarestatus.com
2. Review API docs: https://developers.cloudflare.com/workers-ai/
3. Check router logs for error details
4. Verify credentials are correct
