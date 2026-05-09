"""
Financial Monitoring Service
CoinGecko for crypto, Yahoo Finance for stocks
"""
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config import settings
from app.utils.database import db
from app.utils.logging import get_logger

logger = get_logger("financial_service")


class FinancialService:
    """
    Financial monitoring and alerting service
    Tracks cryptocurrencies and stocks
    """
    
    COINGECKO_API = "https://api.coingecko.com/api/v3"
    YAHOO_FINANCE_API = "https://query1.finance.yahoo.com/v8/finance/chart"
    
    async def update_all_prices(self) -> List[Dict[str, Any]]:
        """
        Update prices for all tracked assets
        Returns list of updated assets
        """
        updated = []
        
        # Get all tracked assets
        assets = await db.fetch_many(
            "financial_tracking",
            filters={"is_active": True},
            limit=50
        )
        
        for asset in assets:
            try:
                if asset.get("asset_type") == "crypto":
                    price_data = await self._get_crypto_price(asset.get("symbol", ""))
                else:
                    price_data = await self._get_stock_price(asset.get("symbol", ""))
                
                if price_data:
                    # Check threshold
                    alert = self._check_threshold(asset, price_data)
                    
                    # Update in database
                    await db.update(
                        "financial_tracking",
                        {
                            "current_price": price_data["price"],
                            "last_updated": datetime.now().isoformat(),
                            "price_change_24h": price_data.get("change_24h", 0),
                            "alert_triggered": alert
                        },
                        {"id": asset.get("id")}
                    )
                    
                    updated.append({
                        "symbol": asset.get("symbol"),
                        "price": price_data["price"],
                        "alert": alert
                    })
                    
            except Exception as e:
                logger.error(f"Price update error for {asset.get('symbol')}: {e}")
                continue
        
        logger.info(f"Updated {len(updated)} asset prices")
        return updated
    
    async def _get_crypto_price(self, symbol: str) -> Optional[Dict]:
        """Get cryptocurrency price from CoinGecko"""
        try:
            # Convert symbol to CoinGecko ID (simplified mapping)
            symbol_map = {
                "BTC": "bitcoin",
                "ETH": "ethereum",
                "SOL": "solana",
                "ADA": "cardano",
                "DOT": "polkadot",
                "LINK": "chainlink",
                "MATIC": "matic-network",
                "AVAX": "avalanche-2",
            }
            
            coin_id = symbol_map.get(symbol.upper(), symbol.lower())
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.COINGECKO_API}/simple/price",
                    params={
                        "ids": coin_id,
                        "vs_currencies": "usd",
                        "include_24hr_change": "true"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    coin_data = data.get(coin_id, {})
                    
                    return {
                        "price": coin_data.get("usd", 0),
                        "change_24h": coin_data.get("usd_24h_change", 0)
                    }
                    
        except Exception as e:
            logger.error(f"CoinGecko API error: {e}")
        
        return None
    
    async def _get_stock_price(self, symbol: str) -> Optional[Dict]:
        """Get stock price from Yahoo Finance"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.YAHOO_FINANCE_API}/{symbol}",
                    params={"interval": "1d", "range": "1d"},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("chart", {}).get("result", [{}])[0]
                    meta = result.get("meta", {})
                    
                    price = meta.get("regularMarketPrice", 0)
                    prev_close = meta.get("chartPreviousClose", 0)
                    
                    change_pct = 0
                    if prev_close > 0:
                        change_pct = ((price - prev_close) / prev_close) * 100
                    
                    return {
                        "price": price,
                        "change_24h": change_pct
                    }
                    
        except Exception as e:
            logger.error(f"Yahoo Finance API error: {e}")
        
        return None
    
    def _check_threshold(self, asset: Dict, price_data: Dict) -> bool:
        """Check if price crossed alert threshold"""
        threshold = asset.get("alert_threshold", 5.0)
        change = abs(price_data.get("change_24h", 0))
        
        return change >= threshold
    
    async def add_tracker(
        self,
        user_id: str,
        symbol: str,
        asset_type: str = "crypto",
        alert_threshold: float = 5.0
    ) -> Dict[str, Any]:
        """Add new financial tracker"""
        tracker = {
            "user_id": user_id,
            "symbol": symbol.upper(),
            "asset_type": asset_type,
            "alert_threshold": alert_threshold,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }
        
        result = await db.insert("financial_tracking", tracker)
        
        return {
            "success": True,
            "tracker_id": result[0].get("id") if result else None,
            "symbol": symbol.upper()
        }
    
    async def get_market_summary(self) -> Dict[str, Any]:
        """Get market summary for dashboard"""
        try:
            # Get top crypto from CoinGecko
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.COINGECKO_API}/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "order": "market_cap_desc",
                        "per_page": "5",
                        "page": "1"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    coins = response.json()
                    
                    return {
                        "success": True,
                        "top_cryptos": [
                            {
                                "symbol": c.get("symbol", "").upper(),
                                "name": c.get("name"),
                                "price": c.get("current_price"),
                                "change_24h": c.get("price_change_percentage_24h"),
                                "market_cap": c.get("market_cap")
                            }
                            for c in coins
                        ],
                        "timestamp": datetime.now().isoformat()
                    }
                    
        except Exception as e:
            logger.error(f"Market summary error: {e}")
        
        return {"success": False, "error": "Failed to fetch market data"}


# Singleton
financial_service = FinancialService()
