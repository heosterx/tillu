# TILLU SearXNG — HuggingFace Space
# ====================================
# Official SearXNG image configured for JSON API access
# Port 7860 required by HF Spaces

FROM searxng/searxng:latest

# HF Spaces requires UID 1000
# SearXNG image already runs as non-root (searxng user)
# We just need to copy config and expose the right port

# Copy our custom settings
COPY settings.yml /etc/searxng/settings.yml

# HF Spaces port
EXPOSE 7860

# Override the default port via env
ENV SEARXNG_PORT=7860
ENV SEARXNG_BIND_ADDRESS=0.0.0.0

# SearXNG reads SEARXNG_SETTINGS_PATH for config location
ENV SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -qO- http://localhost:7860/healthz || exit 1
