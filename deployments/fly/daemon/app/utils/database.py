"""
Supabase database client
"""
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager
from supabase import create_client, Client
from postgrest.exceptions import APIError
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("database")


class DatabaseClient:
    """Supabase database client wrapper"""
    
    _instance = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def connect(self) -> Client:
        """Initialize Supabase client"""
        if self._client is None:
            try:
                self._client = create_client(
                    settings.supabase_url,
                    settings.supabase_service_key or settings.supabase_key
                )
                logger.info("Supabase client initialized")
            except Exception as e:
                logger.error("Failed to initialize Supabase client", error=str(e))
                raise
        return self._client
    
    @property
    def client(self) -> Client:
        """Get Supabase client"""
        if self._client is None:
            return self.connect()
        return self._client
    
    @property
    def table(self):
        """Get table builder"""
        return self.client.table
    
    async def fetch_one(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch single record"""
        try:
            query = self.table(table)
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            result = await query.execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching from {table}", error=str(e))
            return None
    
    async def fetch_many(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        ascending: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Fetch multiple records"""
        try:
            query = self.table(table)
            
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            if order_by:
                query = query.order(order_by, desc=not ascending)
            
            result = await query.limit(limit).offset(offset).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error fetching from {table}", error=str(e))
            return []
    
    async def insert(
        self,
        table: str,
        data: Dict[str, Any] | List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any] | List[Dict[str, Any]]]:
        """Insert record(s)"""
        try:
            result = await self.table(table).insert(data).execute()
            return result.data
        except Exception as e:
            logger.error(f"Error inserting into {table}", error=str(e))
            return None
    
    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Update record(s)"""
        try:
            query = self.table(table)
            for key, value in filters.items():
                query = query.eq(key, value)
            
            result = await query.update(data).execute()
            return result.data
        except Exception as e:
            logger.error(f"Error updating {table}", error=str(e))
            return None
    
    async def delete(
        self,
        table: str,
        filters: Dict[str, Any]
    ) -> bool:
        """Delete record(s)"""
        try:
            query = self.table(table)
            for key, value in filters.items():
                query = query.eq(key, value)
            
            await query.delete().execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting from {table}", error=str(e))
            return False
    
    async def rpc(
        self,
        function_name: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Call stored procedure"""
        try:
            result = await self.client.rpc(function_name, params or {}).execute()
            return result.data
        except Exception as e:
            logger.error(f"Error calling RPC {function_name}", error=str(e))
            return None


# Global database instance
db = DatabaseClient()
