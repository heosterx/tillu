"""
Google OAuth2 token helper.

Exchanges the stored refresh token for a short-lived access token.
Access tokens expire after 1 hour — this helper caches and auto-refreshes.
"""
import time
import httpx
from typing import Optional
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("google_auth")

TOKEN_URL = "https://oauth2.googleapis.com/token"

# Simple in-process cache: (access_token, expires_at)
_cache: tuple[Optional[str], float] = (None, 0.0)


async def get_access_token() -> Optional[str]:
    """
    Return a valid Google OAuth2 access token.
    Refreshes automatically when expired (or within 60s of expiry).
    Returns None if credentials are not configured.
    """
    global _cache

    # Check required config
    if not all([
        settings.google_client_id,
        settings.google_client_secret,
        settings.gmail_refresh_token,
    ]):
        logger.warning(
            "Google OAuth not configured — set GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET, GMAIL_REFRESH_TOKEN"
        )
        return None

    access_token, expires_at = _cache

    # Return cached token if still valid (with 60s buffer)
    if access_token and time.time() < expires_at - 60:
        return access_token

    # Refresh
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type":    "refresh_token",
                    "refresh_token": settings.gmail_refresh_token,
                    "client_id":     settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        access_token = data["access_token"]
        expires_in   = data.get("expires_in", 3600)
        _cache = (access_token, time.time() + expires_in)

        logger.debug("Google access token refreshed")
        return access_token

    except Exception as e:
        logger.error(f"Failed to refresh Google access token: {e}")
        return None
