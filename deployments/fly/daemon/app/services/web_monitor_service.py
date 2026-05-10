"""
Web Monitoring Service
Playwright-based web scraping and change detection
"""
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config import settings
from app.utils.database import db
from app.utils.logging import get_logger

logger = get_logger("web_monitor_service")


class WebMonitorService:
    """
    Web monitoring and change detection service
    Uses Playwright for rendering and extraction
    """
    
    def __init__(self):
        self.playwright_available = False
        try:
            from playwright.async_api import async_playwright
            self.playwright_available = True
        except ImportError:
            logger.warning("Playwright not available - using fallback mode")
    
    async def check_all_monitors(self) -> List[Dict[str, Any]]:
        """
        Check all active web monitors for changes
        Returns list of monitors with detected changes
        """
        changes = []
        
        monitors = await db.fetch_many(
            "web_monitors",
            filters={"is_active": True},
            limit=20
        )
        
        for monitor in monitors:
            try:
                result = await self._check_monitor(monitor)
                
                if result.get("changed"):
                    changes.append(result)
                    
            except Exception as e:
                logger.error(f"Monitor check error for {monitor.get('url')}: {e}")
                continue
        
        logger.info(f"Detected {len(changes)} web changes")
        return changes
    
    async def _check_monitor(self, monitor: Dict) -> Dict[str, Any]:
        """Check single monitor for changes"""
        url = monitor.get("url", "")
        selector = monitor.get("css_selector")
        last_hash = monitor.get("last_content_hash", "")
        
        # Extract current content
        content = await self._extract_content(url, selector)
        
        if not content:
            return {"changed": False, "monitor_id": monitor.get("id")}
        
        # Calculate hash
        current_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Check for change
        changed = last_hash and last_hash != current_hash
        
        # Update monitor record
        await db.update(
            "web_monitors",
            {
                "last_content_hash": current_hash,
                "last_checked": datetime.now().isoformat(),
                "last_changed": datetime.now().isoformat() if changed else monitor.get("last_changed")
            },
            {"id": monitor.get("id")}
        )
        
        return {
            "changed": changed,
            "monitor_id": monitor.get("id"),
            "url": url,
            "title": monitor.get("name"),
            "content_preview": content[:200] if changed else None
        }
    
    async def _extract_content(self, url: str, selector: Optional[str] = None) -> Optional[str]:
        """
        Extract content from URL using Playwright or fallback
        """
        if self.playwright_available:
            return await self._extract_with_playwright(url, selector)
        else:
            return await self._extract_with_requests(url, selector)
    
    async def _extract_with_playwright(self, url: str, selector: Optional[str] = None) -> Optional[str]:
        """Extract content using Playwright"""
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                if selector:
                    # Extract specific element
                    element = await page.query_selector(selector)
                    content = await element.inner_text() if element else None
                else:
                    # Extract page title + main content
                    title = await page.title()
                    content = await page.content()
                    content = f"{title}\n{content[:5000]}"  # Truncate
                
                await browser.close()
                return content
                
        except Exception as e:
            logger.error(f"Playwright extraction error: {e}")
            return await self._extract_with_requests(url, selector)
    
    async def _extract_with_requests(self, url: str, selector: Optional[str] = None) -> Optional[str]:
        """Fallback: Extract with simple HTTP request"""
        try:
            import httpx
            from bs4 import BeautifulSoup
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15.0, follow_redirects=True)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Get text
                    text = soup.get_text(separator='\n', strip=True)
                    
                    # Clean up
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    content = '\n'.join(lines[:100])  # First 100 lines
                    
                    # Include title
                    title = soup.find('title')
                    if title:
                        content = f"{title.get_text()}\n{content}"
                    
                    return content[:5000]  # Limit size
                    
        except Exception as e:
            logger.error(f"Request extraction error: {e}")
        
        return None
    
    async def add_monitor(
        self,
        user_id: str,
        name: str,
        url: str,
        css_selector: Optional[str] = None,
        check_interval: int = 30,
        urgency: int = 5
    ) -> Dict[str, Any]:
        """Add new web monitor"""
        monitor = {
            "user_id": user_id,
            "name": name,
            "url": url,
            "css_selector": css_selector,
            "check_interval_minutes": check_interval,
            "urgency": urgency,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }
        
        result = await db.insert("web_monitors", monitor)
        
        # Do initial check to get baseline
        await self._check_monitor({**monitor, "id": result[0].get("id") if result else None})
        
        return {
            "success": True,
            "monitor_id": result[0].get("id") if result else None,
            "name": name,
            "url": url
        }
    
    async def get_monitors_summary(self, user_id: str = None) -> Dict[str, Any]:
        """Get summary of all monitors"""
        filters = {}
        if user_id:
            filters["user_id"] = user_id
        
        monitors = await db.fetch_many(
            "web_monitors",
            filters=filters,
            limit=50
        )
        
        active = sum(1 for m in monitors if m.get("is_active"))
        recently_changed = sum(
            1 for m in monitors
            if m.get("last_changed") and
            (datetime.now() - datetime.fromisoformat(m.get("last_changed").replace('Z', '+00:00'))).days < 1
        )
        
        return {
            "total_monitors": len(monitors),
            "active": active,
            "recently_changed": recently_changed,
            "monitors": [
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "url": m.get("url"),
                    "is_active": m.get("is_active"),
                    "last_checked": m.get("last_checked"),
                    "last_changed": m.get("last_changed")
                }
                for m in monitors
            ]
        }


# Singleton
web_monitor_service = WebMonitorService()
