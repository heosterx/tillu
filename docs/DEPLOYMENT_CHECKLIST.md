# TILLU Backend — Deployment Checklist (May 2026)

## Pre-Deployment Testing

### Local Development
- [ ] Install updated dependencies: `pip install --upgrade -r requirements.txt`
- [ ] Run type checking: `mypy app/`
- [ ] Run linter: `ruff check app/`
- [ ] Format code: `black app/`
- [ ] Run tests: `pytest`
- [ ] Test API locally: `uvicorn app.main:app --reload`

### Dependency Compatibility
- [ ] Verify LangChain 0.3 API compatibility with existing chains
- [ ] Test Pydantic 2.10 model validation
- [ ] Verify SQLAlchemy 2.1 ORM operations
- [ ] Test Playwright 1.48 browser automation
- [ ] Verify Torch 2.5 model loading

### Integration Testing
- [ ] Test Supabase 2.5 connection
- [ ] Test Redis 5.2 connection
- [ ] Test OpenAI 1.52 API calls
- [ ] Test Groq 0.9 API calls
- [ ] Test Anthropic 0.42 API calls
- [ ] Test Google Generative AI 0.8 API calls
- [ ] Test Cohere 5.11 API calls

---

## Hugging Face Spaces Deployment

### WebSearch Space
- [ ] Update `deployments/huggingface/websearch-space/Dockerfile`
- [ ] Update `deployments/huggingface/websearch-space/requirements.txt`
- [ ] Trigger rebuild from HF Space settings
- [ ] Monitor build logs (typically 5-10 minutes)
- [ ] Test `/health` endpoint
- [ ] Test `/search` endpoint
- [ ] Test `/scrape` endpoint
- [ ] Test `/intelligence` endpoint

### Daemon Space
- [ ] Update `deployments/huggingface/daemon-space/requirements.txt`
- [ ] Trigger rebuild from HF Space settings
- [ ] Monitor build logs
- [ ] Verify daemon startup
- [ ] Test background job processing

### n8n Engine Space
- [ ] Update `deployments/huggingface/n8n-space/Dockerfile`
- [ ] Update n8n version to 2.20.0
- [ ] Trigger rebuild from HF Space settings
- [ ] Monitor build logs (typically 10-15 minutes)
- [ ] Verify n8n UI loads at https://tillu-ai-tillu-engine.hf.space
- [ ] Test workflow execution
- [ ] Verify webhook connectivity

---

## Render Deployment

### WebSearch Service
- [ ] Update `deployments/render/Dockerfile.websearch`
- [ ] Push changes to git
- [ ] Trigger manual deploy from Render dashboard
- [ ] Monitor deployment logs
- [ ] Test service endpoints

### Gateway Service
- [ ] Update main `Dockerfile`
- [ ] Update `requirements.txt`
- [ ] Push changes to git
- [ ] Trigger manual deploy from Render dashboard
- [ ] Monitor deployment logs
- [ ] Test API endpoints

---

## Fly.io Deployment

### Daemon Service
- [ ] Update `deployments/fly/daemon/requirements.txt`
- [ ] Push changes to git
- [ ] Deploy: `fly deploy`
- [ ] Monitor logs: `fly logs`
- [ ] Verify service health

---

## Post-Deployment Verification

### API Health Checks
- [ ] GET `/health` returns 200
- [ ] GET `/status` returns service info
- [ ] All LLM provider endpoints respond
- [ ] Database connections stable
- [ ] Redis connections stable

### Performance Monitoring
- [ ] Monitor CPU usage (should be stable)
- [ ] Monitor memory usage (should not grow unbounded)
- [ ] Monitor response times (should be <2s for most endpoints)
- [ ] Monitor error rates (should be <1%)

### Integration Verification
- [ ] WebSearch returns results
- [ ] Scraper extracts content correctly
- [ ] LLM chains execute successfully
- [ ] Background jobs process correctly
- [ ] Webhooks trigger properly

### Logging & Monitoring
- [ ] Check application logs for errors
- [ ] Verify Sentry integration (if enabled)
- [ ] Check OpenTelemetry traces
- [ ] Monitor Prometheus metrics

---

## Rollback Plan

If critical issues occur:

### Immediate Rollback
1. Revert git commits
2. Rebuild containers with previous versions
3. Redeploy to all platforms

### Gradual Rollback
1. Disable new version in load balancer
2. Route traffic to previous version
3. Investigate issues
4. Fix and redeploy

### Database Considerations
- No schema changes in this update
- All migrations are backward compatible
- No data migration needed

---

## Known Issues & Workarounds

### Python 3.13 Compatibility
- Some packages may need recompilation
- If build fails, check for C extension compatibility
- Fallback: Use Python 3.12 if critical issues arise

### LangChain 0.3 Breaking Changes
- API changes in chain initialization
- Review chain implementations for compatibility
- Test all chain types before production

### Playwright 1.48 Updates
- Browser automation may behave differently
- Test scraping logic thoroughly
- Monitor for timeout issues

---

## Monitoring Commands

### Local Testing
```bash
# Install dependencies
pip install --upgrade -r requirements.txt

# Run tests
pytest -v

# Type checking
mypy app/

# Linting
ruff check app/

# Format
black app/

# Run locally
uvicorn app.main:app --reload
```

### Render Monitoring
```bash
# View logs
curl https://api.render.com/v1/services/{service-id}/logs

# Check deployment status
curl https://api.render.com/v1/services/{service-id}
```

### Fly.io Monitoring
```bash
# View logs
fly logs

# Check status
fly status

# SSH into instance
fly ssh console
```

### HF Spaces Monitoring
- Check Space settings → Logs
- Monitor build progress
- Check runtime logs

---

## Success Criteria

✅ All services deploy successfully
✅ All health checks pass
✅ API response times <2s
✅ Error rate <1%
✅ No memory leaks detected
✅ All integrations working
✅ Logs show no critical errors
✅ Performance metrics stable

---

## Support & Escalation

### If Issues Occur
1. Check logs first
2. Verify all dependencies installed
3. Test individual components
4. Check API provider status
5. Review recent changes
6. Escalate to team if unresolved

### Contact
- Team Slack: #tillu-backend
- On-call: Check rotation schedule
- Emergency: Page on-call engineer

---

**Last Updated**: May 10, 2026
**Status**: Ready for deployment
**Estimated Deployment Time**: 30-45 minutes (all platforms)
