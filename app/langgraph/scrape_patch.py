    async def _scrape_node(self, state: ResearchState) -> ResearchState:
        self.logger.info("Research: Scraping phase", urls=len(state["search_results"]))
        from app.tools.search_tools import ScrapePageTool
        scraper = ScrapePageTool()
        scraped = []
        import asyncio
        tasks = [scraper.execute(r["url"]) for r in state["search_results"][:6] if r.get("url")]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r, res in zip(state["search_results"][:6], results):
            if isinstance(res, dict) and res.get("success"):
                text = res.get("text", "")[:2000]
                summary = text if len(text) < 300 else text[:500]
            else:
                summary = r.get("snippet", "")
            scraped.append({
                "url": r.get("url"),
                "title": r.get("title"),
                "summary": summary,
                "source": r.get("source"),
                "angle": r.get("angle"),
                "word_count": len(summary.split()),
            })
        state["scraped_content"] = scraped
        state["status"] = "scrape_complete"
        self.logger.info(f"Scraped {len(scraped)} pages")
        return state
