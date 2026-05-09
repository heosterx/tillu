"""
News Intelligence Service
RSS feeds, news APIs, article aggregation
"""
import httpx
import feedparser
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.config import settings
from app.utils.database import db
from app.utils.logging import get_logger
from app.transformers.embeddings import embedding_generator

logger = get_logger("news_service")


class NewsService:
    """
    News intelligence aggregation service
    Fetches from RSS feeds, NewsAPI, stores in news_articles table
    """
    
    # Default news sources
    RSS_FEEDS = [
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://rss.cnn.com/rss/edition.rss",
        "https://feeds.reuters.com/reuters/technologyNews",
        "https://feeds.reuters.com/reuters/businessNews",
    ]
    
    def __init__(self):
        self.newsapi_key = settings.newsapi_key
    
    async def fetch_all(self, user_id: str = None, topic: str = None) -> List[Dict[str, Any]]:
        """
        Fetch news from all sources
        
        Args:
            user_id: User to associate articles with
            topic: Optional topic filter
            
        Returns:
            List of news articles stored
        """
        articles = []
        
        # Fetch from RSS feeds
        rss_articles = await self._fetch_rss(user_id, topic)
        articles.extend(rss_articles)
        
        # Fetch from NewsAPI if key available
        if self.newsapi_key:
            api_articles = await self._fetch_newsapi(user_id, topic)
            articles.extend(api_articles)
        
        logger.info(f"Fetched {len(articles)} news articles")
        return articles
    
    async def _fetch_rss(self, user_id: str = None, topic: str = None) -> List[Dict]:
        """Fetch and parse RSS feeds"""
        articles = []
        
        for feed_url in self.RSS_FEEDS:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(feed_url, timeout=15.0)
                    
                    if response.status_code == 200:
                        # Parse RSS
                        feed = feedparser.parse(response.text)
                        
                        for entry in feed.entries[:5]:  # Top 5 per feed
                            # Check if already exists
                            existing = await db.fetch_one(
                                "news_articles",
                                {"url": entry.link}
                            )
                            
                            if existing:
                                continue
                            
                            # Calculate urgency score
                            urgency = self._calculate_urgency(entry)
                            
                            article = {
                                "user_id": user_id,
                                "title": entry.get("title", "Untitled"),
                                "url": entry.link,
                                "source": feed.feed.get("title", "Unknown"),
                                "summary": entry.get("summary", "")[:500],
                                "fetched_at": datetime.now().isoformat(),
                                "urgency_score": urgency,
                                "sentiment": "neutral",
                                "embedding": None  # Will generate below
                            }
                            
                            # Generate embedding for semantic search
                            try:
                                embedding = await embedding_generator.generate(
                                    article["title"] + " " + article["summary"]
                                )
                                article["embedding"] = embedding
                            except Exception as e:
                                logger.warning(f"Failed to generate embedding: {e}")
                            
                            # Store to database
                            result = await db.insert("news_articles", article)
                            
                            if result:
                                articles.append(article)
                                
            except Exception as e:
                logger.error(f"RSS fetch error for {feed_url}: {e}")
                continue
        
        return articles
    
    async def _fetch_newsapi(self, user_id: str = None, topic: str = None) -> List[Dict]:
        """Fetch from NewsAPI"""
        articles = []
        
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "apiKey": self.newsapi_key,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 20
                }
                
                if topic:
                    params["q"] = topic
                else:
                    params["category"] = "technology"
                
                response = await client.get(
                    "https://newsapi.org/v2/top-headlines",
                    params=params,
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for item in data.get("articles", []):
                        # Check if exists
                        existing = await db.fetch_one(
                            "news_articles",
                            {"url": item.get("url")}
                        )
                        
                        if existing:
                            continue
                        
                        article = {
                            "user_id": user_id,
                            "title": item.get("title", "Untitled"),
                            "url": item.get("url"),
                            "source": item.get("source", {}).get("name", "NewsAPI"),
                            "summary": item.get("description", "")[:500],
                            "fetched_at": datetime.now().isoformat(),
                            "urgency_score": 5,  # Default
                            "sentiment": "neutral",
                            "embedding": None
                        }
                        
                        # Generate embedding
                        try:
                            embedding = await embedding_generator.generate(
                                article["title"] + " " + article["summary"]
                            )
                            article["embedding"] = embedding
                        except:
                            pass
                        
                        result = await db.insert("news_articles", article)
                        
                        if result:
                            articles.append(article)
                            
        except Exception as e:
            logger.error(f"NewsAPI fetch error: {e}")
        
        return articles
    
    def _calculate_urgency(self, entry) -> int:
        """Calculate urgency score 1-10 based on keywords"""
        title = entry.get("title", "").lower()
        summary = entry.get("summary", "").lower()
        text = title + " " + summary
        
        urgency_keywords = {
            10: ["breaking", "urgent", "alert", "emergency", "crisis"],
            8: ["important", "major", "critical", "significant"],
            6: ["update", "announced", "launched", "released"],
        }
        
        for score, keywords in urgency_keywords.items():
            if any(kw in text for kw in keywords):
                return score
        
        return 3  # Default low urgency
    
    async def get_personalized_feed(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        Get personalized news feed for user
        Based on interests and recent interactions
        """
        # Get user interests from knowledge base
        interests = await db.fetch_many(
            "knowledge_base",
            filters={"user_id": user_id, "category": "interest"},
            limit=20
        )
        
        interest_keywords = [i.get("content", "").lower() for i in interests]
        
        # Fetch recent articles
        articles = await db.fetch_many(
            "news_articles",
            filters={},
            order_by="fetched_at",
            ascending=False,
            limit=100
        )
        
        # Score articles based on relevance to interests
        scored = []
        for article in articles:
            title = article.get("title", "").lower()
            score = 0
            
            for keyword in interest_keywords:
                if keyword in title:
                    score += 1
            
            # Boost by urgency
            score += article.get("urgency_score", 0) * 0.1
            
            scored.append((score, article))
        
        # Sort by score and return top
        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:limit]]


# Singleton instance
news_service = NewsService()
