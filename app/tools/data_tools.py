"""
Data Tools - Weather, Financial, etc.
"""
import httpx
from typing import Any, Dict, Optional
from app.config import settings
from app.tools.registry import BaseTool, ToolMetadata, ToolRegistry
from app.utils.logging import get_logger

logger = get_logger("data_tools")


class WeatherTool(BaseTool):
    """Get weather information from Open-Meteo"""
    
    metadata = ToolMetadata(
        name="tool_get_weather",
        description="Get current weather and 7-day forecast for any location using Open-Meteo (no API key required).",
        parameters={
            "latitude": {"type": "number", "description": "Location latitude"},
            "longitude": {"type": "number", "description": "Location longitude"},
            "days": {"type": "integer", "description": "Forecast days", "default": 7}
        },
        rate_limited=False
    )
    
    async def execute(
        self,
        latitude: float,
        longitude: float,
        days: int = 7
    ) -> Dict[str, Any]:
        """Execute weather query"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code",
                        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                        "timezone": "auto",
                        "forecast_days": days
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    current = data.get("current", {})
                    daily = data.get("daily", {})
                    
                    return {
                        "success": True,
                        "location": {"lat": latitude, "lon": longitude},
                        "current": {
                            "temperature": current.get("temperature_2m"),
                            "humidity": current.get("relative_humidity_2m"),
                            "feels_like": current.get("apparent_temperature"),
                            "precipitation": current.get("precipitation"),
                            "weather_code": current.get("weather_code")
                        },
                        "forecast": [
                            {
                                "date": daily["time"][i] if "time" in daily else None,
                                "temp_max": daily["temperature_2m_max"][i] if "temperature_2m_max" in daily else None,
                                "temp_min": daily["temperature_2m_min"][i] if "temperature_2m_min" in daily else None,
                                "precipitation": daily["precipitation_sum"][i] if "precipitation_sum" in daily else None
                            }
                            for i in range(min(days, len(daily.get("time", []))))
                        ]
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Weather API returned {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Weather tool error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class CryptoPriceTool(BaseTool):
    """Get cryptocurrency prices from CoinGecko"""
    
    metadata = ToolMetadata(
        name="tool_get_crypto",
        description="Get current cryptocurrency prices and market data from CoinGecko.",
        parameters={
            "symbol": {"type": "string", "description": "Cryptocurrency symbol (e.g., bitcoin, ethereum)"},
            "currency": {"type": "string", "description": "Price currency", "default": "usd"}
        },
        rate_limited=True
    )
    
    async def execute(self, symbol: str, currency: str = "usd") -> Dict[str, Any]:
        """Execute crypto price query"""
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "ids": symbol.lower(),
                    "vs_currencies": currency,
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true"
                }
                
                # Add API key if available
                if settings.coingecko_api_key:
                    params["x_cg_demo_api_key"] = settings.coingecko_api_key
                
                response = await client.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params=params,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    coin_data = data.get(symbol.lower(), {})
                    
                    if coin_data:
                        return {
                            "success": True,
                            "symbol": symbol,
                            "price": coin_data.get(currency),
                            "currency": currency,
                            "change_24h": coin_data.get(f"{currency}_24h_change"),
                            "market_cap": coin_data.get(f"{currency}_market_cap"),
                            "volume_24h": coin_data.get(f"{currency}_24h_vol")
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Cryptocurrency '{symbol}' not found"
                        }
                else:
                    return {
                        "success": False,
                        "error": f"CoinGecko API returned {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Crypto price tool error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class AirQualityTool(BaseTool):
    """Get air quality information"""
    
    metadata = ToolMetadata(
        name="tool_get_air_quality",
        description="Get air quality index and PM2.5 data for a location.",
        parameters={
            "latitude": {"type": "number", "description": "Location latitude"},
            "longitude": {"type": "number", "description": "Location longitude"}
        },
        rate_limited=False
    )
    
    async def execute(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Execute air quality query"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.open-meteo.com/v1/air-quality",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "european_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    current = data.get("current", {})
                    
                    return {
                        "success": True,
                        "location": {"lat": latitude, "lon": longitude},
                        "aqi": current.get("european_aqi"),
                        "pm2_5": current.get("pm2_5"),
                        "pm10": current.get("pm10"),
                        "co": current.get("carbon_monoxide"),
                        "no2": current.get("nitrogen_dioxide")
                    }
                else:
                    return {
        return {
                        "success": False,
                        "error": f"Air quality API returned {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Air quality tool error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Register tools
ToolRegistry.register(WeatherTool())
ToolRegistry.register(CryptoPriceTool())
ToolRegistry.register(AirQualityTool())
                    }
                    
        except Exception as e:
            logger.error(f"Air quality tool error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Register tools
ToolRegistry.register(WeatherTool())
ToolRegistry.register(CryptoPriceTool())
ToolRegistry.register(AirQualityTool())
